-- Milestone 7: Secure Deployment Orchestration.
--
-- This is the milestone that finally connects everything built so far: a
-- Milestone 4 workload_version and a Milestone 5 capacity_reservation
-- become a Milestone 6 signed deployment plan, sent down the Milestone 6
-- control-message channel to a cluster agent, which independently
-- validates and executes it. Approval here reuses the exact lightweight
-- requested_by/approved_by dual-control pattern this codebase has now
-- applied six times (support_access_grants, sovereignty_policies,
-- model_versions, workload_versions, vulnerability_exceptions,
-- capacity_reservations) -- not the fuller multi-step ApprovalPolicy/
-- ApprovalStep/EmergencyOverride system the architecture document
-- describes elsewhere, which is not itself a numbered milestone and is
-- deliberately deferred until enough real duplication justifies building
-- it (see docs/project-status.md's Unresolved Risks).
--
-- deployments is the running (fictionally -- no real cluster exists)
-- instance, one per capacity_reservation. Like capacity_reservations, it
-- legitimately belongs to two scope dimensions (the tenant that owns the
-- workload, the operator whose capacity it runs on), so it uses the same
-- three-permissive-policy RLS shape.
CREATE TABLE deployments (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id    UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    operator_id             UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    cluster_agent_id        UUID NOT NULL REFERENCES cluster_agents(id),
    workload_version_id     UUID NOT NULL REFERENCES workload_versions(id),
    capacity_reservation_id UUID NOT NULL REFERENCES capacity_reservations(id),
    namespace               TEXT NOT NULL,
    replica_count           INT NOT NULL DEFAULT 1 CHECK (replica_count > 0),
    status                  TEXT NOT NULL DEFAULT 'pending_plan_approval' CHECK (status IN (
                                'pending_plan_approval', 'plan_approved', 'submitted', 'deploying', 'running',
                                'scaling', 'pausing', 'paused', 'resuming', 'rolling_back', 'terminating',
                                'terminated', 'failed'
                            )),
    requested_by            UUID NOT NULL REFERENCES users(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (capacity_reservation_id)
);
CREATE INDEX idx_deployments_tenant ON deployments(enterprise_tenant_id);
CREATE INDEX idx_deployments_operator ON deployments(operator_id);
CREATE INDEX idx_deployments_cluster_agent ON deployments(cluster_agent_id);

ALTER TABLE deployments ENABLE ROW LEVEL SECURITY;
ALTER TABLE deployments FORCE ROW LEVEL SECURITY;
CREATE POLICY deployments_tenant_scope ON deployments
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY deployments_operator_scope ON deployments
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY deployments_platform_bypass ON deployments
    USING (current_setting('app.platform_bypass', true) = 'true');

-- deployment_plans is the signed manifest artifact -- immutable once
-- signed, versioned (a new version per rescale/rollback that changes
-- desired state). manifest snapshots the workload version's components
-- (container image digests, command, args, non-secret env, health checks)
-- and the resource/network/security declarations at the moment the plan
-- was drafted -- a later edit to the workload version never silently
-- changes an already-approved plan. manifest_hash + signature (the
-- platform CA's signature, from internal/platform/pki.CA.SignMessage, the
-- same mechanism Milestone 6 uses for deployment-plan-validate messages)
-- make tampering detectable; a cluster agent verifies both independently
-- before ever executing anything (the same local-enforcement discipline
-- Milestone 6 established).
CREATE TABLE deployment_plans (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deployment_id         UUID NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    version               INT NOT NULL CHECK (version > 0),
    status                TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
                              'draft', 'pending_approval', 'approved', 'rejected', 'submitted', 'active', 'superseded'
                          )),
    manifest              JSONB NOT NULL,
    manifest_hash         TEXT NOT NULL,
    signature             TEXT,
    requested_by          UUID NOT NULL REFERENCES users(id),
    approved_by           UUID REFERENCES users(id),
    rejected_reason       TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (deployment_id, version),
    CONSTRAINT deployment_plans_no_self_approval CHECK (approved_by IS NULL OR approved_by <> requested_by)
);
CREATE INDEX idx_deployment_plans_deployment ON deployment_plans(deployment_id);
CREATE INDEX idx_deployment_plans_tenant ON deployment_plans(enterprise_tenant_id);

