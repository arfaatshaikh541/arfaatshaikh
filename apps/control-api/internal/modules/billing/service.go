package billing

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/audit"
	"gridkeep/control-api/internal/platform/billingprovider"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
	"gridkeep/control-api/internal/platform/pki"
)

// signedAtWindow bounds how far AgentReportUsage's claimed signing time may
// drift from the server's clock -- the same replay-protection window every
// other machine-authenticated report in this codebase uses (duplicated
// rather than shared, per this codebase's established convention).
const signedAtWindow = 5 * time.Minute

var (
	ErrPriceBookNotFound       = errors.New("price book not found")
	ErrPriceBookNotDraft       = errors.New("price book is not in draft status")
	ErrBudgetNotFound          = errors.New("budget not found or already archived")
	ErrInvoiceNotFound         = errors.New("invoice not found")
	ErrSettlementNotFound      = errors.New("settlement record not found")
	ErrSettlementNotPending    = errors.New("settlement record is not pending")
	ErrDisputeNotFound         = errors.New("billing dispute not found")
	ErrDisputeNotOpen          = errors.New("billing dispute is not open or under review")
	ErrNoActivePriceBook       = errors.New("no active price book for this operator")
	ErrUnknownUsageMetric      = errors.New("unknown usage metric key")
	ErrNoUsageForPeriod        = errors.New("no aggregated usage for this tenant in the requested period")
	ErrAdjustmentTargetMissing = errors.New("exactly one of invoice_id or settlement_id is required")
	ErrNoTrustedCertificate    = errors.New("no currently valid certificate for this cluster agent")
	ErrInvalidSignature        = errors.New("signature verification failed")
	ErrReplay                  = errors.New("nonce already used or signing time outside the acceptance window")
	ErrUsageReferenceInvalid   = errors.New("exactly one of deployment_id/capacity_reservation_id/network_reservation_id is required")
	ErrUsageReferenceMismatch  = errors.New("referenced resource does not belong to this cluster agent's operator")
)

type Service struct {
	store    *dbpkg.Store
	provider billingprovider.Provider
}

func NewService(store *dbpkg.Store, provider billingprovider.Provider) *Service {
	return &Service{store: store, provider: provider}
}

func actorFromContext(ctx context.Context) uuid.UUID {
	if authUser, ok := httpserver.AuthUser(ctx); ok {
		return authUser.UserID
	}
	return uuid.Nil
}

// ---------------------------------------------------------------------
// Usage metrics (static catalog)
// ---------------------------------------------------------------------

func (s *Service) ListUsageMetrics(ctx context.Context) ([]UsageMetric, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listUsageMetrics(ctx, scopedTx.Tx)
}

// ---------------------------------------------------------------------
// Usage events (read-only from the session-authenticated side; writes only
// ever happen via AgentReportUsage below)
// ---------------------------------------------------------------------

