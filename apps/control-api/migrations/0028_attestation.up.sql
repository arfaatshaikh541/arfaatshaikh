-- Milestone 8: Confidential Computing and Attestation.
--
-- Designs a provider-neutral remote-attestation layer: an operator
-- configures what a confidential-computing-capable cluster's hardware is
-- expected to report (attestation_policies), a cluster agent requests a
-- server-issued challenge (attestation_sessions) and submits signed
-- evidence bound to a specific deployment, and control-api -- not the
-- agent -- verifies that evidence against the policy and records the
-- outcome (attestation_results). This is the opposite trust direction from
-- Milestone 6/7's "local enforcement" model (the agent decides,
-- control-api records): remote attestation is inherently verifier-side,
-- since the verifier is the one making a key-release decision on the
-- result (see internal/modules/deployments' AgentFetchSecrets, extended
-- this milestone to require a fresh, passing result before releasing any
-- workload secret for a confidential-computing-required deployment).
--
-- Only a 'mock' provider_type is implemented (internal/platform/attestation.MockProvider,
-- a simple expected-vs-reported measurement comparison) -- this milestone
-- makes no claim of verifying genuine AMD SEV-SNP/Intel TDX/NVIDIA
-- confidential-computing/cloud-confidential-VM/HSM evidence; the CHECK
-- constraint below just reserves the vocabulary for future real adapters,
-- consistent with the approved architecture's explicit "no fake claims of
-- confidential computing" requirement.
CREATE TABLE attestation_policies (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id           UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    cluster_id            UUID NOT NULL REFERENCES clusters(id) ON DELETE CASCADE,
    provider_type         TEXT NOT NULL DEFAULT 'mock' CHECK (provider_type IN (
                              'mock', 'amd_sev_snp', 'intel_tdx', 'nvidia_cc', 'cloud_confidential_vm', 'hsm'
                          )),
    expected_measurements JSONB NOT NULL,
    status                TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_by            UUID NOT NULL REFERENCES users(id),
    revoked_by            UUID REFERENCES users(id),
    revoked_at            TIMESTAMPTZ,
    revoked_reason        TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_attestation_policies_operator ON attestation_policies(operator_id);
-- One active policy per cluster at a time -- "revocation" is documented as
-- create-new-then-revoke-old, not an in-place edit, so a policy's
-- expected_measurements are as immutable as a deployment plan's manifest
-- once evaluations may have run against them.
CREATE UNIQUE INDEX idx_attestation_policies_cluster_active ON attestation_policies(cluster_id) WHERE status = 'active';

ALTER TABLE attestation_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE attestation_policies FORCE ROW LEVEL SECURITY;
CREATE POLICY attestation_policies_operator_scope ON attestation_policies
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY attestation_policies_platform_bypass ON attestation_policies
    USING (current_setting('app.platform_bypass', true) = 'true');

-- attestation_sessions holds the server-issued attestation challenge --
-- deliberately the reverse of every prior milestone's nonce handling
-- (Milestone 6/7 control messages: the agent mints its own nonce, since it
-- is the one proving freshness of its own signed message). Here control-api
-- itself must mint the nonce, because the whole point of a remote-attestation
-- challenge is that the verifier -- not the prover -- controls what value
-- must appear inside the evidence, so a prover cannot pre-compute or replay
-- evidence for a challenge it does not yet know. Consuming a session
-- exactly once (status pending -> consumed, checked via a conditional
-- UPDATE before any evidence is accepted) is the actual replay-protection
-- mechanism; a session whose expires_at has passed is rejected regardless
-- of whether it was ever consumed.
CREATE TABLE attestation_sessions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id      UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    cluster_agent_id UUID NOT NULL REFERENCES cluster_agents(id) ON DELETE CASCADE,
    nonce            TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'consumed', 'expired')),
    issued_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at       TIMESTAMPTZ NOT NULL,
    UNIQUE (cluster_agent_id, nonce)
);
CREATE INDEX idx_attestation_sessions_agent ON attestation_sessions(cluster_agent_id);

ALTER TABLE attestation_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE attestation_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY attestation_sessions_operator_scope ON attestation_sessions
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY attestation_sessions_platform_bypass ON attestation_sessions
    USING (current_setting('app.platform_bypass', true) = 'true');

-- attestation_results is the append-only evidence-plus-verification record
-- ("evidence retention" in the approved scope) -- a new attestation is
-- always a new row, never an edit to a previous one, using the same
-- BEFORE UPDATE/DELETE-trigger-raises-exception pattern as audit_events,
-- policy_evaluation_records, and deployment_events, independently
-- redefined here per this codebase's established convention. It belongs to
-- two scope dimensions at once -- the operator whose cluster produced the
-- evidence, and the tenant whose deployment it is bound to ("deployment
-- binding" in the approved scope) -- so it uses the same three-permissive-policy
-- dual-scope RLS shape as deployments/deployment_events. The tenant-facing
-- "customer verification view" redacts measurements/raw_evidence at the
-- handler layer (see internal/modules/attestation's package doc), not by
-- RLS -- RLS only decides which *rows* are visible, not which *columns*.
CREATE TABLE attestation_results (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id            UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    enterprise_tenant_id   UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    cluster_agent_id       UUID NOT NULL REFERENCES cluster_agents(id),
    attestation_session_id UUID NOT NULL UNIQUE REFERENCES attestation_sessions(id),
    attestation_policy_id  UUID REFERENCES attestation_policies(id),
    deployment_id          UUID NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
    provider_type          TEXT NOT NULL,
    measurements           JSONB NOT NULL,
    raw_evidence           TEXT NOT NULL,
    decision               TEXT NOT NULL CHECK (decision IN ('pass', 'fail')),
    reason_codes           JSONB NOT NULL DEFAULT '[]'::jsonb,
    nonce                  TEXT NOT NULL,
    signature              TEXT NOT NULL,
    evaluated_at           TIMESTAMPTZ NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_attestation_results_deployment ON attestation_results(deployment_id, evaluated_at DESC);
CREATE INDEX idx_attestation_results_operator ON attestation_results(operator_id);
CREATE INDEX idx_attestation_results_tenant ON attestation_results(enterprise_tenant_id);

ALTER TABLE attestation_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE attestation_results FORCE ROW LEVEL SECURITY;
CREATE POLICY attestation_results_tenant_scope ON attestation_results
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY attestation_results_operator_scope ON attestation_results
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY attestation_results_platform_bypass ON attestation_results
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE FUNCTION attestation_results_deny_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'attestation_results is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER attestation_results_no_update
    BEFORE UPDATE ON attestation_results
    FOR EACH ROW EXECUTE FUNCTION attestation_results_deny_mutation();

CREATE TRIGGER attestation_results_no_delete
    BEFORE DELETE ON attestation_results
    FOR EACH ROW EXECUTE FUNCTION attestation_results_deny_mutation();