ALTER TABLE deployment_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE deployment_plans FORCE ROW LEVEL SECURITY;
CREATE POLICY deployment_plans_tenant_scope ON deployment_plans
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY deployment_plans_platform_bypass ON deployment_plans
    USING (current_setting('app.platform_bypass', true) = 'true');

-- deployment_events is the append-only lifecycle stream ("deployment event
-- stream" in the approved build scope) -- every state transition, whether
-- user-initiated (actor_user_id set) or agent-reported (actor_user_id
-- null), gets one immutable row. Same append-only trigger discipline as
-- audit_events (Milestone 1) and policy_evaluation_records (Milestone 3).
CREATE TABLE deployment_events (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deployment_id         UUID NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    operator_id           UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    event_type            TEXT NOT NULL,
    detail                JSONB NOT NULL DEFAULT '{}'::jsonb,
    actor_user_id         UUID REFERENCES users(id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_deployment_events_deployment ON deployment_events(deployment_id, created_at);
CREATE INDEX idx_deployment_events_tenant ON deployment_events(enterprise_tenant_id);
CREATE INDEX idx_deployment_events_operator ON deployment_events(operator_id);

ALTER TABLE deployment_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE deployment_events FORCE ROW LEVEL SECURITY;
CREATE POLICY deployment_events_tenant_scope ON deployment_events
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY deployment_events_operator_scope ON deployment_events
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY deployment_events_platform_bypass ON deployment_events
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE FUNCTION deployment_events_deny_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'deployment_events is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER deployment_events_no_update
    BEFORE UPDATE ON deployment_events
    FOR EACH ROW EXECUTE FUNCTION deployment_events_deny_mutation();

CREATE TRIGGER deployment_events_no_delete
    BEFORE DELETE ON deployment_events
    FOR EACH ROW EXECUTE FUNCTION deployment_events_deny_mutation();

-- workload_secrets ("secure secrets" in the approved build scope): values
-- are encrypted at rest with AES-256-GCM (internal/platform/secretsvault,
-- the same envelope-encryption shape internal/platform/pki and
-- internal/platform/security's TOTP manager already use for their own
-- secrets, each with its own required-with-no-fallback encryption key).
-- No route in this codebase ever returns a decrypted value; a deployment
-- plan's manifest references a secret by key name only (see
-- deployments.Service's manifest-building code), and only the cluster
-- agent actually assigned to that deployment can fetch decrypted values,
-- through a dedicated, certificate-authenticated endpoint.
CREATE TABLE workload_secrets (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    workload_version_id   UUID NOT NULL REFERENCES workload_versions(id) ON DELETE CASCADE,
    key                   TEXT NOT NULL CHECK (key ~ '^[A-Z][A-Z0-9_]*$'),
    encrypted_value       TEXT NOT NULL,
    created_by            UUID NOT NULL REFERENCES users(id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workload_version_id, key)
);
CREATE INDEX idx_workload_secrets_tenant ON workload_secrets(enterprise_tenant_id);

ALTER TABLE workload_secrets ENABLE ROW LEVEL SECURITY;
ALTER TABLE workload_secrets FORCE ROW LEVEL SECURITY;
CREATE POLICY workload_secrets_tenant_scope ON workload_secrets
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY workload_secrets_platform_bypass ON workload_secrets
    USING (current_setting('app.platform_bypass', true) = 'true');

-- Milestone 6's control_messages.message_type only knew about deployment-
-- plan validation. Rather than adding one enum value per lifecycle action
-- (execute/scale/pause/resume/rollback/terminate, times two for the
-- result direction -- 12 more values), this widens the CHECK to two
-- generic types: 'deployment_command' (to_agent, payload discriminated by
-- an "action" field) and 'deployment_command_result' (from_agent,
-- payload discriminated the same way). Replay protection, signature
-- verification, and the exact-byte-preserving TEXT payload column all
-- apply identically regardless of which action a command payload names.
ALTER TABLE control_messages DROP CONSTRAINT control_messages_message_type_check;
ALTER TABLE control_messages ADD CONSTRAINT control_messages_message_type_check
    CHECK (message_type IN (
        'deployment_plan_validate', 'deployment_plan_validation_result',
        'deployment_command', 'deployment_command_result'
    ));
