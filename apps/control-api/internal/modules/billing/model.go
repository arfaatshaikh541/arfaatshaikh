// Package billing implements Milestone 11's Usage, Billing and Settlement
// scope. SubscriptionPlan/Feature/PlanFeature/EnterpriseSubscription/
// OperatorSubscription (all listed as this milestone's "Entities" in the
// approved architecture) already exist -- migration 0007 (Milestone 1)
// owns them, and this package never touches them. This package's job is
// everything genuinely new: raw usage events, signed usage ingestion,
// usage aggregation, metered pricing, ad-hoc quotes, budgets, invoices,
// operator settlements, reconciliation, disputes, and a billing-provider
// sync integration.
//
// Two of the approved "Entities" are deliberately folded rather than built
// as separate concepts here -- see migration 0034's header comment for the
// full reasoning: ReservationEstimate is not a new table (capacity/network
// reservations already carry their own estimated_cost); BillingEvent and
// WebhookEvent fold into one billing_provider_events table.
//
// Pricing is backend-authoritative throughout: every quote and invoice
// line item is computed server-side from the price book active at
// computation/issue time, never accepted from a request body. Usage
// aggregation and invoice generation have no live scheduler in this
// codebase -- both run on demand, the same "reclaimExpired runs at the top
// of every call" precedent Milestone 5 established and Milestone 10's SLO
// evaluation already reused.
package billing

import (
	"time"

	"github.com/google/uuid"
)

// ---------------------------------------------------------------------
// Usage
// ---------------------------------------------------------------------

type UsageMetric struct {
	Key         string `json:"key"`
	Name        string `json:"name"`
	Unit        string `json:"unit"`
	Description string `json:"description"`
}

type UsageEvent struct {
	ID                    uuid.UUID  `json:"id"`
	OperatorID            uuid.UUID  `json:"operator_id"`
	EnterpriseTenantID    uuid.UUID  `json:"enterprise_tenant_id"`
	ClusterAgentID        uuid.UUID  `json:"cluster_agent_id"`
	DeploymentID          *uuid.UUID `json:"deployment_id,omitempty"`
	CapacityReservationID *uuid.UUID `json:"capacity_reservation_id,omitempty"`
	NetworkReservationID  *uuid.UUID `json:"network_reservation_id,omitempty"`
	UsageMetricKey        string     `json:"usage_metric_key"`
	Quantity              float64    `json:"quantity"`
	OccurredAt            time.Time  `json:"occurred_at"`
	CreatedAt             time.Time  `json:"created_at"`
}

type UsageAggregation struct {
	ID                 uuid.UUID `json:"id"`
	OperatorID         uuid.UUID `json:"operator_id"`
	EnterpriseTenantID uuid.UUID `json:"enterprise_tenant_id"`
	UsageMetricKey     string    `json:"usage_metric_key"`
	PeriodStart        time.Time `json:"period_start"`
	PeriodEnd          time.Time `json:"period_end"`
	TotalQuantity      float64   `json:"total_quantity"`
	SourceEventCount   int       `json:"source_event_count"`
	ComputedAt         time.Time `json:"computed_at"`
}

// usageReportPayload is the to_agent-signed body a cluster agent submits --
// exactly one of DeploymentID/CapacityReservationID/NetworkReservationID
// must be set (enforced in the service layer, not a DB CHECK -- see
// service.go's doc comment on AgentReportUsage); operator_id/
// enterprise_tenant_id are never accepted from this payload at all, only
// ever resolved server-side from whichever reference is set, the same
// "never trust tenant_id/operator_id from a caller when it can be resolved
// from an already-authenticated reference" discipline this codebase has
// applied since Milestone 1, extended here to a machine caller.
type usageReportPayload struct {
	DeploymentID          *string `json:"deployment_id,omitempty"`
	CapacityReservationID *string `json:"capacity_reservation_id,omitempty"`
	NetworkReservationID  *string `json:"network_reservation_id,omitempty"`
	UsageMetricKey        string  `json:"usage_metric_key"`
	Quantity              float64 `json:"quantity"`
	OccurredAt            string  `json:"occurred_at"`
	Nonce                 string  `json:"nonce"`
	SignedAt              string  `json:"signed_at"`
}

