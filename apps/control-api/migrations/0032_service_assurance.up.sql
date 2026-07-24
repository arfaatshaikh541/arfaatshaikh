-- Milestone 10: Service Assurance and Observability.
--
-- The approved scope's "Correlate: workload health, cluster/node/GPU
-- health, model availability, network latency/packet loss, policy
-- compliance, attestation, cost, capacity, operator incidents" requirement
-- is deliberately NOT built as a new table duplicating data this codebase
-- already produces -- deployment_events (Milestone 7), network_health_events
-- (Milestone 9), attestation_results (Milestone 8), and
-- policy_evaluation_records (Milestone 3/5) already are that data. Instead
-- it is a read-time join across those existing tables, implemented in
-- internal/modules/assurance's correlated-health query, no new storage.
--
-- What genuinely does not exist yet, and this migration adds: SLOs (a
-- target either an operator commits to for its own infrastructure --
-- reusing the already-seeded-but-unenforced operator.sla.manage permission
-- -- or an enterprise sets for its own workload/deployment), Incidents (a
-- human-tracked record, dual-scope like deployments/network_reservations
-- since an operator-infra incident can visibly affect a specific tenant,
-- reusing the already-seeded incidents.view/incidents.manage/
-- operator.incidents.manage permissions -- seeded since Milestone 1,
-- unenforced until now), and Alerts (a rule an operator or enterprise
-- defines against the same correlated signals, evaluated on demand).
--
-- SLO/alert-rule evaluation has no live scheduler in this codebase (no
-- worker cron wired to it) -- both are evaluated lazily, on demand, the
-- same "reclaimExpired runs at the top of every call" precedent Milestone
-- 5 established for reservation-hold expiry (see that milestone's own
-- documented limitation). A future milestone that adds a real background
-- worker schedule should add a periodic sweep here too.
CREATE TABLE slo_definitions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id       UUID REFERENCES operators(id) ON DELETE CASCADE,
    enterprise_tenant_id UUID REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    metric_source     TEXT NOT NULL CHECK (metric_source IN (
        'deployment_availability', 'network_reservation_provisioning', 'attestation_success_rate', 'policy_compliance_rate'
    )),
    -- resource_type/resource_id, like audit_events.target_type/target_id,
    -- is a soft reference (no FK -- it names one of several possible
    -- tables) resolved at evaluation time, not at insert time. NULL means
    -- "aggregate across every resource in this SLO's scope" rather than one
    -- specific resource.
    resource_type     TEXT,
    resource_id       UUID,
    target_percentage NUMERIC(5,2) NOT NULL CHECK (target_percentage > 0 AND target_percentage <= 100),
    window_days       INT NOT NULL CHECK (window_days > 0),
    status            TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_by        UUID NOT NULL REFERENCES users(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(operator_id, enterprise_tenant_id) = 1)
);
CREATE INDEX idx_slo_definitions_operator ON slo_definitions(operator_id);
CREATE INDEX idx_slo_definitions_tenant ON slo_definitions(enterprise_tenant_id);

ALTER TABLE slo_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE slo_definitions FORCE ROW LEVEL SECURITY;
CREATE POLICY slo_definitions_operator_scope ON slo_definitions
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY slo_definitions_tenant_scope ON slo_definitions
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY slo_definitions_platform_bypass ON slo_definitions
    USING (current_setting('app.platform_bypass', true) = 'true');

-- slo_evaluations is append-only evidence of each on-demand evaluation --
-- operator_id/enterprise_tenant_id are denormalized from the parent
-- slo_definitions row (the same denormalize-for-RLS-simplicity convention
-- network_service_evaluations already uses for its own parent request),
-- rather than requiring a join through slo_definitions for RLS to work.
CREATE TABLE slo_evaluations (
    id                                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slo_definition_id                   UUID NOT NULL REFERENCES slo_definitions(id) ON DELETE CASCADE,
    operator_id                         UUID REFERENCES operators(id),
    enterprise_tenant_id                UUID REFERENCES enterprise_tenants(id),
    evaluated_at                        TIMESTAMPTZ NOT NULL DEFAULT now(),
    actual_percentage                   NUMERIC(5,2) NOT NULL,
    error_budget_remaining_percentage   NUMERIC(6,2) NOT NULL,
    status                              TEXT NOT NULL CHECK (status IN ('ok', 'at_risk', 'breached')),
    sample_size                         INT NOT NULL,
    detail                              JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX idx_slo_evaluations_definition ON slo_evaluations(slo_definition_id, evaluated_at DESC);

ALTER TABLE slo_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE slo_evaluations FORCE ROW LEVEL SECURITY;
CREATE POLICY slo_evaluations_operator_scope ON slo_evaluations
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY slo_evaluations_tenant_scope ON slo_evaluations
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY slo_evaluations_platform_bypass ON slo_evaluations
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE FUNCTION slo_evaluations_deny_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'slo_evaluations is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER slo_evaluations_no_update
    BEFORE UPDATE ON slo_evaluations
    FOR EACH ROW EXECUTE FUNCTION slo_evaluations_deny_mutation();

CREATE TRIGGER slo_evaluations_no_delete
    BEFORE DELETE ON slo_evaluations
    FOR EACH ROW EXECUTE FUNCTION slo_evaluations_deny_mutation();

-- incidents is dual-scope like deployments/network_reservations (at least
-- one of operator_id/enterprise_tenant_id, not exactly one): an
-- operator-infrastructure incident (e.g. a cluster degradation) can be
-- purely internal (no affected tenant on record yet) or bound to the
-- specific tenant whose deployment it affects; a tenant can also open an
-- incident about its own workload with no operator involved at all (e.g. a
-- model-quality concern).
CREATE TABLE incidents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id     UUID REFERENCES operators(id) ON DELETE CASCADE,
    enterprise_tenant_id UUID REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    severity        TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved')),
    resource_type   TEXT,
    resource_id     UUID,
    opened_by       UUID NOT NULL REFERENCES users(id),
    acknowledged_by UUID REFERENCES users(id),
    acknowledged_at TIMESTAMPTZ,
    resolved_by     UUID REFERENCES users(id),
    resolved_at     TIMESTAMPTZ,
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(operator_id, enterprise_tenant_id) >= 1)
);
CREATE INDEX idx_incidents_operator ON incidents(operator_id, opened_at DESC);
CREATE INDEX idx_incidents_tenant ON incidents(enterprise_tenant_id, opened_at DESC);

ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents FORCE ROW LEVEL SECURITY;
CREATE POLICY incidents_operator_scope ON incidents
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY incidents_tenant_scope ON incidents
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY incidents_platform_bypass ON incidents
    USING (current_setting('app.platform_bypass', true) = 'true');

