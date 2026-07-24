-- Milestone 9: Network and Edge Services.
--
-- Milestone 2's network_capabilities table (migration 0013) is static
-- inventory -- "this data centre/edge site has private-5G capability with
-- this much bandwidth" -- the same way node_pools/accelerators/storage_pools
-- describe compute inventory without being anything a tenant can reserve.
-- This milestone is the marketplace layer on top of it, exactly the
-- relationship Milestone 5's capacity_offers/capacity_reservations has to
-- Milestone 2's node_pools/accelerators: an operator publishes a sellable
-- network_service_offer against one of its already-registered
-- network_capabilities rows, a tenant requests one (optionally correlated
-- to a specific deployment -- "workload-to-network correlation" in the
-- approved scope), and a successful request becomes a network_reservation.
--
-- Deliberately out of scope, per the approved Milestone 9 Build list (which
-- is materially shorter than Milestone 5/7's): a full policy-engine
-- integration for network-specific sovereignty dimensions (network
-- connectivity requirements already exist as workload_versions.network_requirements
-- JSONB from Milestone 4 and as general "public-network restrictions"/
-- "private-connectivity requirements" sovereignty-policy dimensions; this
-- milestone does not add a dedicated ConnectivityPolicy entity or wire a
-- new policy-engine dimension for it); dual-control approval for network
-- reservations (there is no analogue to workload_versions.deployment_approval_required
-- driving an approval requirement here, so every successful reservation
-- commits immediately -- see docs/project-status.md's Deliberate security
-- decisions); and network usage/billing records (metering integration is a
-- later milestone's job, mirroring how Milestone 5 explicitly deferred
-- commercial/billing gating).
CREATE TABLE network_service_offers (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id              UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    network_capability_id    UUID NOT NULL REFERENCES network_capabilities(id) ON DELETE CASCADE,
    region_id                UUID NOT NULL REFERENCES regions(id),
    service_class            TEXT NOT NULL,
    total_bandwidth_gbps     NUMERIC(10,2) NOT NULL CHECK (total_bandwidth_gbps > 0),
    available_bandwidth_gbps NUMERIC(10,2) NOT NULL CHECK (available_bandwidth_gbps >= 0),
    max_latency_ms           NUMERIC(6,2),
    price_per_unit_hour      NUMERIC(12,4) NOT NULL CHECK (price_per_unit_hour >= 0),
    currency                 TEXT NOT NULL DEFAULT 'USD',
    status                   TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'withdrawn')),
    created_by               UUID NOT NULL REFERENCES users(id),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (available_bandwidth_gbps <= total_bandwidth_gbps)
);
CREATE INDEX idx_network_service_offers_operator ON network_service_offers(operator_id);
CREATE INDEX idx_network_service_offers_capability ON network_service_offers(network_capability_id);

ALTER TABLE network_service_offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE network_service_offers FORCE ROW LEVEL SECURITY;
CREATE POLICY network_service_offers_operator_scope ON network_service_offers
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
-- Tenants browse the cross-operator network-service marketplace the same
-- way they browse capacity_offers -- any active offer, regardless of which
-- operator published it, not just their own operator memberships (there
-- are none; a tenant has no operator membership at all).
CREATE POLICY network_service_offers_enterprise_read ON network_service_offers
    FOR SELECT USING (status = 'active');
