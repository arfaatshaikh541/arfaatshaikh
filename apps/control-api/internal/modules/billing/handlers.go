package billing

import (
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"gridkeep/control-api/internal/platform/apierror"
)

type Handlers struct {
	svc    *Service
	logger *slog.Logger
}

func NewHandlers(svc *Service, logger *slog.Logger) *Handlers {
	return &Handlers{svc: svc, logger: logger}
}

func decodeJSON(r *http.Request, dst any) error {
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	return dec.Decode(dst)
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeServiceError(w http.ResponseWriter, r *http.Request, logger *slog.Logger, err error) {
	switch {
	case errors.Is(err, ErrPriceBookNotFound), errors.Is(err, ErrBudgetNotFound), errors.Is(err, ErrInvoiceNotFound),
		errors.Is(err, ErrSettlementNotFound), errors.Is(err, ErrDisputeNotFound):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusNotFound, apierror.CodeNotFound, err.Error()))
	case errors.Is(err, ErrPriceBookNotDraft), errors.Is(err, ErrSettlementNotPending), errors.Is(err, ErrDisputeNotOpen),
		errors.Is(err, ErrNoActivePriceBook), errors.Is(err, ErrNoUsageForPeriod), errors.Is(err, ErrUnknownUsageMetric),
		errors.Is(err, ErrDuplicateUsageEvent):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	case errors.Is(err, ErrAdjustmentTargetMissing), errors.Is(err, ErrUsageReferenceInvalid), errors.Is(err, ErrReplay):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, err.Error()))
	case errors.Is(err, ErrNoTrustedCertificate), errors.Is(err, ErrInvalidSignature), errors.Is(err, ErrUsageReferenceMismatch):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusUnauthorized, apierror.CodeUnauthenticated, err.Error()))
	default:
		apierror.WriteJSON(w, r, logger, apierror.Wrap(500, apierror.CodeInternal, "billing operation failed", err))
	}
}

func parseTimeQuery(s string) (time.Time, error) {
	return time.Parse(time.RFC3339, s)
}

// ---------------------------------------------------------------------
// Usage metrics, usage events, usage aggregation
// ---------------------------------------------------------------------

