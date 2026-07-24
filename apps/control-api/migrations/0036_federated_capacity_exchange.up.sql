-- Milestone 12: Federated Capacity Exchange.
--
-- The approved architecture's "Entities" list for this milestone
-- (CapacityOffer, OfferVersion, OfferScope, OfferPricing, OfferAvailability,
-- OfferSLA, OfferJurisdiction, OfferSecurityProfile, OfferSettlementRule,
-- Reservation, ReservationHold, ReservationCommit, ReservationRelease,
-- SettlementRecord, SettlementDispute) is overwhelmingly already built:
-- capacity_offers (Milestone 5) already covers OfferPricing/OfferAvailability/
-- OfferSecurityProfile (confidential computing) and, via its region_id FK,
-- OfferJurisdiction; capacity_reservations (Milestone 5) already covers
-- Reservation/ReservationHold/ReservationCommit/ReservationRelease in full
-- (held -> committed -> released, with expiry); settlement_records/
-- billing_disputes (Milestone 11) already cover SettlementRecord/
-- SettlementDispute. OfferVersion and OfferSLA are not built as separate
-- tables -- an offer is mutated in place (price/capacity/status), the same
-- "update in place, not a version chain" choice this codebase already made
-- for every other mutable configuration row (price_books' version bump on
-- create-new-then-supersede is the one deliberate exception, for a very
-- different reason: a price book must never change under an already-issued
-- invoice); OfferSLA has no dedicated schema here because Milestone 5's
-- offers do not commit to a service-level target distinct from what
-- Milestone 10's operator-scoped SLOs already let an operator define against
-- its own infrastructure.
--
-- What is genuinely new this milestone is OfferScope (public vs. private/
-- invitation-only visibility) and the bilateral commercial relationship
-- underneath it -- Milestone 5's own EvaluatePlacement already carries a
-- placeholder comment for this exact gap ("bilateral
-- OperatorEnterpriseAgreement gating is Milestone 12's Federated Capacity
-- Exchange"). bilateral_agreements is that relationship (and doubles as the
-- approved scope's "settlement contract" -- see its own comment below).
-- capacity_offer_grants is the per-tenant eligibility/pricing grant a
-- private offer needs (the "invitation"). Both are new, dual-scope tables
-- (always exactly one operator and one enterprise tenant -- there is no
-- legitimate single-owner case the way an SLO or alert rule has, since a
-- bilateral relationship is inherently between exactly two parties), the
-- same shape invoices/credit_notes/billing_disputes already established in
-- Milestone 11.
--
-- Degraded-mode handling and operator routing are added directly onto
-- capacity_offers (degraded/degraded_reason) rather than a separate table:
-- an operator declaring itself degraded is a state of its own already-
-- published offer, not a new entity, and EvaluatePlacement's eligibility
-- loop is the natural, already-existing place to exclude a degraded offer
-- with an explicit, explained reason code -- the same deterministic,
-- never-AI-driven discipline every other eligibility check in this
-- codebase already follows.

ALTER TABLE capacity_offers
    ADD COLUMN visibility TEXT NOT NULL DEFAULT 'public' CHECK (visibility IN ('public', 'private')),
    ADD COLUMN degraded BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN degraded_reason TEXT NOT NULL DEFAULT '';

-- bilateral_agreements is the commercial relationship an operator
-- establishes with one specific enterprise tenant -- the approved scope's
-- "bilateral agreements" requirement, and also its "settlement contracts"
-- requirement: platform_fee_rate/currency here are the authoritative terms
-- internal/modules/billing.CreateSettlementForAgreement reads server-side
-- rather than trusting a request-supplied rate, tightening Milestone 11's
-- own CreateSettlement (which still accepts an ad-hoc rate for operators
-- with no bilateral agreement covering a settlement). minimum_commitment_*
-- is recorded and surfaced but not enforced -- the same "recorded, not
-- blocking" choice Milestone 11 already made for budgets.hard_limit; see
-- docs/project-status.md's Known Limitations.
CREATE TABLE bilateral_agreements (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id                 UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    enterprise_tenant_id        UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    status                      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'terminated')),
    currency                    TEXT NOT NULL DEFAULT 'USD',
    platform_fee_rate           NUMERIC(6,4) NOT NULL DEFAULT 0 CHECK (platform_fee_rate >= 0 AND platform_fee_rate <= 1),
    minimum_commitment_hours    INT CHECK (minimum_commitment_hours IS NULL OR minimum_commitment_hours > 0),
    minimum_commitment_amount   NUMERIC(14,4) CHECK (minimum_commitment_amount IS NULL OR minimum_commitment_amount > 0),
    notes                       TEXT NOT NULL DEFAULT '',
    created_by                  UUID NOT NULL REFERENCES users(id),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    terminates_at               TIMESTAMPTZ,
    UNIQUE (operator_id, enterprise_tenant_id)
);
CREATE INDEX idx_bilateral_agreements_operator ON bilateral_agreements(operator_id);
CREATE INDEX idx_bilateral_agreements_tenant ON bilateral_agreements(enterprise_tenant_id);

