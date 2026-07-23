-- Milestone 6: Operator and Cluster Agents.
--
-- Milestone 2 built the operator-agent identity model (operator_agents,
-- agent_certificates, capacity_snapshots) -- registration, bootstrap-token
-- issuance, certificate issuance from a CSR, and one-directional signed
-- capacity-snapshot ingestion. This milestone adds three things Milestone 2
-- deliberately deferred: certificate rotation (an existing agent renewing
-- its identity without re-bootstrapping), a cluster-scoped agent identity
-- distinct from the operator-wide one (a cluster agent "registers
-- authorised clusters" and later "receives signed deployment plans" --
-- narrower and more privileged in a different way than an operator agent
-- that only reports inventory), and a bidirectional signed-control-message
-- channel with replay protection, which is what carries a deployment-plan
-- validation request down to a cluster agent and its signed decision back.
--
-- rotated_from_certificate_id on the existing agent_certificates table
-- lets an operator agent rotate too -- "certificate rotation" is listed as
-- a capability of the agent model generally, not just cluster agents.
ALTER TABLE agent_certificates ADD COLUMN rotated_from_certificate_id UUID REFERENCES agent_certificates(id);

-- cluster_agents mirrors operator_agents field-for-field, scoped one level
-- narrower (a specific cluster, not the whole operator) -- same bootstrap-
-- token-then-certificate lifecycle, same RLS shape.
CREATE TABLE cluster_agents (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id                 UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    cluster_id                  UUID NOT NULL REFERENCES clusters(id) ON DELETE CASCADE,
    name                        TEXT NOT NULL,
    status                      TEXT NOT NULL DEFAULT 'pending_bootstrap' CHECK (status IN ('pending_bootstrap', 'active', 'revoked')),
    bootstrap_token_hash        TEXT UNIQUE,
    bootstrap_token_expires_at  TIMESTAMPTZ,
    bootstrap_consumed_at       TIMESTAMPTZ,
    registered_by               UUID NOT NULL REFERENCES users(id),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_cluster_agents_operator ON cluster_agents(operator_id);
CREATE INDEX idx_cluster_agents_cluster ON cluster_agents(cluster_id);

ALTER TABLE cluster_agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE cluster_agents FORCE ROW LEVEL SECURITY;
CREATE POLICY cluster_agents_operator_scope ON cluster_agents
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY cluster_agents_platform_bypass ON cluster_agents
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE cluster_agent_certificates (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id                 UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    cluster_agent_id            UUID NOT NULL REFERENCES cluster_agents(id) ON DELETE CASCADE,
    serial_number               TEXT NOT NULL UNIQUE,
    certificate_pem             TEXT NOT NULL,
    rotated_from_certificate_id UUID REFERENCES cluster_agent_certificates(id),
    issued_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at                  TIMESTAMPTZ NOT NULL,
    revoked_at                  TIMESTAMPTZ,
    revoked_reason              TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_cluster_agent_certificates_operator ON cluster_agent_certificates(operator_id);
CREATE INDEX idx_cluster_agent_certificates_agent ON cluster_agent_certificates(cluster_agent_id);

ALTER TABLE cluster_agent_certificates ENABLE ROW LEVEL SECURITY;
ALTER TABLE cluster_agent_certificates FORCE ROW LEVEL SECURITY;
CREATE POLICY cluster_agent_certificates_operator_scope ON cluster_agent_certificates
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY cluster_agent_certificates_platform_bypass ON cluster_agent_certificates
    USING (current_setting('app.platform_bypass', true) = 'true');

-- control_messages is the signed, bidirectional channel between control-api
-- and a cluster agent. direction='to_agent' rows are signed by the
-- platform CA's own key (internal/platform/pki -- the same root that
-- issues agent certificates now also signs outbound control messages, so
-- an agent's chain of trust for verifying either is the one CA cert it
-- already needs); direction='from_agent' rows are signed by the
-- responding agent's own current certificate. (cluster_agent_id, nonce) is
-- unique -- this is the actual replay-protection mechanism: a nonce
-- reused by the same agent in either direction is rejected outright,
-- independent of the signature check.
--
-- payload is TEXT, not JSONB, deliberately: it holds the *exact* bytes a
-- signature was computed over, and JSONB does not round-trip byte-for-byte
-- (Postgres reformats whitespace and key representation on the way in and
-- back out). Any of that reformatting would make VerifySignature fail
-- against perfectly legitimate messages. Application code parses it with
-- encoding/json when it needs structured field access; the database never
-- needs to query into its structure.
CREATE TABLE control_messages (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id       UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    cluster_agent_id  UUID NOT NULL REFERENCES cluster_agents(id) ON DELETE CASCADE,
    direction         TEXT NOT NULL CHECK (direction IN ('to_agent', 'from_agent')),
    message_type      TEXT NOT NULL CHECK (message_type IN ('deployment_plan_validate', 'deployment_plan_validation_result')),
    in_response_to    UUID REFERENCES control_messages(id),
    nonce             TEXT NOT NULL,
    payload           TEXT NOT NULL,
    signature         TEXT NOT NULL,
    signed_at         TIMESTAMPTZ NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'responded', 'rejected_replay', 'rejected_signature', 'rejected_expired_signing_time')),
    received_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cluster_agent_id, nonce)
);
CREATE INDEX idx_control_messages_operator ON control_messages(operator_id);
CREATE INDEX idx_control_messages_agent_status ON control_messages(cluster_agent_id, status);

ALTER TABLE control_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE control_messages FORCE ROW LEVEL SECURITY;
CREATE POLICY control_messages_operator_scope ON control_messages
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY control_messages_platform_bypass ON control_messages
    USING (current_setting('app.platform_bypass', true) = 'true');

-- deployment_plan_validations is the local-enforcement decision record: did
-- the cluster agent (not control-api) independently verify the plan's
-- signature and accept or reject it against its own view of operator/
-- sovereignty policy. workload_version_id/capacity_reservation_id are
-- informational cross-references into Milestone 4/5's tenant-owned
-- entities (an operator cannot read those rows directly -- RLS still fully
-- protects them -- this table only ever stores the id an operator already
-- had from the reservation it is testing deployment for).
CREATE TABLE deployment_plan_validations (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id             UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    cluster_agent_id        UUID NOT NULL REFERENCES cluster_agents(id) ON DELETE CASCADE,
    control_message_id      UUID NOT NULL REFERENCES control_messages(id),
    plan_id                 TEXT NOT NULL,
    workload_version_id     UUID REFERENCES workload_versions(id),
    capacity_reservation_id UUID REFERENCES capacity_reservations(id),
    signature_valid         BOOLEAN NOT NULL,
    policy_decision         TEXT NOT NULL CHECK (policy_decision IN ('allow', 'deny')),
    reason_codes            JSONB NOT NULL DEFAULT '[]'::jsonb,
    decided_at              TIMESTAMPTZ NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_deployment_plan_validations_operator ON deployment_plan_validations(operator_id);
CREATE INDEX idx_deployment_plan_validations_agent ON deployment_plan_validations(cluster_agent_id);

ALTER TABLE deployment_plan_validations ENABLE ROW LEVEL SECURITY;
ALTER TABLE deployment_plan_validations FORCE ROW LEVEL SECURITY;
CREATE POLICY deployment_plan_validations_operator_scope ON deployment_plan_validations
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY deployment_plan_validations_platform_bypass ON deployment_plan_validations
    USING (current_setting('app.platform_bypass', true) = 'true');