func (s *Service) ListUsageEvents(ctx context.Context) ([]UsageEvent, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listUsageEventsForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) ListOperatorUsageEvents(ctx context.Context) ([]UsageEvent, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listUsageEventsForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

// ---------------------------------------------------------------------
// Usage aggregation (on demand -- no live scheduler in this codebase, the
// same "reclaimExpired runs at the top of every call" precedent Milestone 5
// established and every later milestone reused)
// ---------------------------------------------------------------------

func (s *Service) AggregateUsage(ctx context.Context, tenantID uuid.UUID, periodStart, periodEnd time.Time) ([]UsageAggregation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return aggregateUsage(ctx, scopedTx.Tx, *scope.OperatorID, tenantID, periodStart, periodEnd)
}

func (s *Service) ListUsageAggregations(ctx context.Context) ([]UsageAggregation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listUsageAggregationsForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) ListOperatorUsageAggregations(ctx context.Context) ([]UsageAggregation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listUsageAggregationsForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

// ---------------------------------------------------------------------
// Pricing (operator-scoped)
// ---------------------------------------------------------------------

func (s *Service) CreatePriceBook(ctx context.Context, in CreatePriceBookInput) (PriceBook, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	pb, err := createPriceBook(ctx, scopedTx.Tx, scope.OperatorID, actor, in)
	if err != nil {
		return PriceBook{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "price_books.created", TargetType: "price_book", TargetID: &pb.ID,
		Evidence: map[string]any{"version": pb.Version, "currency": pb.Currency, "rule_count": len(pb.Rules)},
	}); err != nil {
		return PriceBook{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return PriceBook{}, err
	}
	return pb, nil
}

func (s *Service) ListPriceBooks(ctx context.Context) ([]PriceBook, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listPriceBooksForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) GetPriceBook(ctx context.Context, id uuid.UUID) (PriceBook, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	pb, exists, err := getPriceBookByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return PriceBook{}, err
	}
	if !exists {
		return PriceBook{}, ErrPriceBookNotFound
	}
	return pb, nil
}

func (s *Service) ActivatePriceBook(ctx context.Context, id uuid.UUID) (PriceBook, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getPriceBookByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id); err != nil {
		return PriceBook{}, err
	} else if !exists {
		return PriceBook{}, ErrPriceBookNotFound
	}
	ok, err := activatePriceBook(ctx, scopedTx.Tx, scope.OperatorID, id)
	if err != nil {
		return PriceBook{}, err
	}
	if !ok {
		return PriceBook{}, ErrPriceBookNotDraft
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "price_books.activated", TargetType: "price_book", TargetID: &id,
	}); err != nil {
		return PriceBook{}, err
	}
	pb, exists, err := getPriceBookByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return PriceBook{}, err
	}
	if !exists {
		return PriceBook{}, ErrPriceBookNotFound
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return PriceBook{}, err
	}
	return pb, nil
}

// ---------------------------------------------------------------------
// Quotes (enterprise-scoped, ad-hoc estimate)
// ---------------------------------------------------------------------

