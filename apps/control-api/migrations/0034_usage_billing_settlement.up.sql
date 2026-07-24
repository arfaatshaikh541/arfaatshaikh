-- Milestone 11: Usage, Billing and Settlement.
--
-- SubscriptionPlan/Feature/PlanFeature/EnterpriseSubscription/OperatorSubscription
-- (all listed as this milestone's "Entities" in the approved architecture)
-- already exist -- migration 0007 (Milestone 1) owns them; nothing here
-- rebuilds them. This milestone's genuinely new job is: raw usage events,
-- signed usage ingestion, usage aggregation, pricing, estimates, budgets,
-- invoices, operator settlements, reconciliation, disputes, and a
-- billing-provider abstraction.
--
-- Two of the approved "Entities" are deliberately folded rather than built
-- as separate tables:
--   - ReservationEstimate is NOT a new table. capacity_reservations.estimated_cost
--     (Milestone 5) and network_reservations.estimated_cost (Milestone 9) already
--     compute and persist a reservation's estimated cost at reservation time,
--     from the winning offer's own price_per_unit_hour. Rebuilding that as a
--     third table would duplicate data this codebase already has. The new
--     `quotes` table below covers the standalone/ad-hoc estimate case (asking
--     "what would N units of a metered usage metric cost" without reserving
--     anything) -- the genuinely new capability this milestone adds.
--   - BillingEvent and WebhookEvent fold into one `billing_provider_events`
--     table. Without a real external billing gateway reachable in this
--     sandbox (the same category of constraint as MinIO/Docker Hub), there is
--     no meaningful distinction between "a raw webhook we received" and "the
--     billing event we processed from it" -- both become the same record a
--     mock provider drives synchronously. See internal/platform/billingprovider.
CREATE TABLE usage_metrics (
    key         TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    unit        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO usage_metrics (key, name, unit) VALUES
    ('cpu_seconds', 'CPU seconds', 'seconds'),
    ('gpu_seconds', 'GPU seconds', 'seconds'),
    ('gpu_memory_gb_seconds', 'GPU memory', 'GB-seconds'),
    ('storage_gb_hours', 'Storage', 'GB-hours'),
    ('object_storage_gb_hours', 'Object storage', 'GB-hours'),
    ('network_ingress_gb', 'Network ingress', 'GB'),
    ('network_egress_gb', 'Network egress', 'GB'),
    ('private_network_gb_hours', 'Private-network usage', 'GB-hours'),
    ('network_slice_gbps_hours', 'Network-slice usage', 'Gbps-hours'),
    ('model_requests', 'Model requests', 'requests'),
    ('model_tokens', 'Model tokens', 'tokens'),
    ('inference_seconds', 'Inference time', 'seconds'),
    ('reservation_hours', 'Reservation time', 'hours'),
    ('confidential_computing_premium_hours', 'Confidential-computing premium', 'hours'),
    ('support_hours', 'Support', 'hours');

-- usage_events is the immutable raw ledger every aggregation/invoice is
-- computed from -- append-only via the deny-mutation trigger below, the
-- same discipline network_health_events/deployment_events already
-- established, plus a per-agent nonce uniqueness constraint for the
-- approved scope's "duplicate protection"/"idempotency" requirements
-- (mirroring control_messages' nonce handling). Always both operator- and
-- tenant-scoped: usage only ever happens on an operator's infrastructure on
-- behalf of a specific tenant, unlike network_health_events where a
-- tenant-less operator-only signal is legitimate.
CREATE TABLE usage_events (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id            UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    enterprise_tenant_id   UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    cluster_agent_id       UUID NOT NULL REFERENCES cluster_agents(id),
    deployment_id          UUID REFERENCES deployments(id),
    capacity_reservation_id UUID REFERENCES capacity_reservations(id),
    network_reservation_id UUID REFERENCES network_reservations(id),
    usage_metric_key       TEXT NOT NULL REFERENCES usage_metrics(key),
    quantity                NUMERIC(18,6) NOT NULL CHECK (quantity >= 0),
    occurred_at              TIMESTAMPTZ NOT NULL,
    nonce                    TEXT NOT NULL,
    signature                TEXT NOT NULL,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cluster_agent_id, nonce)
);
CREATE INDEX idx_usage_events_operator ON usage_events(operator_id, occurred_at DESC);
CREATE INDEX idx_usage_events_tenant ON usage_events(enterprise_tenant_id, occurred_at DESC);
CREATE INDEX idx_usage_events_metric_period ON usage_events(enterprise_tenant_id, usage_metric_key, occurred_at);

ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_events FORCE ROW LEVEL SECURITY;
CREATE POLICY usage_events_operator_scope ON usage_events
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY usage_events_tenant_scope ON usage_events
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY usage_events_platform_bypass ON usage_events
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE FUNCTION usage_events_deny_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'usage_events is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER usage_events_no_update
    BEFORE UPDATE ON usage_events
    FOR EACH ROW EXECUTE FUNCTION usage_events_deny_mutation();

CREATE TRIGGER usage_events_no_delete
    BEFORE DELETE ON usage_events
    FOR EACH ROW EXECUTE FUNCTION usage_events_deny_mutation();

-- usage_aggregations is a recomputable rollup, not append-only evidence --
-- re-aggregating an in-progress period is expected (more usage_events may
-- have landed since the last computation) and upserts via the unique
-- constraint below, the same "no live scheduler, computed on demand"
-- precedent Milestone 10's slo_evaluations established, except here the
-- output itself is idempotently replaced rather than accumulated as new
-- history, since an aggregation is a derived summary, not independent
-- evidence.
CREATE TABLE usage_aggregations (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id          UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    enterprise_tenant_id UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    usage_metric_key     TEXT NOT NULL REFERENCES usage_metrics(key),
    period_start         TIMESTAMPTZ NOT NULL,
    period_end           TIMESTAMPTZ NOT NULL,
    total_quantity       NUMERIC(18,6) NOT NULL,
    source_event_count   INT NOT NULL,
    computed_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (operator_id, enterprise_tenant_id, usage_metric_key, period_start, period_end)
);
CREATE INDEX idx_usage_aggregations_tenant ON usage_aggregations(enterprise_tenant_id, period_start DESC);
CREATE INDEX idx_usage_aggregations_operator ON usage_aggregations(operator_id, period_start DESC);

ALTER TABLE usage_aggregations ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_aggregations FORCE ROW LEVEL SECURITY;
CREATE POLICY usage_aggregations_operator_scope ON usage_aggregations
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY usage_aggregations_tenant_scope ON usage_aggregations
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY usage_aggregations_platform_bypass ON usage_aggregations
    USING (current_setting('app.platform_bypass', true) = 'true');

-- price_books/price_rules is metered-usage pricing -- a distinct pricing
-- dimension from capacity_offers/network_service_offers' own
-- price_per_unit_hour (reservation pricing already visible to tenants
-- since Milestone 5/9); this is what a usage_metric costs per unit,
-- versioned, one active book per operator via a partial unique index
-- mirroring attestation_policies' "one active policy per cluster"
-- (revocation/replacement is create-new-then-supersede-old, never an
-- in-place edit of a book already in use for real invoices).
-- operator_id is nullable: a NULL-operator book is the platform reference
-- price book, used only if an operator has never published its own.
CREATE TABLE price_books (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID REFERENCES operators(id) ON DELETE CASCADE,
    version     INT NOT NULL,
    currency    TEXT NOT NULL DEFAULT 'USD',
    status      TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    created_by  UUID NOT NULL REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_at TIMESTAMPTZ,
    UNIQUE (operator_id, version)
);
CREATE UNIQUE INDEX idx_price_books_operator_active ON price_books(operator_id) WHERE status = 'active';
-- A second partial unique index is needed for the platform-default book
-- specifically, since operator_id IS NULL never equals itself for the
-- purposes of a plain UNIQUE/partial-unique index over a nullable column.
CREATE UNIQUE INDEX idx_price_books_platform_active ON price_books((operator_id IS NULL)) WHERE status = 'active' AND operator_id IS NULL;

ALTER TABLE price_books ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_books FORCE ROW LEVEL SECURITY;
CREATE POLICY price_books_operator_scope ON price_books
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
-- Tenants may read any active price book (their own operator's, or the
-- platform default), mirroring network_service_offers_enterprise_read's
-- "any tenant sees any active offer" marketplace-read pattern -- a tenant
-- deciding whether to request a Quote needs to know what an active book's
-- rules actually charge.
CREATE POLICY price_books_enterprise_read ON price_books
    FOR SELECT USING (status = 'active');
CREATE POLICY price_books_platform_bypass ON price_books
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE price_rules (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    price_book_id    UUID NOT NULL REFERENCES price_books(id) ON DELETE CASCADE,
    usage_metric_key TEXT NOT NULL REFERENCES usage_metrics(key),
    unit_price       NUMERIC(14,6) NOT NULL CHECK (unit_price >= 0),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (price_book_id, usage_metric_key)
);

-- price_rules has no operator_id/enterprise_tenant_id of its own --
-- visibility is entirely derived from its parent price_books row, so its
-- RLS policies re-join to price_books rather than duplicating scope
-- columns. This is the one table in this migration that departs from the
-- otherwise-universal "denormalize the scope columns" convention, because
-- price_rules has no independent existence or write path apart from its
-- book (every rule is written in the same request that authors its book).
ALTER TABLE price_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_rules FORCE ROW LEVEL SECURITY;
CREATE POLICY price_rules_operator_scope ON price_rules
    USING (EXISTS (SELECT 1 FROM price_books pb WHERE pb.id = price_rules.price_book_id
        AND pb.operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid));
CREATE POLICY price_rules_enterprise_read ON price_rules
    FOR SELECT USING (EXISTS (SELECT 1 FROM price_books pb WHERE pb.id = price_rules.price_book_id AND pb.status = 'active'));
CREATE POLICY price_rules_platform_bypass ON price_rules
    USING (current_setting('app.platform_bypass', true) = 'true');

-- quotes is an immutable, ad-hoc cost estimate snapshot -- "estimates
-- before deployment" for the standalone case (not tied to a specific
-- reservation, which already has its own estimated_cost -- see this
-- migration's header comment). line_items is a JSONB array of
-- {usage_metric_key, quantity, unit_price, amount} computed server-side
-- from the resolved price book at request time -- never trusted from the
-- client (the approved scope's "no frontend price trust" requirement).
CREATE TABLE quotes (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    operator_id          UUID NOT NULL REFERENCES operators(id),
    price_book_id        UUID NOT NULL REFERENCES price_books(id),
    line_items           JSONB NOT NULL,
    estimated_total      NUMERIC(14,4) NOT NULL,
    currency             TEXT NOT NULL,
    requested_by         UUID NOT NULL REFERENCES users(id),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_quotes_tenant ON quotes(enterprise_tenant_id, created_at DESC);

ALTER TABLE quotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotes FORCE ROW LEVEL SECURITY;
CREATE POLICY quotes_tenant_scope ON quotes
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY quotes_platform_bypass ON quotes
    USING (current_setting('app.platform_bypass', true) = 'true');

-- budgets is enterprise-owned; hard_limit is recorded and surfaced (an
-- exceeded hard_limit budget fires a critical-severity alert -- see
-- internal/modules/assurance's widened alert_rules.metric_source below)
-- but does not itself block new reservations/deployments in this
-- milestone -- wiring an actual spend-blocking check into Milestone 5/9's
-- EvaluateAndReserve flows is deliberately out of scope here; see
-- docs/project-status.md's Known Limitations.
CREATE TABLE budgets (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    name             TEXT NOT NULL,
    period_days      INT NOT NULL CHECK (period_days > 0),
    threshold_amount NUMERIC(14,4) NOT NULL CHECK (threshold_amount > 0),
    currency         TEXT NOT NULL DEFAULT 'USD',
    hard_limit       BOOLEAN NOT NULL DEFAULT FALSE,
    status           TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_by       UUID NOT NULL REFERENCES users(id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_budgets_tenant ON budgets(enterprise_tenant_id);

ALTER TABLE budgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE budgets FORCE ROW LEVEL SECURITY;
CREATE POLICY budgets_tenant_scope ON budgets
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY budgets_platform_bypass ON budgets
    USING (current_setting('app.platform_bypass', true) = 'true');

-- invoices is dual-scope like deployments/network_reservations/incidents --
-- both the tenant being billed and the operator whose infrastructure
-- produced the usage need visibility. line_items mirrors quotes' shape
-- (computed server-side from usage_aggregations against the price book
-- active when the invoice was issued, snapshotted at issue time so a later
-- price-book change never retroactively changes an already-issued
-- invoice's numbers).
CREATE TABLE invoices (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    operator_id          UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    price_book_id        UUID NOT NULL REFERENCES price_books(id),
    period_start         TIMESTAMPTZ NOT NULL,
    period_end           TIMESTAMPTZ NOT NULL,
    line_items           JSONB NOT NULL,
    subtotal             NUMERIC(14,4) NOT NULL,
    tax_amount           NUMERIC(14,4) NOT NULL DEFAULT 0,
    total                NUMERIC(14,4) NOT NULL,
    currency             TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'issued' CHECK (status IN ('issued', 'paid', 'disputed', 'void')),
    external_ref         TEXT,
    issued_by            UUID NOT NULL REFERENCES users(id),
    issued_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_invoices_tenant ON invoices(enterprise_tenant_id, issued_at DESC);
CREATE INDEX idx_invoices_operator ON invoices(operator_id, issued_at DESC);

ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;
CREATE POLICY invoices_tenant_scope ON invoices
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY invoices_operator_scope ON invoices
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY invoices_platform_bypass ON invoices
    USING (current_setting('app.platform_bypass', true) = 'true');

-- settlement_records is operator-owned only -- a settlement aggregates
-- revenue across every tenant invoice for one operator over a period, not
-- a single tenant's concern, unlike invoices themselves.
CREATE TABLE settlement_records (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id         UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    period_start        TIMESTAMPTZ NOT NULL,
    period_end          TIMESTAMPTZ NOT NULL,
    gross_amount        NUMERIC(14,4) NOT NULL,
    platform_fee_amount NUMERIC(14,4) NOT NULL,
    net_amount          NUMERIC(14,4) NOT NULL,
    currency            TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'reconciled', 'paid', 'disputed')),
    invoice_count        INT NOT NULL,
    created_by            UUID NOT NULL REFERENCES users(id),
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    reconciled_at          TIMESTAMPTZ
);
CREATE INDEX idx_settlement_records_operator ON settlement_records(operator_id, period_start DESC);

ALTER TABLE settlement_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE settlement_records FORCE ROW LEVEL SECURITY;
CREATE POLICY settlement_records_operator_scope ON settlement_records
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY settlement_records_platform_bypass ON settlement_records
    USING (current_setting('app.platform_bypass', true) = 'true');

-- adjustments is append-only -- a correction is itself an immutable fact,
-- the same reasoning audit_events/deployment_events already established.
-- Exactly one of invoice_id/settlement_id is set (num_nonnulls = 1);
-- operator_id is always set (denormalized from whichever parent it
-- corrects) and enterprise_tenant_id is set only when correcting an
-- invoice (settlements have no single tenant).
CREATE TABLE adjustments (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id           UUID REFERENCES invoices(id) ON DELETE CASCADE,
    settlement_id        UUID REFERENCES settlement_records(id) ON DELETE CASCADE,
    operator_id          UUID NOT NULL REFERENCES operators(id),
    enterprise_tenant_id UUID REFERENCES enterprise_tenants(id),
    amount               NUMERIC(14,4) NOT NULL,
    reason               TEXT NOT NULL,
    created_by           UUID NOT NULL REFERENCES users(id),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(invoice_id, settlement_id) = 1)
);
CREATE INDEX idx_adjustments_invoice ON adjustments(invoice_id);
CREATE INDEX idx_adjustments_settlement ON adjustments(settlement_id);

ALTER TABLE adjustments ENABLE ROW LEVEL SECURITY;
ALTER TABLE adjustments FORCE ROW LEVEL SECURITY;
CREATE POLICY adjustments_operator_scope ON adjustments
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY adjustments_tenant_scope ON adjustments
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY adjustments_platform_bypass ON adjustments
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE FUNCTION adjustments_deny_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'adjustments is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER adjustments_no_update
    BEFORE UPDATE ON adjustments
    FOR EACH ROW EXECUTE FUNCTION adjustments_deny_mutation();

CREATE TRIGGER adjustments_no_delete
    BEFORE DELETE ON adjustments
    FOR EACH ROW EXECUTE FUNCTION adjustments_deny_mutation();

-- credit_notes is dual-scope like invoices (denormalizing operator_id from
-- the invoice it credits), since the operator whose revenue is reduced
-- needs visibility alongside the tenant receiving the credit.
CREATE TABLE credit_notes (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id           UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    enterprise_tenant_id UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    operator_id          UUID NOT NULL REFERENCES operators(id),
    amount               NUMERIC(14,4) NOT NULL CHECK (amount > 0),
    reason               TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'issued' CHECK (status IN ('issued', 'applied')),
    created_by           UUID NOT NULL REFERENCES users(id),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_at           TIMESTAMPTZ
);
CREATE INDEX idx_credit_notes_invoice ON credit_notes(invoice_id);
CREATE INDEX idx_credit_notes_tenant ON credit_notes(enterprise_tenant_id);

ALTER TABLE credit_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_notes FORCE ROW LEVEL SECURITY;
CREATE POLICY credit_notes_tenant_scope ON credit_notes
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY credit_notes_operator_scope ON credit_notes
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY credit_notes_platform_bypass ON credit_notes
    USING (current_setting('app.platform_bypass', true) = 'true');

-- billing_disputes is dual-scope like invoices/credit_notes -- a tenant
-- opens it, the operator (or platform) resolves it.
CREATE TABLE billing_disputes (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id           UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    enterprise_tenant_id UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    operator_id          UUID NOT NULL REFERENCES operators(id),
    reason               TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'under_review', 'resolved', 'rejected')),
    resolution_note      TEXT NOT NULL DEFAULT '',
    opened_by            UUID NOT NULL REFERENCES users(id),
    resolved_by          UUID REFERENCES users(id),
    opened_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at          TIMESTAMPTZ
);
CREATE INDEX idx_billing_disputes_invoice ON billing_disputes(invoice_id);

ALTER TABLE billing_disputes ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_disputes FORCE ROW LEVEL SECURITY;
CREATE POLICY billing_disputes_tenant_scope ON billing_disputes
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY billing_disputes_operator_scope ON billing_disputes
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY billing_disputes_platform_bypass ON billing_disputes
    USING (current_setting('app.platform_bypass', true) = 'true');

-- billing_provider_events is append-only -- see this migration's header
-- comment on folding BillingEvent/WebhookEvent into one table. Exactly one
-- of invoice_id/settlement_id is set, same shape as adjustments.
CREATE TABLE billing_provider_events (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id           UUID REFERENCES invoices(id) ON DELETE CASCADE,
    settlement_id        UUID REFERENCES settlement_records(id) ON DELETE CASCADE,
    operator_id          UUID NOT NULL REFERENCES operators(id),
    enterprise_tenant_id UUID REFERENCES enterprise_tenants(id),
    provider_type        TEXT NOT NULL DEFAULT 'mock',
    event_type           TEXT NOT NULL,
    external_ref         TEXT,
    detail                JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(invoice_id, settlement_id) = 1)
);
CREATE INDEX idx_billing_provider_events_invoice ON billing_provider_events(invoice_id);
CREATE INDEX idx_billing_provider_events_settlement ON billing_provider_events(settlement_id);

ALTER TABLE billing_provider_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_provider_events FORCE ROW LEVEL SECURITY;
CREATE POLICY billing_provider_events_operator_scope ON billing_provider_events
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY billing_provider_events_tenant_scope ON billing_provider_events
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY billing_provider_events_platform_bypass ON billing_provider_events
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE FUNCTION billing_provider_events_deny_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'billing_provider_events is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER billing_provider_events_no_update
    BEFORE UPDATE ON billing_provider_events
    FOR EACH ROW EXECUTE FUNCTION billing_provider_events_deny_mutation();

CREATE TRIGGER billing_provider_events_no_delete
    BEFORE DELETE ON billing_provider_events
    FOR EACH ROW EXECUTE FUNCTION billing_provider_events_deny_mutation();

-- Milestone 10 widened alert_rules.metric_source generically rather than
-- one enum value per source; this migration adds 'budget_utilization' the
-- same way -- an enterprise's budget alert reuses the existing generic
-- alert infrastructure entirely rather than a parallel budget-alert
-- system. resource_id on such a rule is the budget's own id.
ALTER TABLE alert_rules DROP CONSTRAINT alert_rules_metric_source_check;
ALTER TABLE alert_rules ADD CONSTRAINT alert_rules_metric_source_check
    CHECK (metric_source IN (
        'deployment_availability', 'network_reservation_provisioning', 'attestation_success_rate',
        'policy_compliance_rate', 'slo_burn_rate', 'budget_utilization'
    ));