// ---------------------------------------------------------------------
// Pricing
// ---------------------------------------------------------------------

type PriceRule struct {
	ID             uuid.UUID `json:"id"`
	PriceBookID    uuid.UUID `json:"price_book_id"`
	UsageMetricKey string    `json:"usage_metric_key"`
	UnitPrice      float64   `json:"unit_price"`
}

type PriceRuleInput struct {
	UsageMetricKey string
	UnitPrice      float64
}

type PriceBook struct {
	ID          uuid.UUID   `json:"id"`
	OperatorID  *uuid.UUID  `json:"operator_id,omitempty"`
	Version     int         `json:"version"`
	Currency    string      `json:"currency"`
	Status      string      `json:"status"`
	CreatedBy   uuid.UUID   `json:"created_by"`
	CreatedAt   time.Time   `json:"created_at"`
	ActivatedAt *time.Time  `json:"activated_at,omitempty"`
	Rules       []PriceRule `json:"rules,omitempty"`
}

type CreatePriceBookInput struct {
	Currency string
	Rules    []PriceRuleInput
}

// ---------------------------------------------------------------------
// Quotes (ad-hoc estimate, never tied to a reservation -- see package doc)
// ---------------------------------------------------------------------

type QuoteLineItemInput struct {
	UsageMetricKey string
	Quantity       float64
}

type quoteLineItem struct {
	UsageMetricKey string  `json:"usage_metric_key"`
	Quantity       float64 `json:"quantity"`
	UnitPrice      float64 `json:"unit_price"`
	Amount         float64 `json:"amount"`
}

type Quote struct {
	ID                 uuid.UUID       `json:"id"`
	EnterpriseTenantID uuid.UUID       `json:"enterprise_tenant_id"`
	OperatorID         uuid.UUID       `json:"operator_id"`
	PriceBookID        uuid.UUID       `json:"price_book_id"`
	LineItems          []quoteLineItem `json:"line_items"`
	EstimatedTotal     float64         `json:"estimated_total"`
	Currency           string          `json:"currency"`
	RequestedBy        uuid.UUID       `json:"requested_by"`
	CreatedAt          time.Time       `json:"created_at"`
}

// ---------------------------------------------------------------------
// Budgets
// ---------------------------------------------------------------------

type Budget struct {
	ID                 uuid.UUID `json:"id"`
	EnterpriseTenantID uuid.UUID `json:"enterprise_tenant_id"`
	Name               string    `json:"name"`
	PeriodDays         int       `json:"period_days"`
	ThresholdAmount    float64   `json:"threshold_amount"`
	Currency           string    `json:"currency"`
	HardLimit          bool      `json:"hard_limit"`
	Status             string    `json:"status"`
	CreatedBy          uuid.UUID `json:"created_by"`
	CreatedAt          time.Time `json:"created_at"`
	UpdatedAt          time.Time `json:"updated_at"`
}

type CreateBudgetInput struct {
	Name            string
	PeriodDays      int
	ThresholdAmount float64
	Currency        string
	HardLimit       bool
}

// ---------------------------------------------------------------------
// Invoices, settlements, adjustments, credit notes, disputes
// ---------------------------------------------------------------------

type Invoice struct {
	ID                 uuid.UUID       `json:"id"`
	EnterpriseTenantID uuid.UUID       `json:"enterprise_tenant_id"`
	OperatorID         uuid.UUID       `json:"operator_id"`
	PriceBookID        uuid.UUID       `json:"price_book_id"`
	PeriodStart        time.Time       `json:"period_start"`
	PeriodEnd          time.Time       `json:"period_end"`
	LineItems          []quoteLineItem `json:"line_items"`
	Subtotal           float64         `json:"subtotal"`
	TaxAmount          float64         `json:"tax_amount"`
	Total              float64         `json:"total"`
	Currency           string          `json:"currency"`
	Status             string          `json:"status"`
	ExternalRef        *string         `json:"external_ref,omitempty"`
	IssuedBy           uuid.UUID       `json:"issued_by"`
	IssuedAt           time.Time       `json:"issued_at"`
	UpdatedAt          time.Time       `json:"updated_at"`
}

