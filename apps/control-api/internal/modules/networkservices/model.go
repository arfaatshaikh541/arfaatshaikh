// Package networkservices implements Milestone 9's Network and Edge
// Services scope: the marketplace layer on top of Milestone 2's static
// network_capabilities inventory, the same relationship Milestone 5's
// capacity_offers/capacity_reservations has to Milestone 2's
// node_pools/accelerators. An operator publishes a sellable
// NetworkServiceOffer against one of its already-registered network
// capabilities; a tenant requests one (optionally correlated to a specific
// deployment -- "workload-to-network correlation" in the approved scope),
// runs through a deterministic eligibility/ranking evaluation exactly
// mirroring Milestone 5's placement engine's own explainability discipline,
// and a successful request becomes a NetworkReservation. A committed
// reservation is provisioned by sending a signed control message to the
// cluster agent resolved from the offer's network capability's location,
// reusing Milestone 6/7's control_messages channel and its generic
// message-type widening rather than building parallel plumbing.
//
// Deliberately out of scope, per the approved Milestone 9 Build list: dual
// -control approval for network reservations (there is no analogue to
// workload_versions.deployment_approval_required to drive an approval
// requirement here, so a successful request commits immediately -- see
// migration 0030's header comment and docs/project-status.md's Deliberate
// security decisions); a dedicated ConnectivityPolicy sovereignty-policy
// dimension or policy-engine integration; and network usage/billing
// records (metering integration is a later milestone's job).
package networkservices

import (
	"time"

	"github.com/google/uuid"
)

// OfferSummary is the enterprise-facing read model of a
// network_service_offers row -- fetched through that table's
// network_service_offers_enterprise_read RLS policy, so only active offers
// are ever visible here regardless of which operator published them.
type OfferSummary struct {
	ID                     uuid.UUID `json:"id"`
	OperatorID             uuid.UUID `json:"operator_id"`
	RegionID               uuid.UUID `json:"region_id"`
	ServiceClass           string    `json:"service_class"`
	AvailableBandwidthGbps float64   `json:"available_bandwidth_gbps"`
	MaxLatencyMs           *float64  `json:"max_latency_ms,omitempty"`
	PricePerUnitHour       float64   `json:"price_per_unit_hour"`
	Currency               string    `json:"currency"`
}

// NetworkServiceOffer is the operator-facing full read model.
type NetworkServiceOffer struct {
	ID                     uuid.UUID `json:"id"`
	OperatorID             uuid.UUID `json:"operator_id"`
	NetworkCapabilityID    uuid.UUID `json:"network_capability_id"`
	RegionID               uuid.UUID `json:"region_id"`
	ServiceClass           string    `json:"service_class"`
	TotalBandwidthGbps     float64   `json:"total_bandwidth_gbps"`
	AvailableBandwidthGbps float64   `json:"available_bandwidth_gbps"`
	MaxLatencyMs           *float64  `json:"max_latency_ms,omitempty"`
	PricePerUnitHour       float64   `json:"price_per_unit_hour"`
	Currency               string    `json:"currency"`
	Status                 string    `json:"status"`
	CreatedBy              uuid.UUID `json:"created_by"`
	CreatedAt              time.Time `json:"created_at"`
	UpdatedAt              time.Time `json:"updated_at"`
}

type CreateOfferInput struct {
	NetworkCapabilityID uuid.UUID
	ServiceClass        string
	TotalBandwidthGbps  float64
	MaxLatencyMs        *float64
	PricePerUnitHour    float64
	Currency            string
}

type UpdateOfferInput struct {
	AvailableBandwidthGbps *float64
	PricePerUnitHour       *float64
	Status                 *string
}

type NetworkServiceRequest struct {
	ID                    uuid.UUID  `json:"id"`
	EnterpriseTenantID    uuid.UUID  `json:"enterprise_tenant_id"`
	DeploymentID          *uuid.UUID `json:"deployment_id,omitempty"`
	RequiredBandwidthGbps float64    `json:"required_bandwidth_gbps"`
	MaxLatencyMs          *float64   `json:"max_latency_ms,omitempty"`
	ServiceClass          *string    `json:"service_class,omitempty"`
	Simulate              bool       `json:"simulate"`
	Status                string     `json:"status"`
	RequestedBy           uuid.UUID  `json:"requested_by"`
	CreatedAt             time.Time  `json:"created_at"`
	UpdatedAt             time.Time  `json:"updated_at"`
}