// CreateQuote computes every line item's unit price and amount server-side
// from the chosen operator's currently active price book -- the request
// only ever supplies usage_metric_key/quantity pairs, never a price,
// honouring the approved scope's backend-authoritative pricing requirement.
func (s *Service) CreateQuote(ctx context.Context, operatorID uuid.UUID, items []QuoteLineItemInput) (Quote, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	pb, ok, err := resolveActivePriceBook(ctx, scopedTx.Tx, operatorID)
	if err != nil {
		return Quote{}, err
	}
	if !ok {
		return Quote{}, ErrNoActivePriceBook
	}

	lineItems := make([]quoteLineItem, 0, len(items))
	var total float64
	for _, item := range items {
		unitPrice, found := unitPriceFor(pb.Rules, item.UsageMetricKey)
		if !found {
			return Quote{}, fmt.Errorf("%w: %s", ErrUnknownUsageMetric, item.UsageMetricKey)
		}
		amount := unitPrice * item.Quantity
		lineItems = append(lineItems, quoteLineItem{
			UsageMetricKey: item.UsageMetricKey, Quantity: item.Quantity, UnitPrice: unitPrice, Amount: amount,
		})
		total += amount
	}

	q, err := createQuote(ctx, scopedTx.Tx, *scope.TenantID, operatorID, pb.ID, lineItems, total, pb.Currency, actor)
	if err != nil {
		return Quote{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "quotes.created", TargetType: "quote", TargetID: &q.ID,
		Evidence: map[string]any{"operator_id": operatorID, "price_book_id": pb.ID, "estimated_total": total},
	}); err != nil {
		return Quote{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Quote{}, err
	}
	return q, nil
}

func (s *Service) ListQuotes(ctx context.Context) ([]Quote, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listQuotesForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

// ---------------------------------------------------------------------
// Budgets (enterprise-scoped)
// ---------------------------------------------------------------------

func (s *Service) CreateBudget(ctx context.Context, in CreateBudgetInput) (Budget, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	b, err := createBudget(ctx, scopedTx.Tx, *scope.TenantID, actor, in)
	if err != nil {
		return Budget{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "budgets.created", TargetType: "budget", TargetID: &b.ID,
		Evidence: map[string]any{"threshold_amount": in.ThresholdAmount, "period_days": in.PeriodDays, "hard_limit": in.HardLimit},
	}); err != nil {
		return Budget{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Budget{}, err
	}
	return b, nil
}

func (s *Service) ListBudgets(ctx context.Context) ([]Budget, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listBudgetsForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) ArchiveBudget(ctx context.Context, id uuid.UUID) error {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getBudgetByIDTenant(ctx, scopedTx.Tx, *scope.TenantID, id); err != nil {
		return err
	} else if !exists {
		return ErrBudgetNotFound
	}
	ok, err := archiveBudget(ctx, scopedTx.Tx, id)
	if err != nil {
		return err
	}
	if !ok {
		return ErrBudgetNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "budgets.archived", TargetType: "budget", TargetID: &id,
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

// ---------------------------------------------------------------------
// Invoices (operator-triggered generation; both sides can list/read)
// ---------------------------------------------------------------------

// GenerateInvoice re-aggregates usage for [periodStart, periodEnd) to make
// sure the invoice reflects every usage event landed so far, resolves the
// operator's own active price book, computes every line item and the
// subtotal/tax/total server-side (never accepted from a request body),
// issues the invoice, then syncs it to the configured billing provider and
// records the outcome as a billing_provider_events row -- mirroring how
// internal/modules/attestation records every evidence-provider call.
func (s *Service) GenerateInvoice(ctx context.Context, tenantID uuid.UUID, periodStart, periodEnd time.Time, taxAmount float64) (Invoice, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	operatorID := *scope.OperatorID

	if _, err := aggregateUsage(ctx, scopedTx.Tx, operatorID, tenantID, periodStart, periodEnd); err != nil {
		return Invoice{}, err
	}
	aggregations, err := getUsageAggregationsForPeriod(ctx, scopedTx.Tx, operatorID, tenantID, periodStart, periodEnd)
	if err != nil {
		return Invoice{}, err
	}
	if len(aggregations) == 0 {
		return Invoice{}, ErrNoUsageForPeriod
	}

	pb, ok, err := resolveActivePriceBook(ctx, scopedTx.Tx, operatorID)
	if err != nil {
		return Invoice{}, err
	}
	if !ok {
		return Invoice{}, ErrNoActivePriceBook
	}

	lineItems := make([]quoteLineItem, 0, len(aggregations))
	var subtotal float64
	for _, agg := range aggregations {
		unitPrice, found := unitPriceFor(pb.Rules, agg.UsageMetricKey)
		if !found {
			continue // no price rule for this metric on this operator's active book -- not billed.
		}
		amount := unitPrice * agg.TotalQuantity
		lineItems = append(lineItems, quoteLineItem{
			UsageMetricKey: agg.UsageMetricKey, Quantity: agg.TotalQuantity, UnitPrice: unitPrice, Amount: amount,
		})
		subtotal += amount
	}
	total := subtotal + taxAmount

	inv, err := createInvoice(ctx, scopedTx.Tx, tenantID, operatorID, pb.ID, periodStart, periodEnd, lineItems, subtotal, taxAmount, total, pb.Currency, actor)
	if err != nil {
		return Invoice{}, err
	}

	syncResult, syncErr := s.provider.Sync(ctx, billingprovider.Invoice{ID: inv.ID, Total: inv.Total, Currency: inv.Currency})
	detail := map[string]any{"total": inv.Total, "currency": inv.Currency}
	eventType := "invoice_sync_succeeded"
	var externalRef *string
	if syncErr != nil {
		eventType = "invoice_sync_failed"
		detail["error"] = syncErr.Error()
	} else if syncResult.Synced {
		ref := syncResult.ExternalRef
		externalRef = &ref
		if err := setInvoiceExternalRef(ctx, scopedTx.Tx, inv.ID, ref); err != nil {
			return Invoice{}, err
		}
		inv.ExternalRef = &ref
	}
	if _, err := insertBillingProviderEvent(ctx, scopedTx.Tx, &inv.ID, nil, operatorID, &tenantID, "mock", eventType, externalRef, detail); err != nil {
		return Invoice{}, err
	}

	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "invoices.issued", TargetType: "invoice", TargetID: &inv.ID,
		Evidence: map[string]any{"enterprise_tenant_id": tenantID, "total": inv.Total, "currency": inv.Currency},
	}); err != nil {
		return Invoice{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Invoice{}, err
	}
	return inv, nil
}

func (s *Service) ListInvoices(ctx context.Context) ([]Invoice, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listInvoicesForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) ListOperatorInvoices(ctx context.Context) ([]Invoice, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listInvoicesForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) GetInvoice(ctx context.Context, id uuid.UUID) (Invoice, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	inv, exists, err := getInvoiceByIDTenant(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return Invoice{}, err
	}
	if !exists {
		return Invoice{}, ErrInvoiceNotFound
	}
	return inv, nil
}

func (s *Service) GetOperatorInvoice(ctx context.Context, id uuid.UUID) (Invoice, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	inv, exists, err := getInvoiceByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return Invoice{}, err
	}
	if !exists {
		return Invoice{}, ErrInvoiceNotFound
	}
	return inv, nil
}

func (s *Service) MarkInvoicePaid(ctx context.Context, id uuid.UUID) error {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getInvoiceByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id); err != nil {
		return err
	} else if !exists {
		return ErrInvoiceNotFound
	}
	if err := setInvoiceStatus(ctx, scopedTx.Tx, id, "paid"); err != nil {
		return err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "invoices.marked_paid", TargetType: "invoice", TargetID: &id,
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

func (s *Service) ListBillingProviderEventsForInvoice(ctx context.Context, invoiceID uuid.UUID) ([]BillingProviderEvent, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listBillingProviderEventsForInvoice(ctx, scopedTx.Tx, invoiceID)
}

// ---------------------------------------------------------------------
// Settlements (operator-scoped)
// ---------------------------------------------------------------------

func (s *Service) CreateSettlement(ctx context.Context, periodStart, periodEnd time.Time, platformFeeRate float64) (SettlementRecord, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	operatorID := *scope.OperatorID

	invoices, err := listInvoicesForOperator(ctx, scopedTx.Tx, operatorID)
	if err != nil {
		return SettlementRecord{}, err
	}
	var gross float64
	var invoiceCount int
	var currency string
	for _, inv := range invoices {
		if inv.IssuedAt.Before(periodStart) || !inv.IssuedAt.Before(periodEnd) {
			continue
		}
		if inv.Status != "paid" && inv.Status != "issued" {
			continue
		}
		gross += inv.Total
		invoiceCount++
		currency = inv.Currency
	}
	if currency == "" {
		currency = "USD"
	}
	platformFee := gross * platformFeeRate
	net := gross - platformFee

	rec, err := createSettlement(ctx, scopedTx.Tx, operatorID, periodStart, periodEnd, gross, platformFee, net, currency, invoiceCount, actor)
	if err != nil {
		return SettlementRecord{}, err
	}

	syncResult, syncErr := s.provider.Sync(ctx, billingprovider.Invoice{ID: rec.ID, Total: rec.NetAmount, Currency: rec.Currency})
	detail := map[string]any{"net_amount": rec.NetAmount, "currency": rec.Currency}
	eventType := "settlement_sync_succeeded"
	var externalRef *string
	if syncErr != nil {
		eventType = "settlement_sync_failed"
		detail["error"] = syncErr.Error()
	} else if syncResult.Synced {
		ref := syncResult.ExternalRef
		externalRef = &ref
	}
	if _, err := insertBillingProviderEvent(ctx, scopedTx.Tx, nil, &rec.ID, operatorID, nil, "mock", eventType, externalRef, detail); err != nil {
		return SettlementRecord{}, err
	}

	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "settlements.created", TargetType: "settlement_record", TargetID: &rec.ID,
		Evidence: map[string]any{"gross_amount": gross, "net_amount": net, "invoice_count": invoiceCount},
	}); err != nil {
		return SettlementRecord{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return SettlementRecord{}, err
	}
	return rec, nil
}

func (s *Service) ListSettlements(ctx context.Context) ([]SettlementRecord, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listSettlementsForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) GetSettlement(ctx context.Context, id uuid.UUID) (SettlementRecord, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	rec, exists, err := getSettlementByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return SettlementRecord{}, err
	}
	if !exists {
		return SettlementRecord{}, ErrSettlementNotFound
	}
	return rec, nil
}

func (s *Service) ReconcileSettlement(ctx context.Context, id uuid.UUID) (SettlementRecord, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getSettlementByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id); err != nil {
		return SettlementRecord{}, err
	} else if !exists {
		return SettlementRecord{}, ErrSettlementNotFound
	}
	ok, err := reconcileSettlement(ctx, scopedTx.Tx, id)
	if err != nil {
		return SettlementRecord{}, err
	}
	if !ok {
		return SettlementRecord{}, ErrSettlementNotPending
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "settlements.reconciled", TargetType: "settlement_record", TargetID: &id,
	}); err != nil {
		return SettlementRecord{}, err
	}
	rec, exists, err := getSettlementByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return SettlementRecord{}, err
	}
	if !exists {
		return SettlementRecord{}, ErrSettlementNotFound
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return SettlementRecord{}, err
	}
	return rec, nil
}