ALTER TABLE bilateral_agreements ENABLE ROW LEVEL SECURITY;
ALTER TABLE bilateral_agreements FORCE ROW LEVEL SECURITY;
CREATE POLICY bilateral_agreements_operator_scope ON bilateral_agreements
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY bilateral_agreements_tenant_read ON bilateral_agreements
    FOR SELECT USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY bilateral_agreements_platform_bypass ON bilateral_agreements
    USING (current_setting('app.platform_bypass', true) = 'true');

-- capacity_offer_grants is the per-tenant "invitation" a private offer
-- needs to be visible/reservable at all -- see capacity_offers_enterprise_read
-- above. bilateral_agreement_id is nullable: a grant can exist as a simple
-- invitation without a full commercial agreement (an operator inviting a
-- prospective customer to see a private offer before any contract is
-- signed), the same "not every relationship needs the heavier row" choice
-- adjustments/billing_provider_events' num_nonnulls=1 constraint expresses
-- for invoice-vs-settlement. price_per_unit_hour_override, when set, is
-- what internal/modules/placement.EvaluatePlacement uses instead of the
-- offer's own base price for this specific tenant -- the approved scope's
-- "enterprise-specific pricing" requirement, computed and applied entirely
-- server-side, never accepted from a placement request.
CREATE TABLE capacity_offer_grants (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capacity_offer_id           UUID NOT NULL REFERENCES capacity_offers(id) ON DELETE CASCADE,
    operator_id                 UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    enterprise_tenant_id        UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    bilateral_agreement_id      UUID REFERENCES bilateral_agreements(id),
    price_per_unit_hour_override NUMERIC(12,4) CHECK (price_per_unit_hour_override IS NULL OR price_per_unit_hour_override >= 0),
    status                      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_by                  UUID NOT NULL REFERENCES users(id),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (capacity_offer_id, enterprise_tenant_id)
);
CREATE INDEX idx_capacity_offer_grants_offer ON capacity_offer_grants(capacity_offer_id);
CREATE INDEX idx_capacity_offer_grants_tenant ON capacity_offer_grants(enterprise_tenant_id);

ALTER TABLE capacity_offer_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE capacity_offer_grants FORCE ROW LEVEL SECURITY;
CREATE POLICY capacity_offer_grants_operator_scope ON capacity_offer_grants
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY capacity_offer_grants_tenant_read ON capacity_offer_grants
    FOR SELECT USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY capacity_offer_grants_platform_bypass ON capacity_offer_grants
    USING (current_setting('app.platform_bypass', true) = 'true');

-- A private offer is only visible to a tenant enterprise that holds an
-- active capacity_offer_grants row for it -- the same "invitation-only"
-- shape network_service_offers_enterprise_read and price_books_enterprise_read
-- already established for their own visibility rules, just conditioned on
-- an explicit per-tenant grant instead of a blanket "any authenticated
-- tenant" or "status = active" check. Replacing rather than widening the
-- existing policy, since a public offer's visibility is unconditional and a
-- private offer's is conditional on a real row existing -- a single policy
-- expresses both without contradiction. Defined here, after
-- capacity_offer_grants exists, since the policy's EXISTS clause references it.
DROP POLICY capacity_offers_enterprise_read ON capacity_offers;
CREATE POLICY capacity_offers_enterprise_read ON capacity_offers
    FOR SELECT
    USING (
        NULLIF(current_setting('app.tenant_id', true), '') IS NOT NULL
        AND status = 'active'
        AND (
            visibility = 'public'
            OR EXISTS (
                SELECT 1 FROM capacity_offer_grants g
                WHERE g.capacity_offer_id = capacity_offers.id
                  AND g.enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                  AND g.status = 'active'
            )
        )
    );

-- settlement_records gains an optional tenant/agreement pairing -- a
-- settlement created against a specific bilateral agreement (via
-- CreateSettlementForAgreement) is scoped to that one tenant's invoices and
-- priced at that agreement's own contracted rate, distinct from Milestone
-- 11's existing operator-wide CreateSettlement (which still works unchanged
-- for operators with no bilateral agreement covering a given customer --
-- both columns stay NULL for that path). Adding a tenant-read policy lets
-- the enterprise verify its own contracted settlement independently of the
-- operator's math -- the approved scope's "no hidden fees" requirement
-- extended to settlement, not just invoicing.
ALTER TABLE settlement_records
    ADD COLUMN enterprise_tenant_id UUID REFERENCES enterprise_tenants(id),
    ADD COLUMN bilateral_agreement_id UUID REFERENCES bilateral_agreements(id);
CREATE INDEX idx_settlement_records_tenant ON settlement_records(enterprise_tenant_id) WHERE enterprise_tenant_id IS NOT NULL;

CREATE POLICY settlement_records_tenant_read ON settlement_records
    FOR SELECT USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