-- incident_events is the append-only timeline (opened/acknowledged/
-- comment/resolved), the same discipline deployment_events/
-- network_health_events already established for their own event streams.
CREATE TABLE incident_events (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id    UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    operator_id    UUID REFERENCES operators(id),
    enterprise_tenant_id UUID REFERENCES enterprise_tenants(id),
    event_type     TEXT NOT NULL,
    detail         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by     UUID REFERENCES users(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_incident_events_incident ON incident_events(incident_id, created_at);

ALTER TABLE incident_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE incident_events FORCE ROW LEVEL SECURITY;
CREATE POLICY incident_events_operator_scope ON incident_events
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY incident_events_tenant_scope ON incident_events
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY incident_events_platform_bypass ON incident_events
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE FUNCTION incident_events_deny_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'incident_events is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER incident_events_no_update
    BEFORE UPDATE ON incident_events
    FOR EACH ROW EXECUTE FUNCTION incident_events_deny_mutation();

CREATE TRIGGER incident_events_no_delete
    BEFORE DELETE ON incident_events
    FOR EACH ROW EXECUTE FUNCTION incident_events_deny_mutation();

-- alert_rules, unlike incidents, has exactly one owner (whoever defines the
-- rule) -- there is no legitimate second party who needs visibility into a
-- rule definition the way a tenant needs visibility into an incident
-- affecting its own workload.
CREATE TABLE alert_rules (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id   UUID REFERENCES operators(id) ON DELETE CASCADE,
    enterprise_tenant_id UUID REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    metric_source TEXT NOT NULL CHECK (metric_source IN (
        'deployment_availability', 'network_reservation_provisioning', 'attestation_success_rate', 'policy_compliance_rate', 'slo_burn_rate'
    )),
    resource_type TEXT,
    resource_id   UUID,
    comparison    TEXT NOT NULL CHECK (comparison IN ('lt', 'gt')),
    threshold     NUMERIC(10,4) NOT NULL,
    severity      TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused')),
    created_by    UUID NOT NULL REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(operator_id, enterprise_tenant_id) = 1)
);
CREATE INDEX idx_alert_rules_operator ON alert_rules(operator_id);
CREATE INDEX idx_alert_rules_tenant ON alert_rules(enterprise_tenant_id);

ALTER TABLE alert_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_rules FORCE ROW LEVEL SECURITY;
CREATE POLICY alert_rules_operator_scope ON alert_rules
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY alert_rules_tenant_scope ON alert_rules
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY alert_rules_platform_bypass ON alert_rules
    USING (current_setting('app.platform_bypass', true) = 'true');

-- alerts is the fired-instance history for a rule -- status transitions
-- firing -> resolved via a single UPDATE (not append-only; the same
-- transition-in-place pattern network_reservations' status column uses),
-- since an alert's resolution is an update to the same logical incident of
-- firing, not a new independent fact the way a health event is.
CREATE TABLE alerts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_rule_id UUID NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
    operator_id   UUID REFERENCES operators(id),
    enterprise_tenant_id UUID REFERENCES enterprise_tenants(id),
    status        TEXT NOT NULL DEFAULT 'firing' CHECK (status IN ('firing', 'resolved')),
    value_at_fire NUMERIC(10,4) NOT NULL,
    detail        JSONB NOT NULL DEFAULT '{}'::jsonb,
    fired_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at   TIMESTAMPTZ
);
CREATE INDEX idx_alerts_rule ON alerts(alert_rule_id, fired_at DESC);

ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts FORCE ROW LEVEL SECURITY;
CREATE POLICY alerts_operator_scope ON alerts
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY alerts_tenant_scope ON alerts
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY alerts_platform_bypass ON alerts
    USING (current_setting('app.platform_bypass', true) = 'true');