func (h *Handlers) ListUsageMetrics(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListUsageMetrics(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list usage metrics", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListUsageEvents(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListUsageEvents(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list usage events", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListOperatorUsageEvents(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListOperatorUsageEvents(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list usage events", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type aggregateUsageRequest struct {
	EnterpriseTenantID string `json:"enterprise_tenant_id"`
	PeriodStart        string `json:"period_start"`
	PeriodEnd          string `json:"period_end"`
}

func (h *Handlers) AggregateUsage(w http.ResponseWriter, r *http.Request) {
	var req aggregateUsageRequest
	if err := decodeJSON(r, &req); err != nil || req.EnterpriseTenantID == "" || req.PeriodStart == "" || req.PeriodEnd == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	tenantID, err := uuid.Parse(req.EnterpriseTenantID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	periodStart, err := parseTimeQuery(req.PeriodStart)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	periodEnd, err := parseTimeQuery(req.PeriodEnd)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.AggregateUsage(r.Context(), tenantID, periodStart, periodEnd)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListUsageAggregations(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListUsageAggregations(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list usage aggregations", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListOperatorUsageAggregations(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListOperatorUsageAggregations(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list usage aggregations", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// Pricing
// ---------------------------------------------------------------------

type priceRuleRequest struct {
	UsageMetricKey string  `json:"usage_metric_key"`
	UnitPrice      float64 `json:"unit_price"`
}

type createPriceBookRequest struct {
	Currency string             `json:"currency"`
	Rules    []priceRuleRequest `json:"rules"`
}

func (h *Handlers) CreatePriceBook(w http.ResponseWriter, r *http.Request) {
	var req createPriceBookRequest
	if err := decodeJSON(r, &req); err != nil || req.Currency == "" || len(req.Rules) == 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	rules := make([]PriceRuleInput, 0, len(req.Rules))
	for _, rr := range req.Rules {
		if rr.UsageMetricKey == "" || rr.UnitPrice < 0 {
			apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
			return
		}
		rules = append(rules, PriceRuleInput(rr))
	}
	pb, err := h.svc.CreatePriceBook(r.Context(), CreatePriceBookInput{Currency: req.Currency, Rules: rules})
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, pb)
}

func (h *Handlers) ListPriceBooks(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListPriceBooks(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list price books", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func priceBookIDParam(r *http.Request) (uuid.UUID, error) {
	return uuid.Parse(chi.URLParam(r, "priceBookID"))
}

func (h *Handlers) GetPriceBook(w http.ResponseWriter, r *http.Request) {
	id, err := priceBookIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	pb, err := h.svc.GetPriceBook(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, pb)
}

func (h *Handlers) ActivatePriceBook(w http.ResponseWriter, r *http.Request) {
	id, err := priceBookIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	pb, err := h.svc.ActivatePriceBook(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, pb)
}

// ---------------------------------------------------------------------
// Quotes
// ---------------------------------------------------------------------

type quoteLineItemRequest struct {
	UsageMetricKey string  `json:"usage_metric_key"`
	Quantity       float64 `json:"quantity"`
}

type createQuoteRequest struct {
	OperatorID string                 `json:"operator_id"`
	Items      []quoteLineItemRequest `json:"items"`
}

func (h *Handlers) CreateQuote(w http.ResponseWriter, r *http.Request) {
	var req createQuoteRequest
	if err := decodeJSON(r, &req); err != nil || req.OperatorID == "" || len(req.Items) == 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	operatorID, err := uuid.Parse(req.OperatorID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	items := make([]QuoteLineItemInput, 0, len(req.Items))
	for _, it := range req.Items {
		if it.UsageMetricKey == "" || it.Quantity < 0 {
			apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
			return
		}
		items = append(items, QuoteLineItemInput(it))
	}
	q, err := h.svc.CreateQuote(r.Context(), operatorID, items)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, q)
}

func (h *Handlers) ListQuotes(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListQuotes(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list quotes", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// Budgets
// ---------------------------------------------------------------------

type createBudgetRequest struct {
	Name            string  `json:"name"`
	PeriodDays      int     `json:"period_days"`
	ThresholdAmount float64 `json:"threshold_amount"`
	Currency        string  `json:"currency"`
	HardLimit       bool    `json:"hard_limit"`
}

func (h *Handlers) CreateBudget(w http.ResponseWriter, r *http.Request) {
	var req createBudgetRequest
	if err := decodeJSON(r, &req); err != nil || req.Name == "" || req.PeriodDays <= 0 || req.ThresholdAmount <= 0 || req.Currency == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	b, err := h.svc.CreateBudget(r.Context(), CreateBudgetInput(req))
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, b)
}

func (h *Handlers) ListBudgets(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListBudgets(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list budgets", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ArchiveBudget(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "budgetID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.ArchiveBudget(r.Context(), id); err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "archived"})
}

// ---------------------------------------------------------------------
// Invoices
// ---------------------------------------------------------------------

type generateInvoiceRequest struct {
	EnterpriseTenantID string  `json:"enterprise_tenant_id"`
	PeriodStart        string  `json:"period_start"`
	PeriodEnd          string  `json:"period_end"`
	TaxAmount          float64 `json:"tax_amount"`
}

func (h *Handlers) GenerateInvoice(w http.ResponseWriter, r *http.Request) {
	var req generateInvoiceRequest
	if err := decodeJSON(r, &req); err != nil || req.EnterpriseTenantID == "" || req.PeriodStart == "" || req.PeriodEnd == "" || req.TaxAmount < 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	tenantID, err := uuid.Parse(req.EnterpriseTenantID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	periodStart, err := parseTimeQuery(req.PeriodStart)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	periodEnd, err := parseTimeQuery(req.PeriodEnd)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	inv, err := h.svc.GenerateInvoice(r.Context(), tenantID, periodStart, periodEnd, req.TaxAmount)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, inv)
}

func (h *Handlers) ListInvoices(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListInvoices(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list invoices", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListOperatorInvoices(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListOperatorInvoices(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list invoices", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func invoiceIDParam(r *http.Request) (uuid.UUID, error) {
	return uuid.Parse(chi.URLParam(r, "invoiceID"))
}

func (h *Handlers) GetInvoice(w http.ResponseWriter, r *http.Request) {
	id, err := invoiceIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	inv, err := h.svc.GetInvoice(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, inv)
}

func (h *Handlers) GetOperatorInvoice(w http.ResponseWriter, r *http.Request) {
	id, err := invoiceIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	inv, err := h.svc.GetOperatorInvoice(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, inv)
}

func (h *Handlers) MarkInvoicePaid(w http.ResponseWriter, r *http.Request) {
	id, err := invoiceIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.MarkInvoicePaid(r.Context(), id); err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "paid"})
}

func (h *Handlers) ListBillingProviderEventsForInvoice(w http.ResponseWriter, r *http.Request) {
	id, err := invoiceIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListBillingProviderEventsForInvoice(r.Context(), id)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list billing provider events", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// Settlements
// ---------------------------------------------------------------------

type createSettlementRequest struct {
	PeriodStart     string  `json:"period_start"`
	PeriodEnd       string  `json:"period_end"`
	PlatformFeeRate float64 `json:"platform_fee_rate"`
}

func (h *Handlers) CreateSettlement(w http.ResponseWriter, r *http.Request) {
	var req createSettlementRequest
	if err := decodeJSON(r, &req); err != nil || req.PeriodStart == "" || req.PeriodEnd == "" || req.PlatformFeeRate < 0 || req.PlatformFeeRate > 1 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	periodStart, err := parseTimeQuery(req.PeriodStart)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	periodEnd, err := parseTimeQuery(req.PeriodEnd)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	rec, err := h.svc.CreateSettlement(r.Context(), periodStart, periodEnd, req.PlatformFeeRate)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, rec)
}

func (h *Handlers) ListSettlements(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListSettlements(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list settlement records", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func settlementIDParam(r *http.Request) (uuid.UUID, error) {
	return uuid.Parse(chi.URLParam(r, "settlementID"))
}

func (h *Handlers) GetSettlement(w http.ResponseWriter, r *http.Request) {
	id, err := settlementIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	rec, err := h.svc.GetSettlement(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, rec)
}

func (h *Handlers) ReconcileSettlement(w http.ResponseWriter, r *http.Request) {
	id, err := settlementIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	rec, err := h.svc.ReconcileSettlement(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, rec)
}

func (h *Handlers) ListBillingProviderEventsForSettlement(w http.ResponseWriter, r *http.Request) {
	id, err := settlementIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListBillingProviderEventsForSettlement(r.Context(), id)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list billing provider events", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// Adjustments
// ---------------------------------------------------------------------

type createAdjustmentRequest struct {
	InvoiceID          *string `json:"invoice_id,omitempty"`
	SettlementID       *string `json:"settlement_id,omitempty"`
	EnterpriseTenantID *string `json:"enterprise_tenant_id,omitempty"`
	Amount             float64 `json:"amount"`
	Reason             string  `json:"reason"`
}

func (h *Handlers) CreateAdjustment(w http.ResponseWriter, r *http.Request) {
	var req createAdjustmentRequest
	if err := decodeJSON(r, &req); err != nil || req.Reason == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var invoiceID, settlementID *uuid.UUID
	var tenantID *uuid.UUID
	if req.InvoiceID != nil {
		id, err := uuid.Parse(*req.InvoiceID)
		if err != nil {
			apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
			return
		}
		invoiceID = &id
	}
	if req.SettlementID != nil {
		id, err := uuid.Parse(*req.SettlementID)
		if err != nil {
			apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
			return
		}
		settlementID = &id
	}
	if req.EnterpriseTenantID != nil {
		id, err := uuid.Parse(*req.EnterpriseTenantID)
		if err != nil {
			apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
			return
		}
		tenantID = &id
	}
	a, err := h.svc.CreateAdjustment(r.Context(), invoiceID, settlementID, tenantID, req.Amount, req.Reason)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, a)
}

func (h *Handlers) ListAdjustmentsForInvoice(w http.ResponseWriter, r *http.Request) {
	id, err := invoiceIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListAdjustmentsForInvoice(r.Context(), id)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list adjustments", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListAdjustmentsForSettlement(w http.ResponseWriter, r *http.Request) {
	id, err := settlementIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListAdjustmentsForSettlement(r.Context(), id)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list adjustments", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// Credit notes
// ---------------------------------------------------------------------

type createCreditNoteRequest struct {
	InvoiceID          string  `json:"invoice_id"`
	EnterpriseTenantID string  `json:"enterprise_tenant_id"`
	Amount             float64 `json:"amount"`
	Reason             string  `json:"reason"`
}

func (h *Handlers) CreateCreditNote(w http.ResponseWriter, r *http.Request) {
	var req createCreditNoteRequest
	if err := decodeJSON(r, &req); err != nil || req.InvoiceID == "" || req.EnterpriseTenantID == "" || req.Amount <= 0 || req.Reason == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	invoiceID, err := uuid.Parse(req.InvoiceID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	tenantID, err := uuid.Parse(req.EnterpriseTenantID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	cn, err := h.svc.CreateCreditNote(r.Context(), invoiceID, tenantID, req.Amount, req.Reason)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, cn)
}

func (h *Handlers) ListCreditNotes(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListCreditNotes(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list credit notes", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListOperatorCreditNotes(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListOperatorCreditNotes(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list credit notes", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// Billing disputes
// ---------------------------------------------------------------------

type createDisputeRequest struct {
	InvoiceID string `json:"invoice_id"`
	Reason    string `json:"reason"`
}

func (h *Handlers) CreateDispute(w http.ResponseWriter, r *http.Request) {
	var req createDisputeRequest
	if err := decodeJSON(r, &req); err != nil || req.InvoiceID == "" || req.Reason == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	invoiceID, err := uuid.Parse(req.InvoiceID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	d, err := h.svc.CreateDispute(r.Context(), invoiceID, req.Reason)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, d)
}

func (h *Handlers) ListDisputes(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListDisputes(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list billing disputes", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListOperatorDisputes(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListOperatorDisputes(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list billing disputes", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type resolveDisputeRequest struct {
	Status         string `json:"status"`
	ResolutionNote string `json:"resolution_note,omitempty"`
}

func (h *Handlers) ResolveDispute(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "disputeID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req resolveDisputeRequest
	if err := decodeJSON(r, &req); err != nil || (req.Status != "resolved" && req.Status != "rejected") {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	d, err := h.svc.ResolveDispute(r.Context(), id, req.Status, req.ResolutionNote)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, d)
}

// ---------------------------------------------------------------------
// Machine-authenticated (no session)
// ---------------------------------------------------------------------

const maxUsageReportBodyBytes = 1 << 16 // 64 KiB, generous for one usage event.

// AgentReportUsage reads the raw request body first (the signature covers
// those exact bytes) and only afterward parses it as JSON -- the same
// discipline every other machine-authenticated report handler in this
// codebase uses.
func (h *Handlers) AgentReportUsage(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "clusterAgentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	signature := r.Header.Get("X-Agent-Signature")
	if signature == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusUnauthorized, apierror.CodeUnauthenticated, "X-Agent-Signature header is required."))
		return
	}
	rawBody, err := io.ReadAll(io.LimitReader(r.Body, maxUsageReportBodyBytes+1))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if len(rawBody) > maxUsageReportBodyBytes {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	probe, err := decodeUsageReportPayload(rawBody)
	if err != nil || probe.UsageMetricKey == "" || probe.Nonce == "" || probe.SignedAt == "" || probe.OccurredAt == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	event, err := h.svc.AgentReportUsage(r.Context(), agentID, rawBody, signature)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, event)
}