func (s *Service) ListBillingProviderEventsForSettlement(ctx context.Context, settlementID uuid.UUID) ([]BillingProviderEvent, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listBillingProviderEventsForSettlement(ctx, scopedTx.Tx, settlementID)
}

// ---------------------------------------------------------------------
// Adjustments (operator-scoped, append-only)
// ---------------------------------------------------------------------

func (s *Service) CreateAdjustment(ctx context.Context, invoiceID, settlementID *uuid.UUID, tenantID *uuid.UUID, amount float64, reason string) (Adjustment, error) {
	if (invoiceID == nil) == (settlementID == nil) {
		return Adjustment{}, ErrAdjustmentTargetMissing
	}
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	operatorID := *scope.OperatorID

	if invoiceID != nil {
		if _, exists, err := getInvoiceByIDOperator(ctx, scopedTx.Tx, operatorID, *invoiceID); err != nil {
			return Adjustment{}, err
		} else if !exists {
			return Adjustment{}, ErrInvoiceNotFound
		}
	}
	if settlementID != nil {
		if _, exists, err := getSettlementByIDOperator(ctx, scopedTx.Tx, operatorID, *settlementID); err != nil {
			return Adjustment{}, err
		} else if !exists {
			return Adjustment{}, ErrSettlementNotFound
		}
	}

	a, err := insertAdjustment(ctx, scopedTx.Tx, invoiceID, settlementID, operatorID, tenantID, amount, reason, actor)
	if err != nil {
		return Adjustment{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "adjustments.created", TargetType: "adjustment", TargetID: &a.ID,
		Evidence: map[string]any{"amount": amount, "reason": reason},
	}); err != nil {
		return Adjustment{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Adjustment{}, err
	}
	return a, nil
}

func (s *Service) ListAdjustmentsForInvoice(ctx context.Context, invoiceID uuid.UUID) ([]Adjustment, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listAdjustmentsForInvoice(ctx, scopedTx.Tx, invoiceID)
}

func (s *Service) ListAdjustmentsForSettlement(ctx context.Context, settlementID uuid.UUID) ([]Adjustment, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listAdjustmentsForSettlement(ctx, scopedTx.Tx, settlementID)
}

// ---------------------------------------------------------------------
// Credit notes (operator-scoped)
// ---------------------------------------------------------------------

func (s *Service) CreateCreditNote(ctx context.Context, invoiceID, tenantID uuid.UUID, amount float64, reason string) (CreditNote, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	operatorID := *scope.OperatorID

	if _, exists, err := getInvoiceByIDOperator(ctx, scopedTx.Tx, operatorID, invoiceID); err != nil {
		return CreditNote{}, err
	} else if !exists {
		return CreditNote{}, ErrInvoiceNotFound
	}

	cn, err := insertCreditNote(ctx, scopedTx.Tx, invoiceID, tenantID, operatorID, amount, reason, actor)
	if err != nil {
		return CreditNote{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "credit_notes.created", TargetType: "credit_note", TargetID: &cn.ID,
		Evidence: map[string]any{"invoice_id": invoiceID, "amount": amount, "reason": reason},
	}); err != nil {
		return CreditNote{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return CreditNote{}, err
	}
	return cn, nil
}

func (s *Service) ListCreditNotes(ctx context.Context) ([]CreditNote, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listCreditNotesForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) ListOperatorCreditNotes(ctx context.Context) ([]CreditNote, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listCreditNotesForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

// ---------------------------------------------------------------------
// Billing disputes (enterprise opens, operator resolves)
// ---------------------------------------------------------------------

func (s *Service) CreateDispute(ctx context.Context, invoiceID uuid.UUID, reason string) (BillingDispute, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	inv, exists, err := getInvoiceByIDTenant(ctx, scopedTx.Tx, tenantID, invoiceID)
	if err != nil {
		return BillingDispute{}, err
	}
	if !exists {
		return BillingDispute{}, ErrInvoiceNotFound
	}

	d, err := createDispute(ctx, scopedTx.Tx, invoiceID, tenantID, inv.OperatorID, reason, actor)
	if err != nil {
		return BillingDispute{}, err
	}
	if err := setInvoiceStatus(ctx, scopedTx.Tx, invoiceID, "disputed"); err != nil {
		return BillingDispute{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "billing_disputes.opened", TargetType: "billing_dispute", TargetID: &d.ID,
		Evidence: map[string]any{"invoice_id": invoiceID, "reason": reason},
	}); err != nil {
		return BillingDispute{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return BillingDispute{}, err
	}
	return d, nil
}

func (s *Service) ListDisputes(ctx context.Context) ([]BillingDispute, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listDisputesForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) ListOperatorDisputes(ctx context.Context) ([]BillingDispute, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listDisputesForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) ResolveDispute(ctx context.Context, id uuid.UUID, status, note string) (BillingDispute, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	operatorID := *scope.OperatorID

	d, exists, err := getDisputeByIDOperator(ctx, scopedTx.Tx, operatorID, id)
	if err != nil {
		return BillingDispute{}, err
	}
	if !exists {
		return BillingDispute{}, ErrDisputeNotFound
	}
	ok, err := resolveDispute(ctx, scopedTx.Tx, id, actor, status, note)
	if err != nil {
		return BillingDispute{}, err
	}
	if !ok {
		return BillingDispute{}, ErrDisputeNotOpen
	}
	if status == "resolved" {
		if err := setInvoiceStatus(ctx, scopedTx.Tx, d.InvoiceID, "issued"); err != nil {
			return BillingDispute{}, err
		}
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "billing_disputes.resolved", TargetType: "billing_dispute", TargetID: &id,
		Evidence: map[string]any{"status": status},
	}); err != nil {
		return BillingDispute{}, err
	}
	updated, exists, err := getDisputeByIDOperator(ctx, scopedTx.Tx, operatorID, id)
	if err != nil {
		return BillingDispute{}, err
	}
	if !exists {
		return BillingDispute{}, ErrDisputeNotFound
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return BillingDispute{}, err
	}
	return updated, nil
}

// ---------------------------------------------------------------------
// Agent-facing (machine-authenticated, no session)
// ---------------------------------------------------------------------

// AgentReportUsage records a cluster agent's signed report of resource
// consumption -- mirrors internal/modules/agents.SubmitCapacitySnapshot's
// shape (a push, not a response to a pending command, so this opens its own
// platform_bypass transaction rather than matching a control message):
// signature verified against the agent's current certificate, exactly one
// of deployment_id/capacity_reservation_id/network_reservation_id resolved
// to its owning operator/tenant (never trusted from the payload directly),
// the resolved operator required to match the reporting agent's own
// operator. Duplicate/replayed reports are rejected at the database level
// by usage_events' UNIQUE (cluster_agent_id, nonce) constraint -- see
// repository.go's ErrDuplicateUsageEvent.
func decodeUsageReportPayload(rawBody []byte) (usageReportPayload, error) {
	var body usageReportPayload
	if err := json.Unmarshal(rawBody, &body); err != nil {
		return usageReportPayload{}, fmt.Errorf("decode usage report: %w", err)
	}
	return body, nil
}

func (s *Service) AgentReportUsage(ctx context.Context, agentID uuid.UUID, rawBody []byte, signatureB64 string) (UsageEvent, error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return UsageEvent{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	agentOperatorID, certPEM, ok, err := clusterAgentIdentity(ctx, tx, agentID)
	if err != nil {
		return UsageEvent{}, err
	}
	if !ok {
		return UsageEvent{}, ErrNoTrustedCertificate
	}
	valid, err := pki.VerifySignature(certPEM, rawBody, signatureB64)
	if err != nil {
		return UsageEvent{}, fmt.Errorf("%w: %v", ErrInvalidSignature, err)
	}
	if !valid {
		return UsageEvent{}, ErrInvalidSignature
	}

	body, err := decodeUsageReportPayload(rawBody)
	if err != nil {
		return UsageEvent{}, err
	}
	signedAt, err := time.Parse(time.RFC3339, body.SignedAt)
	if err != nil {
		return UsageEvent{}, fmt.Errorf("%w: invalid signed_at", ErrReplay)
	}
	if time.Since(signedAt).Abs() > signedAtWindow {
		return UsageEvent{}, ErrReplay
	}
	occurredAt, err := time.Parse(time.RFC3339, body.OccurredAt)
	if err != nil {
		return UsageEvent{}, fmt.Errorf("invalid occurred_at: %w", err)
	}

	var deploymentID, capacityReservationID, networkReservationID *uuid.UUID
	var resolvedOperatorID, resolvedTenantID uuid.UUID
	var resolveErr error
	var resolveOK bool
	switch {
	case body.DeploymentID != nil:
		id, perr := uuid.Parse(*body.DeploymentID)
		if perr != nil {
			return UsageEvent{}, fmt.Errorf("invalid deployment_id: %w", perr)
		}
		deploymentID = &id
		resolvedOperatorID, resolvedTenantID, resolveOK, resolveErr = resolveDeploymentOwnership(ctx, tx, id)
	case body.CapacityReservationID != nil:
		id, perr := uuid.Parse(*body.CapacityReservationID)
		if perr != nil {
			return UsageEvent{}, fmt.Errorf("invalid capacity_reservation_id: %w", perr)
		}
		capacityReservationID = &id
		resolvedOperatorID, resolvedTenantID, resolveOK, resolveErr = resolveCapacityReservationOwnership(ctx, tx, id)
	case body.NetworkReservationID != nil:
		id, perr := uuid.Parse(*body.NetworkReservationID)
		if perr != nil {
			return UsageEvent{}, fmt.Errorf("invalid network_reservation_id: %w", perr)
		}
		networkReservationID = &id
		resolvedOperatorID, resolvedTenantID, resolveOK, resolveErr = resolveNetworkReservationOwnership(ctx, tx, id)
	default:
		return UsageEvent{}, ErrUsageReferenceInvalid
	}
	if resolveErr != nil {
		return UsageEvent{}, resolveErr
	}
	if !resolveOK {
		return UsageEvent{}, ErrUsageReferenceInvalid
	}
	if resolvedOperatorID != agentOperatorID {
		return UsageEvent{}, ErrUsageReferenceMismatch
	}

	event, err := insertUsageEvent(ctx, tx, resolvedOperatorID, resolvedTenantID, agentID, deploymentID, capacityReservationID, networkReservationID,
		body.UsageMetricKey, body.Quantity, occurredAt, body.Nonce, signatureB64)
	if err != nil {
		if errors.Is(err, ErrDuplicateUsageEvent) {
			return UsageEvent{}, ErrDuplicateUsageEvent
		}
		return UsageEvent{}, err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ScopeType: audit.ScopeOperator, ScopeID: &resolvedOperatorID,
		Action: "usage_events.reported", TargetType: "usage_event", TargetID: &event.ID,
		Evidence: map[string]any{"cluster_agent_id": agentID, "usage_metric_key": body.UsageMetricKey, "quantity": body.Quantity},
	}); err != nil {
		return UsageEvent{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return UsageEvent{}, fmt.Errorf("commit usage event: %w", err)
	}
	return event, nil
}
