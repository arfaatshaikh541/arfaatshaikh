package billing

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
)

// MountTenantScoped registers onto a router already nested under
// /api/v1/enterprises/{tenantID} by app.go. Usage/aggregation/invoice/
// credit-note reads and quote creation reuse usage.view/billing.view
// (Milestone 1's own "roles anticipate milestones" seeding -- see
// migration 0035's header comment); budgets are gated by the narrower,
// newly-minted budgets.manage (there is no separate budgets.view -- a
// tenant's own spend budgets are private financial configuration, not a
// broad read); opening a dispute is gated by the newly-minted
// billing.dispute, distinct from merely viewing billing.view.
func MountTenantScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireEnterprisePermission("usage.view")).Get("/usage-metrics", h.ListUsageMetrics)
	r.With(authz.RequireEnterprisePermission("usage.view")).Get("/usage-events", h.ListUsageEvents)
	r.With(authz.RequireEnterprisePermission("usage.view")).Get("/usage-aggregations", h.ListUsageAggregations)

	r.With(authz.RequireEnterprisePermission("billing.view")).Post("/quotes", h.CreateQuote)
	r.With(authz.RequireEnterprisePermission("billing.view")).Get("/quotes", h.ListQuotes)

	r.With(authz.RequireEnterprisePermission("budgets.manage")).Post("/budgets", h.CreateBudget)
	r.With(authz.RequireEnterprisePermission("budgets.manage")).Get("/budgets", h.ListBudgets)
	r.With(authz.RequireEnterprisePermission("budgets.manage")).Post("/budgets/{budgetID}/archive", h.ArchiveBudget)

	r.With(authz.RequireEnterprisePermission("billing.view")).Get("/invoices", h.ListInvoices)
	r.With(authz.RequireEnterprisePermission("billing.view")).Get("/invoices/{invoiceID}", h.GetInvoice)

	r.With(authz.RequireEnterprisePermission("billing.view")).Get("/credit-notes", h.ListCreditNotes)

	r.With(authz.RequireEnterprisePermission("billing.dispute")).Post("/billing-disputes", h.CreateDispute)
	r.With(authz.RequireEnterprisePermission("billing.view")).Get("/billing-disputes", h.ListDisputes)
}

// MountOperatorScoped registers onto a router already nested under
// /api/v1/operators/{operatorID} by app.go. Price book reads are available
// to any operator member (matching this codebase's established "view is
// membership, manage/mutate is a permission" convention); price book
// writes require operator.pricing.manage; usage reads require
// operator.usage.view; invoice/settlement/adjustment/credit-note/dispute
// reads require the already-seeded operator.settlements.view; the
// mutations that actually move money (generating an invoice, creating or
// reconciling a settlement, issuing an adjustment or credit note,
// resolving a dispute) require the newly-minted, narrower
// operator.settlements.manage.
func MountOperatorScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireOperatorMembership()).Get("/usage-metrics", h.ListUsageMetrics)
	r.With(authz.RequireOperatorPermission("operator.usage.view")).Get("/usage-events", h.ListOperatorUsageEvents)
	r.With(authz.RequireOperatorPermission("operator.usage.view")).Post("/usage-aggregations", h.AggregateUsage)
	r.With(authz.RequireOperatorPermission("operator.usage.view")).Get("/usage-aggregations", h.ListOperatorUsageAggregations)

	r.With(authz.RequireOperatorPermission("operator.pricing.manage")).Post("/price-books", h.CreatePriceBook)
	r.With(authz.RequireOperatorMembership()).Get("/price-books", h.ListPriceBooks)
	r.With(authz.RequireOperatorMembership()).Get("/price-books/{priceBookID}", h.GetPriceBook)
	r.With(authz.RequireOperatorPermission("operator.pricing.manage")).Post("/price-books/{priceBookID}/activate", h.ActivatePriceBook)

	r.With(authz.RequireOperatorPermission("operator.settlements.manage")).Post("/invoices", h.GenerateInvoice)
	r.With(authz.RequireOperatorPermission("operator.settlements.view")).Get("/invoices", h.ListOperatorInvoices)
	r.With(authz.RequireOperatorPermission("operator.settlements.view")).Get("/invoices/{invoiceID}", h.GetOperatorInvoice)
	r.With(authz.RequireOperatorPermission("operator.settlements.manage")).Post("/invoices/{invoiceID}/mark-paid", h.MarkInvoicePaid)
	r.With(authz.RequireOperatorPermission("operator.settlements.view")).Get("/invoices/{invoiceID}/provider-events", h.ListBillingProviderEventsForInvoice)
	r.With(authz.RequireOperatorPermission("operator.settlements.view")).Get("/invoices/{invoiceID}/adjustments", h.ListAdjustmentsForInvoice)

	r.With(authz.RequireOperatorPermission("operator.settlements.manage")).Post("/settlements", h.CreateSettlement)
	r.With(authz.RequireOperatorPermission("operator.settlements.manage")).Post("/settlements/for-agreement", h.CreateSettlementForAgreement)
	r.With(authz.RequireOperatorPermission("operator.settlements.view")).Get("/settlements", h.ListSettlements)
	r.With(authz.RequireOperatorPermission("operator.settlements.view")).Get("/settlements/{settlementID}", h.GetSettlement)
	r.With(authz.RequireOperatorPermission("operator.settlements.manage")).Post("/settlements/{settlementID}/reconcile", h.ReconcileSettlement)
	r.With(authz.RequireOperatorPermission("operator.settlements.view")).Get("/settlements/{settlementID}/provider-events", h.ListBillingProviderEventsForSettlement)
	r.With(authz.RequireOperatorPermission("operator.settlements.view")).Get("/settlements/{settlementID}/adjustments", h.ListAdjustmentsForSettlement)

	r.With(authz.RequireOperatorPermission("operator.settlements.manage")).Post("/adjustments", h.CreateAdjustment)

	r.With(authz.RequireOperatorPermission("operator.settlements.manage")).Post("/credit-notes", h.CreateCreditNote)
	r.With(authz.RequireOperatorPermission("operator.settlements.view")).Get("/credit-notes", h.ListOperatorCreditNotes)

	r.With(authz.RequireOperatorPermission("operator.settlements.view")).Get("/billing-disputes", h.ListOperatorDisputes)
	r.With(authz.RequireOperatorPermission("operator.settlements.manage")).Post("/billing-disputes/{disputeID}/resolve", h.ResolveDispute)
}

// MountMachineFacing registers the one route a cluster agent itself calls
// to report signed usage -- no user session, certificate-signature
// authenticated, mirroring internal/modules/agents' capacity-snapshot
// route and internal/modules/networkservices' MountMachineFacing for the
// same reason.
func MountMachineFacing(r chi.Router, h *Handlers) {
	r.Post("/api/v1/cluster-agents/{clusterAgentID}/usage-events", h.AgentReportUsage)
}
