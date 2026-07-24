// Package placement is the enterprise-scoped half of Milestone 5's
// Placement and Capacity Engine. It implements the approved architecture's
// 14-step placement order, steps 1-13 (step 14, creating a signed
// deployment plan and actually deploying, is explicitly Milestone 7's job
// -- no cluster agents exist yet to deploy anything to):
//
//  1. reject ineligible targets       -- offer status filter (query-level)
//  2. verify sovereignty              -- policy-engine, every published policy
//  3. verify security requirements    -- confidential computing
//  4. verify commercial eligibility   -- Milestone 12: a private offer with no
//     active grant for the tenant never
//     reaches this loop at all (RLS on
//     capacity_offers already filtered it
//     out); an offer this tenant is
//     eligible to see may also carry a
//     per-tenant price override (a
//     capacity_offer_grants row), applied
//     in step 9 below instead of the
//     offer's own base price
//  5. verify capacity                 -- available_capacity >= quantity
//  6. verify model/runtime compatibility -- accelerator type match
//  7. verify network constraints      -- stub; Milestone 9
//  8. verify failover compatibility   -- stub; a later milestone
//  9. calculate cost                  -- quantity * price_per_unit_hour
//  10. rank eligible targets          -- deterministic: cost, then energy, then id
//  11. present explanation            -- placement_evaluations.explanation
//  12. require approval where configured -- workload_versions.deployment_approval_required
//  13. reserve capacity atomically    -- conditional UPDATE, retried down the rank on contention
//
// Ranking is deliberately a plain, auditable sort -- the approved
// architecture requires every placement decision to be explainable, which
// rules out any ML/LLM-based ranking; "explainable" and "non-deterministic"
// cannot both be true of the same decision.
//
// Milestone 12 adds one more woven-in eligibility check, operator
// availability: an offer whose operator has self-declared it degraded is
// excluded with an explicit OPERATOR_DEGRADED reason code, the same
// deterministic, explained-rejection discipline every other eligibility
// check above already follows -- this is "operator routing"/"degraded-mode
// handling", not a new numbered step of its own (it slots in alongside
// steps 3-8's other eligibility checks).
package placement

import (
	"time"

	"github.com/google/uuid"
)

// OfferSummary is the enterprise-facing read model of a capacity_offers
// row -- fetched through that table's capacity_offers_enterprise_read RLS
// policy, so only active offers are ever visible here regardless of which
// operator published them.
type OfferSummary struct {
	ID                             uuid.UUID `json:"id"`
	OperatorID                     uuid.UUID `json:"operator_id"`
	RegionID                       uuid.UUID `json:"region_id"`
	AcceleratorType                string    `json:"accelerator_type"`
	AvailableCapacity              int       `json:"available_capacity"`
	PricePerUnitHour               float64   `json:"price_per_unit_hour"`
	Currency                       string    `json:"currency"`
	ConfidentialComputingAvailable bool      `json:"confidential_computing_available"`
	EstimatedKWhPerUnitHour        float64   `json:"estimated_kwh_per_unit_hour"`
	Degraded                       bool      `json:"degraded"`
	DegradedReason                 string    `json:"degraded_reason,omitempty"`
}

// AgreementSummary is the enterprise-facing read model of a
// bilateral_agreements row -- fetched through that table's
// bilateral_agreements_tenant_read RLS policy, so a tenant only ever sees
// its own agreements regardless of which operator authored them. A local
// type, not an import of internal/modules/capacityoffers.BilateralAgreement,
// matching this codebase's established "no cross-module Go type imports,
// only cross-module SQL" convention.
type AgreementSummary struct {
	ID              uuid.UUID `json:"id"`
	OperatorID      uuid.UUID `json:"operator_id"`
	Status          string    `json:"status"`
	Currency        string    `json:"currency"`
	PlatformFeeRate float64   `json:"platform_fee_rate"`
	CreatedAt       time.Time `json:"created_at"`
}

type PlacementRequest struct {
	ID                 uuid.UUID `json:"id"`
	EnterpriseTenantID uuid.UUID `json:"enterprise_tenant_id"`
	WorkloadVersionID  uuid.UUID `json:"workload_version_id"`
	Quantity           int       `json:"quantity"`
	Simulate           bool      `json:"simulate"`
	Status             string    `json:"status"`
	RequestedBy        uuid.UUID `json:"requested_by"`
	CreatedAt          time.Time `json:"created_at"`
	UpdatedAt          time.Time `json:"updated_at"`
}

type PlacementEvaluation struct {
	ID                 uuid.UUID      `json:"id"`
	PlacementRequestID uuid.UUID      `json:"placement_request_id"`
	CapacityOfferID    uuid.UUID      `json:"capacity_offer_id"`
	OperatorID         uuid.UUID      `json:"operator_id"`
	RegionID           uuid.UUID      `json:"region_id"`
	AcceleratorType    string         `json:"accelerator_type"`
	Decision           string         `json:"decision"`
	Rank               *int           `json:"rank,omitempty"`
	EstimatedCost      float64        `json:"estimated_cost"`
	EstimatedEnergyKWh float64        `json:"estimated_energy_kwh"`
	ReasonCodes        []string       `json:"reason_codes"`
	Explanation        map[string]any `json:"explanation"`
	CreatedAt          time.Time      `json:"created_at"`
}

type Reservation struct {
	ID                 uuid.UUID  `json:"id"`
	EnterpriseTenantID uuid.UUID  `json:"enterprise_tenant_id"`
	OperatorID         uuid.UUID  `json:"operator_id"`
	PlacementRequestID uuid.UUID  `json:"placement_request_id"`
	CapacityOfferID    uuid.UUID  `json:"capacity_offer_id"`
	Quantity           int        `json:"quantity"`
	PricePerUnitHour   float64    `json:"price_per_unit_hour"`
	EstimatedCost      float64    `json:"estimated_cost"`
	Status             string     `json:"status"`
	ApprovalRequired   bool       `json:"approval_required"`
	RequestedBy        uuid.UUID  `json:"requested_by"`
	ApprovedBy         *uuid.UUID `json:"approved_by,omitempty"`
	HeldAt             time.Time  `json:"held_at"`
	ExpiresAt          time.Time  `json:"expires_at"`
	CommittedAt        *time.Time `json:"committed_at,omitempty"`
	ReleasedAt         *time.Time `json:"released_at,omitempty"`
	ReleaseReason      string     `json:"release_reason,omitempty"`
}

// EvaluatePlacementResult bundles everything one call to EvaluatePlacement
// produces -- the request record, every candidate's explained evaluation,
// and (unless simulate=true or nothing could be secured) the reservation
// that was actually created.
type EvaluatePlacementResult struct {
	Request     PlacementRequest      `json:"request"`
	Evaluations []PlacementEvaluation `json:"evaluations"`
	Reservation *Reservation          `json:"reservation,omitempty"`
}