CREATE POLICY network_service_offers_platform_bypass ON network_service_offers
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE network_service_requests (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id   UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    deployment_id          UUID REFERENCES deployments(id),
    required_bandwidth_gbps NUMERIC(10,2) NOT NULL CHECK (required_bandwidth_gbps > 0),
    max_latency_ms         NUMERIC(6,2),
    service_class          TEXT,
    simulate               BOOLEAN NOT NULL DEFAULT FALSE,
    status                 TEXT NOT NULL DEFAULT 'evaluated' CHECK (status IN ('evaluated', 'reserved', 'cancelled')),
    requested_by           UUID NOT NULL REFERENCES users(id),
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_network_service_requests_tenant ON network_service_requests(enterprise_tenant_id);
CREATE INDEX idx_network_service_requests_deployment ON network_service_requests(deployment_id);

ALTER TABLE network_service_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE network_service_requests FORCE ROW LEVEL SECURITY;
CREATE POLICY network_service_requests_tenant_scope ON network_service_requests
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY network_service_requests_platform_bypass ON network_service_requests
    USING (current_setting('app.platform_bypass', true) = 'true');

-- network_service_evaluations is explained evidence, the same "every
-- placement decision must be explainable" discipline Milestone 5's
-- placement_evaluations established -- ranking here is a plain,
-- deterministic sort (bandwidth/latency eligibility, then price), never an
-- AI/ML decision.
CREATE TABLE network_service_evaluations (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id      UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    network_service_request_id UUID NOT NULL REFERENCES network_service_requests(id) ON DELETE CASCADE,
    network_service_offer_id UUID NOT NULL REFERENCES network_service_offers(id),
    operator_id               UUID NOT NULL REFERENCES operators(id),
    region_id                 UUID NOT NULL REFERENCES regions(id),
    service_class              TEXT NOT NULL,
    decision                  TEXT NOT NULL CHECK (decision IN ('eligible', 'rejected')),
    rank                       INT,
    estimated_cost             NUMERIC(14,4) NOT NULL,
    reason_codes               JSONB NOT NULL DEFAULT '[]'::jsonb,
    explanation                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_network_service_evaluations_request ON network_service_evaluations(network_service_request_id);

ALTER TABLE network_service_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE network_service_evaluations FORCE ROW LEVEL SECURITY;
CREATE POLICY network_service_evaluations_tenant_scope ON network_service_evaluations
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY network_service_evaluations_platform_bypass ON network_service_evaluations
    USING (current_setting('app.platform_bypass', true) = 'true');

-- network_reservations has no 'held' status and no approval workflow --
-- unlike capacity_reservations, there is no analogue to
-- workload_versions.deployment_approval_required to drive a dual-control
-- gate here, so a successful request commits immediately (see this
-- migration's header comment). provisioning_status tracks the separate,
-- asynchronous question of whether the operator's cluster agent has
-- actually confirmed provisioning yet (see control_messages' widened
-- message_type below) -- a reservation can be 'committed' (bandwidth is
-- reserved, billing-relevant) while still 'pending' provisioning.
CREATE TABLE network_reservations (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id        UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    operator_id                 UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    network_service_request_id UUID NOT NULL REFERENCES network_service_requests(id),
    network_service_offer_id   UUID NOT NULL REFERENCES network_service_offers(id),
    deployment_id               UUID REFERENCES deployments(id),
    cluster_agent_id             UUID REFERENCES cluster_agents(id),
    bandwidth_gbps               NUMERIC(10,2) NOT NULL CHECK (bandwidth_gbps > 0),
    price_per_unit_hour          NUMERIC(12,4) NOT NULL,
    estimated_cost                NUMERIC(14,4) NOT NULL,
    status                        TEXT NOT NULL DEFAULT 'committed' CHECK (status IN ('committed', 'released')),
    provisioning_status           TEXT NOT NULL DEFAULT 'pending' CHECK (provisioning_status IN ('pending', 'provisioned', 'failed')),
    requested_by                  UUID NOT NULL REFERENCES users(id),
    committed_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    released_at                   TIMESTAMPTZ,
    release_reason                TEXT,
    updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_network_reservations_tenant ON network_reservations(enterprise_tenant_id);
CREATE INDEX idx_network_reservations_operator ON network_reservations(operator_id);
CREATE INDEX idx_network_reservations_offer ON network_reservations(network_service_offer_id);

ALTER TABLE network_reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE network_reservations FORCE ROW LEVEL SECURITY;
CREATE POLICY network_reservations_tenant_scope ON network_reservations
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY network_reservations_operator_scope ON network_reservations
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY network_reservations_platform_bypass ON network_reservations
    USING (current_setting('app.platform_bypass', true) = 'true');

-- network_health_events is the append-only telemetry/incident stream --
-- "network-health events" in the approved scope. enterprise_tenant_id is
-- nullable: a provisioning confirmation/failure is bound to one specific
-- reservation (and therefore one tenant), but an operator can also report a
-- broader network-health signal (e.g. "this network_capability is
-- degraded") with no single reservation or tenant to attribute it to; RLS's
-- tenant-scope policy simply never matches a NULL enterprise_tenant_id, so
-- such events are correctly invisible to any tenant.
CREATE TABLE network_health_events (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id            UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    enterprise_tenant_id   UUID REFERENCES enterprise_tenants(id),
    network_reservation_id UUID REFERENCES network_reservations(id) ON DELETE CASCADE,
    event_type             TEXT NOT NULL,
    severity                TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    detail                   JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at              TIMESTAMPTZ NOT NULL,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_network_health_events_operator ON network_health_events(operator_id, occurred_at DESC);
CREATE INDEX idx_network_health_events_reservation ON network_health_events(network_reservation_id);

ALTER TABLE network_health_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE network_health_events FORCE ROW LEVEL SECURITY;
CREATE POLICY network_health_events_operator_scope ON network_health_events
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY network_health_events_tenant_scope ON network_health_events
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY network_health_events_platform_bypass ON network_health_events
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE FUNCTION network_health_events_deny_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'network_health_events is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER network_health_events_no_update
    BEFORE UPDATE ON network_health_events
    FOR EACH ROW EXECUTE FUNCTION network_health_events_deny_mutation();

CREATE TRIGGER network_health_events_no_delete
    BEFORE DELETE ON network_health_events
    FOR EACH ROW EXECUTE FUNCTION network_health_events_deny_mutation();

-- Milestone 6/7 widened control_messages.message_type generically rather
-- than one enum value per action; this migration does the same for
-- network-service provisioning -- 'network_service_provision' (to_agent,
-- payload discriminated by the reservation it provisions) and
-- 'network_service_provision_result' (from_agent, the signed confirmation
-- or failure that becomes a network_health_event).
ALTER TABLE control_messages DROP CONSTRAINT control_messages_message_type_check;
ALTER TABLE control_messages ADD CONSTRAINT control_messages_message_type_check
    CHECK (message_type IN (
        'deployment_plan_validate', 'deployment_plan_validation_result',
        'deployment_command', 'deployment_command_result',
        'network_service_provision', 'network_service_provision_result'
    ));
