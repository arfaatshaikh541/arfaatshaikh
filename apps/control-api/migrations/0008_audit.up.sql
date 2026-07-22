-- Milestone 1: append-only, hash-chained audit log. `seq` is the strict
-- monotonic ordering used to build the chain; rows are never updated or
-- deleted (enforced by revoking UPDATE/DELETE below).

CREATE TABLE audit_events (
    seq           BIGSERIAL PRIMARY KEY,
    id            UUID NOT NULL UNIQUE,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_user_id UUID REFERENCES users(id),
    scope_type    TEXT NOT NULL CHECK (scope_type IN ('enterprise', 'operator', 'platform')),
    scope_id      UUID,
    action        TEXT NOT NULL,
    target_type   TEXT,
    target_id     UUID,
    evidence      JSONB NOT NULL DEFAULT '{}'::jsonb,
    prev_hash     TEXT NOT NULL,
    hash          TEXT NOT NULL
);
CREATE INDEX idx_audit_events_scope ON audit_events(scope_type, scope_id, occurred_at DESC);
CREATE INDEX idx_audit_events_actor ON audit_events(actor_user_id, occurred_at DESC);

ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;

CREATE POLICY audit_events_tenant_scope ON audit_events
    USING (scope_type = 'enterprise' AND scope_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

CREATE POLICY audit_events_operator_scope ON audit_events
    USING (scope_type = 'operator' AND scope_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);

CREATE POLICY audit_events_platform_bypass ON audit_events
    USING (current_setting('app.platform_bypass', true) = 'true');

-- Append-only enforcement: a BEFORE UPDATE/DELETE trigger raises an
-- exception unconditionally. Unlike a GRANT/REVOKE, this holds even for the
-- table owner / application role, so a compromised or misused application
-- connection still cannot rewrite or delete history -- only INSERT and
-- SELECT (subject to the RLS policies above) succeed.
CREATE FUNCTION audit_events_deny_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_events_no_update
    BEFORE UPDATE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_deny_mutation();

CREATE TRIGGER audit_events_no_delete
    BEFORE DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_deny_mutation();