// SettlementRecord's EnterpriseTenantID/BilateralAgreementID are nil for an
// operator-wide settlement (the original Milestone 11 CreateSettlement
// path, still unchanged); both are set for a settlement created against one
// specific bilateral agreement (Milestone 12's CreateSettlementForAgreement),
// which is scoped to that one tenant's invoices and priced at the
// agreement's own contracted platform_fee_rate, never a request-supplied one.
type SettlementRecord struct {
	ID                   uuid.UUID  `json:"id"`
	OperatorID           uuid.UUID  `json:"operator_id"`
	EnterpriseTenantID   *uuid.UUID `json:"enterprise_tenant_id,omitempty"`
	BilateralAgreementID *uuid.UUID `json:"bilateral_agreement_id,omitempty"`
	PeriodStart          time.Time  `json:"period_start"`
	PeriodEnd            time.Time  `json:"period_end"`
	GrossAmount          float64    `json:"gross_amount"`
	PlatformFeeAmount    float64    `json:"platform_fee_amount"`
	NetAmount            float64    `json:"net_amount"`
	Currency             string     `json:"currency"`
	Status               string     `json:"status"`
	InvoiceCount         int        `json:"invoice_count"`
	CreatedBy            uuid.UUID  `json:"created_by"`
	CreatedAt            time.Time  `json:"created_at"`
	ReconciledAt         *time.Time `json:"reconciled_at,omitempty"`
}

type Adjustment struct {
	ID                 uuid.UUID  `json:"id"`
	InvoiceID          *uuid.UUID `json:"invoice_id,omitempty"`
	SettlementID       *uuid.UUID `json:"settlement_id,omitempty"`
	OperatorID         uuid.UUID  `json:"operator_id"`
	EnterpriseTenantID *uuid.UUID `json:"enterprise_tenant_id,omitempty"`
	Amount             float64    `json:"amount"`
	Reason             string     `json:"reason"`
	CreatedBy          uuid.UUID  `json:"created_by"`
	CreatedAt          time.Time  `json:"created_at"`
}

type CreditNote struct {
	ID                 uuid.UUID  `json:"id"`
	InvoiceID          uuid.UUID  `json:"invoice_id"`
	EnterpriseTenantID uuid.UUID  `json:"enterprise_tenant_id"`
	OperatorID         uuid.UUID  `json:"operator_id"`
	Amount             float64    `json:"amount"`
	Reason             string     `json:"reason"`
	Status             string     `json:"status"`
	CreatedBy          uuid.UUID  `json:"created_by"`
	CreatedAt          time.Time  `json:"created_at"`
	AppliedAt          *time.Time `json:"applied_at,omitempty"`
}

type BillingDispute struct {
	ID                 uuid.UUID  `json:"id"`
	InvoiceID          uuid.UUID  `json:"invoice_id"`
	EnterpriseTenantID uuid.UUID  `json:"enterprise_tenant_id"`
	OperatorID         uuid.UUID  `json:"operator_id"`
	Reason             string     `json:"reason"`
	Status             string     `json:"status"`
	ResolutionNote     string     `json:"resolution_note"`
	OpenedBy           uuid.UUID  `json:"opened_by"`
	ResolvedBy         *uuid.UUID `json:"resolved_by,omitempty"`
	OpenedAt           time.Time  `json:"opened_at"`
	ResolvedAt         *time.Time `json:"resolved_at,omitempty"`
}

type BillingProviderEvent struct {
	ID           uuid.UUID      `json:"id"`
	InvoiceID    *uuid.UUID     `json:"invoice_id,omitempty"`
	SettlementID *uuid.UUID     `json:"settlement_id,omitempty"`
	ProviderType string         `json:"provider_type"`
	EventType    string         `json:"event_type"`
	ExternalRef  *string        `json:"external_ref,omitempty"`
	Detail       map[string]any `json:"detail"`
	OccurredAt   time.Time      `json:"occurred_at"`
}