type NetworkServiceEvaluation struct {
	ID                      uuid.UUID      `json:"id"`
	NetworkServiceRequestID uuid.UUID      `json:"network_service_request_id"`
	NetworkServiceOfferID   uuid.UUID      `json:"network_service_offer_id"`
	OperatorID              uuid.UUID      `json:"operator_id"`
	RegionID                uuid.UUID      `json:"region_id"`
	ServiceClass            string         `json:"service_class"`
	Decision                string         `json:"decision"`
	Rank                    *int           `json:"rank,omitempty"`
	EstimatedCost           float64        `json:"estimated_cost"`
	ReasonCodes             []string       `json:"reason_codes"`
	Explanation             map[string]any `json:"explanation"`
	CreatedAt               time.Time      `json:"created_at"`
}

type NetworkReservation struct {
	ID                      uuid.UUID  `json:"id"`
	EnterpriseTenantID      uuid.UUID  `json:"enterprise_tenant_id"`
	OperatorID              uuid.UUID  `json:"operator_id"`
	NetworkServiceRequestID uuid.UUID  `json:"network_service_request_id"`
	NetworkServiceOfferID   uuid.UUID  `json:"network_service_offer_id"`
	DeploymentID            *uuid.UUID `json:"deployment_id,omitempty"`
	ClusterAgentID          *uuid.UUID `json:"cluster_agent_id,omitempty"`
	BandwidthGbps           float64    `json:"bandwidth_gbps"`
	PricePerUnitHour        float64    `json:"price_per_unit_hour"`
	EstimatedCost           float64    `json:"estimated_cost"`
	Status                  string     `json:"status"`
	ProvisioningStatus      string     `json:"provisioning_status"`
	RequestedBy             uuid.UUID  `json:"requested_by"`
	CommittedAt             time.Time  `json:"committed_at"`
	ReleasedAt              *time.Time `json:"released_at,omitempty"`
	ReleaseReason           string     `json:"release_reason,omitempty"`
}

type NetworkHealthEvent struct {
	ID                   uuid.UUID      `json:"id"`
	OperatorID           uuid.UUID      `json:"operator_id"`
	EnterpriseTenantID   *uuid.UUID     `json:"enterprise_tenant_id,omitempty"`
	NetworkReservationID *uuid.UUID     `json:"network_reservation_id,omitempty"`
	EventType            string         `json:"event_type"`
	Severity             string         `json:"severity"`
	Detail               map[string]any `json:"detail"`
	OccurredAt           time.Time      `json:"occurred_at"`
	CreatedAt            time.Time      `json:"created_at"`
}

// EvaluateNetworkServiceResult bundles everything one evaluation call
// produces -- the request record, every candidate offer's explained
// evaluation, and (unless simulate=true or nothing could be reserved) the
// reservation that was actually created.
type EvaluateNetworkServiceResult struct {
	Request     NetworkServiceRequest      `json:"request"`
	Evaluations []NetworkServiceEvaluation `json:"evaluations"`
	Reservation *NetworkReservation        `json:"reservation,omitempty"`
}

// networkProvisionPayload is the to_agent control-message payload for both
// actions this package sends against a network reservation -- "action"
// ("provision" or "release") discriminates which one, the same single
// generic message_type ("network_service_provision") for every action
// convention internal/modules/deployments' deploymentCommandPayload
// established, rather than widening migration 0030's message_type CHECK
// constraint again for a second value.
type networkProvisionPayload struct {
	Action        string  `json:"action"`
	ReservationID string  `json:"reservation_id"`
	BandwidthGbps float64 `json:"bandwidth_gbps,omitempty"`
	ServiceClass  string  `json:"service_class,omitempty"`
}

// networkProvisionResult is the from_agent signed response a cluster agent
// posts back -- see AgentReportProvisionResult in service.go.
type networkProvisionResult struct {
	Action        string `json:"action"`
	ReservationID string `json:"reservation_id"`
	Success       bool   `json:"success"`
	Detail        string `json:"detail"`
	Nonce         string `json:"nonce"`
	SignedAt      string `json:"signed_at"`
}
