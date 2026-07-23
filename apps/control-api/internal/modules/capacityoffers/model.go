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
	CreatedBy                      uuid.UUID `json:"created_by"`
	CreatedAt                      time.Time `json:"created_at"`
	UpdatedAt                      time.Time `json:"updated_at"`
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
}

type UpdateOfferInput struct {
	AvailableCapacity *int
	PricePerUnitHour  *float64
	Status            *string
}
