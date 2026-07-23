-- Milestone 5: Placement and Capacity Engine.
--
-- capacity_offers is the new, structured, sellable-capacity abstraction an
-- operator publishes against one of its own clusters (Milestone 2's
-- clusters/node_pools/accelerators/capacity_snapshots describe physical
-- inventory and agent-reported facts; capacity_offers is the operator's own
-- commercial decision about how much of that capacity it is willing to
-- sell, at what price, right now). This milestone is explicitly scoped to
-- a single operator publishing to every tenant -- no bilateral
-- OperatorEnterpriseAgreement gating, no cross-operator federation, no
-- marketplace settlement -- that full "Federated Capacity Exchange" is
-- Milestone 12's job. available_capacity is decremented by an atomic
-- conditional UPDATE (see capacityoffers/placement repositories) rather
-- than SELECT ... FOR UPDATE, so concurrent reservation attempts race
-- safely at the database's own row-lock level.
--
-- region_id is denormalized from the offer's cluster (via the cluster's
-- data centre or edge site) at write time by the service layer, never
-- accepted from the client -- consistent with the platform-wide rule that
-- region/jurisdiction facts are never trusted from the browser.
--
-- Three RLS policies apply to capacity_offers, not the usual two: the
-- owning operator gets full read/write (capacity_offers_operator_scope),
-- ANY authenticated enterprise-scoped request may read (SELECT-only)
-- active offers regardless of which operator owns them
-- (capacity_offers_enterprise_read) -- this is what makes a single-operator
-- offer part of a tenant-visible marketplace without any federation
-- machinery -- and platform bypass as always.

CREATE TABLE capacity_offers (
    id                            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id                   UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    cluster_id                    UUID NOT NULL REFERENCES clusters(id) ON DELETE CASCADE,
    region_id                     UUID NOT NULL REFERENCES regions(id),
    accelerator_type              TEXT NOT NULL DEFAULT 'cpu_only',
    total_capacity                INT NOT NULL CHECK (total_capacity > 0),
    available_capacity            INT NOT NULL CHECK (available_capacity >= 0),
    price_per_unit_hour           NUMERIC(12,4) NOT NULL CHECK (price_per_unit_hour >= 0),
    currency                      TEXT NOT NULL DEFAULT 'USD',
    confidential_computing_available BOOLEAN NOT NULL DEFAULT FALSE,
    estimated_kwh_per_unit_hour   NUMERIC(10,4) NOT NULL DEFAULT 0 CHECK (estimated_kwh_per_unit_hour >= 0),
    status                        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'withdrawn')),
    created_by                    UUID NOT NULL REFERENCES users(id),
    created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (available_capacity <= total_capacity)
);
CREATE INDEX idx_capacity_offers_operator ON capacity_offers(operator_id);
CREATE INDEX idx_capacity_offers_region ON capacity_offers(region_id);
CREATE INDEX idx_capacity_offers_status ON capacity_offers(status) WHERE status = 'active';

ALTER TABLE capacity_offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE capacity_offers FORCE ROW LEVEL SECURITY;

CREATE POLICY capacity_offers_operator_scope ON capacity_offers
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);

CREATE POLICY capacity_offers_enterprise_read ON capacity_offers
    FOR SELECT
    USING (
        NULLIF(current_setting('app.tenant_id', true), '') IS NOT NULL
        AND status = 'active'
    );

CREATE POLICY capacity_offers_platform_bypass ON capacity_offers
    USING (current_setting('app.platform_bypass', true) = 'true');

