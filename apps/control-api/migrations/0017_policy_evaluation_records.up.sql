-- Milestone 3: structured, queryable compliance evidence for every policy
-- evaluation (approved architecture §22: "evaluation always emits a
-- structured, signed, immutable PolicyEvaluationRecord... this record, not
-- just the decision, is what's retained for compliance evidence"). Every
-- real (non-simulation) evaluation also gets a normal audit_events entry
-- for the standard cross-cutting audit trail; this table exists alongside
-- it for structured, queryable evidence with its own tamper-evident
-- append-only guarantee, exactly like audit_events already has.

CREATE TABLE policy_evaluation_records (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id   UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    sovereignty_policy_id  UUID NOT NULL REFERENCES sovereignty_policies(id),
    policy_version         INT NOT NULL,
    decision               TEXT NOT NULL CHECK (decision IN ('allow', 'deny')),
    reason_codes           JSONB NOT NULL,
    candidate              JSONB NOT NULL,
    inputs_hash            TEXT NOT NULL,
    is_simulation          BOOLEAN NOT NULL DEFAULT FALSE,
    evaluated_by           UUID REFERENCES users(id),
    evaluated_at           TIMESTAMPTZ NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_policy_evaluation_records_tenant ON policy_evaluation_records(enterprise_tenant_id, evaluated_at DESC);
CREATE INDEX idx_policy_evaluation_records_policy ON policy_evaluation_records(sovereignty_policy_id, evaluated_at DESC);

ALTER TABLE policy_evaluation_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE policy_evaluation_records FORCE ROW LEVEL SECURITY;

CREATE POLICY policy_evaluation_records_tenant_scope ON policy_evaluation_records
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

CREATE POLICY policy_evaluation_records_platform_bypass ON policy_evaluation_records
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE FUNCTION policy_evaluation_records_deny_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'policy_evaluation_records is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER policy_evaluation_records_no_update
    BEFORE UPDATE ON policy_evaluation_records
    FOR EACH ROW EXECUTE FUNCTION policy_evaluation_records_deny_mutation();

CREATE TRIGGER policy_evaluation_records_no_delete
    BEFORE DELETE ON policy_evaluation_records
    FOR EACH ROW EXECUTE FUNCTION policy_evaluation_records_deny_mutation();
