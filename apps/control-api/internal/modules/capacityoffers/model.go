// Package capacityoffers is the operator-scoped half of Milestone 5's
// Placement and Capacity Engine: operators publish, price, and withdraw
// sellable capacity against their own clusters, and can see reservations
// enterprises have placed against that capacity. The enterprise-scoped
// half -- browsing offers, evaluating placement, reserving -- is the
// sibling internal/modules/placement package.
package capacityoffers

import (
	"time"

	"github.com/google/uuid"
)

type CapacityOffer struct {
	ID                             uuid.UUID `json:"id"`
	OperatorID                     uuid.UUID `json:"operator_id"`
	ClusterID                      uuid.UUID `json:"cluster_id"`
	RegionID                       uuid.UUID `json:"region_id"`
	AcceleratorType                string    `json:"accelerator_type"`
	TotalCapacity                  int       `json:"total_capacity"`
	AvailableCapacity              int       `json:"available_capacity"`
	PricePerUnitHour               float64   `json:"price_per_unit_hour"`
	Currency                       string    `json:"currency"`
	ConfidentialComputingAvailable bool      `json:"confidential_computing_available"`
	EstimatedKWhPerUnitHour        float64   `json:"estimated_kwh_per_unit_hour"`
	Status                         string    `json:"status"`
	Visibility                     string    `json:"visibility"`
	Degraded                       bool      `json:"degraded"`
	DegradedReason                 string    `json:"degraded_reason"`
	CreatedBy                      uuid.UUID `json:"created_by"`
	CreatedAt                      time.Time `json:"created_at"`
	UpdatedAt                      time.Time `json:"updated_at"`
}

// BilateralAgreement is the commercial relationship an operator establishes
// with one specific enterprise tenant -- Milestone 12's Federated Capacity
// Exchange "bilateral agreements" and "settlement contracts" requirements
// in one row (see migration 0036's header comment for why they are the same
// table). PlatformFeeRate/Currency are the terms
// internal/modules/billing.CreateSettlementForAgreement reads server-side.
type BilateralAgreement struct {
	ID                      uuid.UUID  `json:"id"`
	OperatorID              uuid.UUID  `json:"operator_id"`
	EnterpriseTenantID      uuid.UUID  `json:"enterprise_tenant_id"`
	Status                  string     `json:"status"`
	Currency                string     `json:"currency"`
	PlatformFeeRate         float64    `json:"platform_fee_rate"`
	MinimumCommitmentHours  *int       `json:"minimum_commitment_hours,omitempty"`
	MinimumCommitmentAmount *float64   `json:"minimum_commitment_amount,omitempty"`
	Notes                   string     `json:"notes"`
	CreatedBy               uuid.UUID  `json:"created_by"`
	CreatedAt               time.Time  `json:"created_at"`
	UpdatedAt               time.Time  `json:"updated_at"`
	TerminatesAt            *time.Time `json:"terminates_at,omitempty"`
}

type CreateAgreementInput struct {
	EnterpriseTenantID      uuid.UUID
	Currency                string
	PlatformFeeRate         float64
	MinimumCommitmentHours  *int
	MinimumCommitmentAmount *float64
	Notes                   string
}

// CapacityOfferGrant is the per-tenant "invitation" a private offer needs to
// be visible/reservable at all (see capacity_offers_enterprise_read's RLS
// policy in migration 0036). PricePerUnitHourOverride, when set, is what
// internal/modules/placement.EvaluatePlacement uses instead of the offer's
// own base price for this specific tenant -- Milestone 12's
// "enterprise-specific pricing" requirement.
type CapacityOfferGrant struct {
	ID                       uuid.UUID  `json:"id"`
	CapacityOfferID          uuid.UUID  `json:"capacity_offer_id"`
	OperatorID               uuid.UUID  `json:"operator_id"`
	EnterpriseTenantID       uuid.UUID  `json:"enterprise_tenant_id"`
	BilateralAgreementID     *uuid.UUID `json:"bilateral_agreement_id,omitempty"`
	PricePerUnitHourOverride *float64   `json:"price_per_unit_hour_override,omitempty"`
	Status                   string     `json:"status"`
	CreatedBy                uuid.UUID  `json:"created_by"`
	CreatedAt                time.Time  `json:"created_at"`
}

type CreateGrantInput struct {
	EnterpriseTenantID       uuid.UUID
	BilateralAgreementID     *uuid.UUID
	PricePerUnitHourOverride *float64
}

// Reservation is the operator-side read model of a capacity_reservations
// row -- the same table the placement package writes to, visible here
// through capacity_reservations' operator-scope RLS policy so operator
// staff can see what has been held/committed against their own capacity
// without needing any cross-module service call.
type Reservation struct {
	ID                 uuid.UUID  `json:"id"`
	EnterpriseTenantID uuid.UUID  `json:"enterprise_tenant_id"`
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
}

type CreateOfferInput struct {
	ClusterID                      uuid.UUID
	AcceleratorType                string
	TotalCapacity                  int
	PricePerUnitHour               float64
	Currency                       string
	ConfidentialComputingAvailable bool
	EstimatedKWhPerUnitHour        float64
	Visibility                     string
}

type UpdateOfferInput struct {
	AvailableCapacity *int
	PricePerUnitHour  *float64
	Status            *string
	Visibility        *string
	Degraded          *bool
	DegradedReason    *string
}
