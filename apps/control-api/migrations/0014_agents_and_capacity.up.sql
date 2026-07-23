-- Milestone 2: operator-agent registration, certificate lifecycle, and
-- signed capacity-snapshot ingestion.
--
-- operator_agents: a machine identity registered by operator staff
-- (operator.agents.manage). Registration issues a single-use bootstrap
-- token (hashed at rest, same opaque-token pattern as every other token in
-- this schema) the agent exchanges for its first certificate.
--
-- agent_certificates: real X.509 certificates issued by the control-api's
-- local development CA (internal/platform/pki) from a CSR the agent itself
-- generates -- the private key never leaves the agent and is never stored
-- here, only the issued (public) certificate.
--
-- capacity_snapshots: signed-assertion inventory facts per the approved
-- infrastructure-inventory model -- every row this schema's only ingestion
-- path (POST .../capacity-snapshots) creates has already had its signature
-- verified against the submitting agent's current certificate before the
-- row is written, so trust_status is 'verified' for every row written by
-- that path; 'unverified'/'rejected' exist for a possible future
-- manual-entry path and are never produced by agent ingestion today.

CREATE TABLE operator_agents (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id                 UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    name                        TEXT NOT NULL,
    status                      TEXT NOT NULL DEFAULT 'pending_bootstrap' CHECK (status IN ('pending_bootstrap', 'active', 'revoked')),
    bootstrap_token_hash        TEXT UNIQUE,
    bootstrap_token_expires_at  TIMESTAMPTZ,
    bootstrap_consumed_at       TIMESTAMPTZ,
    registered_by               UUID NOT NULL REFERENCES users(id),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_operator_agents_operator ON operator_agents(operator_id);

ALTER TABLE operator_agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE operator_agents FORCE ROW LEVEL SECURITY;
CREATE POLICY operator_agents_operator_scope ON operator_agents
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY operator_agents_platform_bypass ON operator_agents
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE agent_certificates (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id       UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    operator_agent_id UUID NOT NULL REFERENCES operator_agents(id) ON DELETE CASCADE,
    serial_number     TEXT NOT NULL UNIQUE,
    certificate_pem   TEXT NOT NULL,
    issued_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at        TIMESTAMPTZ NOT NULL,
    revoked_at        TIMESTAMPTZ,
    revoked_reason    TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_agent_certificates_operator ON agent_certificates(operator_id);
CREATE INDEX idx_agent_certificates_agent ON agent_certificates(operator_agent_id);

ALTER TABLE agent_certificates ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_certificates FORCE ROW LEVEL SECURITY;
CREATE POLICY agent_certificates_operator_scope ON agent_certificates
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY agent_certificates_platform_bypass ON agent_certificates
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE capacity_snapshots (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id       UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    operator_agent_id UUID NOT NULL REFERENCES operator_agents(id) ON DELETE CASCADE,
    cluster_id        UUID NOT NULL REFERENCES clusters(id) ON DELETE CASCADE,
    source            TEXT NOT NULL DEFAULT 'operator_agent' CHECK (source IN ('operator_agent', 'manual')),
    trust_status      TEXT NOT NULL DEFAULT 'unverified' CHECK (trust_status IN ('verified', 'unverified', 'rejected')),
    payload           JSONB NOT NULL,
    signature         TEXT,
    collected_at      TIMESTAMPTZ NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_capacity_snapshots_operator ON capacity_snapshots(operator_id);
CREATE INDEX idx_capacity_snapshots_cluster_collected ON capacity_snapshots(cluster_id, collected_at DESC);

ALTER TABLE capacity_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE capacity_snapshots FORCE ROW LEVEL SECURITY;
CREATE POLICY capacity_snapshots_operator_scope ON capacity_snapshots
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY capacity_snapshots_platform_bypass ON capacity_snapshots
    USING (current_setting('app.platform_bypass', true) = 'true');