-- placement_requests: one row per "an enterprise asked the placement
-- engine to find capacity for a published workload version." simulate=true
-- runs every eligibility/ranking/cost/energy step but never reserves
-- capacity -- the "simulation mode" required by this milestone.
CREATE TABLE placement_requests (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    workload_version_id   UUID NOT NULL REFERENCES workload_versions(id),
    quantity              INT NOT NULL CHECK (quantity > 0),
    simulate              BOOLEAN NOT NULL DEFAULT FALSE,
    status                TEXT NOT NULL DEFAULT 'evaluated' CHECK (status IN ('evaluated', 'reserved', 'expired', 'cancelled')),
    requested_by          UUID NOT NULL REFERENCES users(id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_placement_requests_tenant ON placement_requests(enterprise_tenant_id);
CREATE INDEX idx_placement_requests_workload_version ON placement_requests(workload_version_id);

ALTER TABLE placement_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE placement_requests FORCE ROW LEVEL SECURITY;
CREATE POLICY placement_requests_tenant_scope ON placement_requests
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY placement_requests_platform_bypass ON placement_requests
    USING (current_setting('app.platform_bypass', true) = 'true');

-- placement_evaluations: one row per candidate capacity_offer considered
-- for a placement_request -- the explainability record this milestone
-- requires. Fields the offer owner could otherwise mutate or delete out
-- source from under it (operator_id, accelerator_type) are snapshotted
-- here at evaluation time, and `explanation` carries the full ordered
-- per-step trace (eligibility, sovereignty, security, capacity, runtime
-- compatibility, cost, energy) so a rejection is never just a bare
-- decision. rank is only set for eligible candidates.
CREATE TABLE placement_evaluations (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id    UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    placement_request_id   UUID NOT NULL REFERENCES placement_requests(id) ON DELETE CASCADE,
    capacity_offer_id       UUID NOT NULL REFERENCES capacity_offers(id),
    operator_id             UUID NOT NULL,
    region_id               UUID NOT NULL,
    accelerator_type        TEXT NOT NULL,
    decision                TEXT NOT NULL CHECK (decision IN ('eligible', 'rejected')),
    rank                    INT,
    estimated_cost          NUMERIC(14,4) NOT NULL DEFAULT 0,
    estimated_energy_kwh    NUMERIC(14,4) NOT NULL DEFAULT 0,
    reason_codes            JSONB NOT NULL DEFAULT '[]'::jsonb,
    explanation             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_placement_evaluations_request ON placement_evaluations(placement_request_id);
CREATE INDEX idx_placement_evaluations_tenant ON placement_evaluations(enterprise_tenant_id);

ALTER TABLE placement_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE placement_evaluations FORCE ROW LEVEL SECURITY;
CREATE POLICY placement_evaluations_tenant_scope ON placement_evaluations
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY placement_evaluations_platform_bypass ON placement_evaluations
    USING (current_setting('app.platform_bypass', true) = 'true');

-- capacity_reservations is the one table in this schema that legitimately
-- belongs to two different scope dimensions at once: the enterprise tenant
-- that holds it, and the operator whose capacity_offers.available_capacity
-- it is holding. Postgres RLS policies for the same command OR together,
-- so three permissive policies (tenant OR operator OR platform bypass) give
-- each side exactly its own rows without a join, unlike every other table
-- in this schema which has had exactly one scope dimension.
--
-- Dual control mirrors the requested_by/approved_by + no-self-approval
-- pattern used four times already (support_access_grants, sovereignty_
-- policies, model_versions, workload_versions): approval_required is a
-- snapshot of the referenced workload_versions.deployment_approval_required
-- at hold time (a field that has existed since Milestone 4 but was unused
-- until now), and a reservation created against a version that requires
-- approval cannot become 'committed' until a genuinely different user
-- approves it. expires_at supports lazy reclamation of abandoned holds
-- (see placement/repository.go's reclaimExpired) -- there is no
-- scheduler/cron in this codebase yet to sweep these proactively, a known
-- limitation documented in docs/project-status.md pending a future
-- milestone's worker integration.
CREATE TABLE capacity_reservations (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id   UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    operator_id            UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    placement_request_id   UUID NOT NULL REFERENCES placement_requests(id),
    capacity_offer_id      UUID NOT NULL REFERENCES capacity_offers(id),
    quantity               INT NOT NULL CHECK (quantity > 0),
    price_per_unit_hour    NUMERIC(12,4) NOT NULL,
    estimated_cost         NUMERIC(14,4) NOT NULL,
    status                 TEXT NOT NULL DEFAULT 'held' CHECK (status IN ('held', 'committed', 'released', 'expired')),
    approval_required      BOOLEAN NOT NULL DEFAULT FALSE,
    requested_by           UUID NOT NULL REFERENCES users(id),
    approved_by            UUID REFERENCES users(id),
    held_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at             TIMESTAMPTZ NOT NULL,
    committed_at           TIMESTAMPTZ,
    released_at            TIMESTAMPTZ,
    release_reason         TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT capacity_reservations_no_self_approval CHECK (approved_by IS NULL OR approved_by <> requested_by)
);
CREATE INDEX idx_capacity_reservations_tenant ON capacity_reservations(enterprise_tenant_id);
CREATE INDEX idx_capacity_reservations_operator ON capacity_reservations(operator_id);
CREATE INDEX idx_capacity_reservations_offer ON capacity_reservations(capacity_offer_id);
CREATE INDEX idx_capacity_reservations_expiry ON capacity_reservations(status, expires_at) WHERE status = 'held';

ALTER TABLE capacity_reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE capacity_reservations FORCE ROW LEVEL SECURITY;

CREATE POLICY capacity_reservations_tenant_scope ON capacity_reservations
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

CREATE POLICY capacity_reservations_operator_scope ON capacity_reservations
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);

CREATE POLICY capacity_reservations_platform_bypass ON capacity_reservations
    USING (current_setting('app.platform_bypass', true) = 'true');
