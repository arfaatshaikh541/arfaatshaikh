package capacityoffers

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"

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
	case errors.Is(err, ErrClusterNotFound):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, err.Error()))
	case errors.Is(err, ErrOfferNotFound), errors.Is(err, ErrAgreementNotFound), errors.Is(err, ErrGrantNotFound):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusNotFound, apierror.CodeNotFound, err.Error()))
	case errors.Is(err, ErrAgreementNotActive):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	case errors.Is(err, ErrGrantAgreementMismatch):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, err.Error()))
	default:
		apierror.WriteJSON(w, r, logger, apierror.Wrap(500, apierror.CodeInternal, "capacity offer operation failed", err))
	}
}

type createOfferRequest struct {
	ClusterID                      string  `json:"cluster_id"`
	AcceleratorType                string  `json:"accelerator_type"`
	TotalCapacity                  int     `json:"total_capacity"`
	PricePerUnitHour               float64 `json:"price_per_unit_hour"`
	Currency                       string  `json:"currency"`
	ConfidentialComputingAvailable bool    `json:"confidential_computing_available"`
	EstimatedKWhPerUnitHour        float64 `json:"estimated_kwh_per_unit_hour"`
	Visibility                     string  `json:"visibility,omitempty"`
}

func (h *Handlers) CreateOffer(w http.ResponseWriter, r *http.Request) {
	var req createOfferRequest
	if err := decodeJSON(r, &req); err != nil || req.TotalCapacity <= 0 || req.PricePerUnitHour < 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	clusterID, err := uuid.Parse(req.ClusterID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	acceleratorType := req.AcceleratorType
	if acceleratorType == "" {
		acceleratorType = "cpu_only"
	}
	currency := req.Currency
	if currency == "" {
		currency = "USD"
	}
	visibility := req.Visibility
	if visibility == "" {
		visibility = "public"
	}
	if visibility != "public" && visibility != "private" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	o, err := h.svc.CreateOffer(r.Context(), CreateOfferInput{
		ClusterID:                      clusterID,
		AcceleratorType:                acceleratorType,
		TotalCapacity:                  req.TotalCapacity,
		PricePerUnitHour:               req.PricePerUnitHour,
		Currency:                       currency,
		ConfidentialComputingAvailable: req.ConfidentialComputingAvailable,
		EstimatedKWhPerUnitHour:        req.EstimatedKWhPerUnitHour,
		Visibility:                     visibility,
	})
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, o)
}

func (h *Handlers) ListOffers(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListOffers(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list capacity offers", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) GetOffer(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "offerID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	o, err := h.svc.GetOffer(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, o)
}

type updateOfferRequest struct {
	AvailableCapacity *int     `json:"available_capacity"`
	PricePerUnitHour  *float64 `json:"price_per_unit_hour"`
	Status            *string  `json:"status"`
	Visibility        *string  `json:"visibility"`
	Degraded          *bool    `json:"degraded"`
	DegradedReason    *string  `json:"degraded_reason"`
}

func (h *Handlers) UpdateOffer(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "offerID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req updateOfferRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if req.Status != nil {
		switch *req.Status {
		case "active", "paused", "withdrawn":
		default:
			apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
			return
		}
	}
	if req.Visibility != nil && *req.Visibility != "public" && *req.Visibility != "private" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	o, err := h.svc.UpdateOffer(r.Context(), id, UpdateOfferInput(req))
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, o)
}

func (h *Handlers) ListReservations(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListReservations(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list capacity reservations", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// Bilateral agreements
// ---------------------------------------------------------------------

type createAgreementRequest struct {
	EnterpriseTenantID      string   `json:"enterprise_tenant_id"`
	Currency                string   `json:"currency"`
	PlatformFeeRate         float64  `json:"platform_fee_rate"`
	MinimumCommitmentHours  *int     `json:"minimum_commitment_hours,omitempty"`
	MinimumCommitmentAmount *float64 `json:"minimum_commitment_amount,omitempty"`
	Notes                   string   `json:"notes,omitempty"`
}

func (h *Handlers) CreateAgreement(w http.ResponseWriter, r *http.Request) {
	var req createAgreementRequest
	if err := decodeJSON(r, &req); err != nil || req.EnterpriseTenantID == "" || req.PlatformFeeRate < 0 || req.PlatformFeeRate > 1 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	tenantID, err := uuid.Parse(req.EnterpriseTenantID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	currency := req.Currency
	if currency == "" {
		currency = "USD"
	}
	a, err := h.svc.CreateAgreement(r.Context(), CreateAgreementInput{
		EnterpriseTenantID: tenantID, Currency: currency, PlatformFeeRate: req.PlatformFeeRate,
		MinimumCommitmentHours: req.MinimumCommitmentHours, MinimumCommitmentAmount: req.MinimumCommitmentAmount, Notes: req.Notes,
	})
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, a)
}

func (h *Handlers) ListAgreements(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListAgreements(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list bilateral agreements", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) TerminateAgreement(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "agreementID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	a, err := h.svc.TerminateAgreement(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, a)
}

// ---------------------------------------------------------------------
// Capacity offer grants
// ---------------------------------------------------------------------

type createGrantRequest struct {
	EnterpriseTenantID       string   `json:"enterprise_tenant_id"`
	BilateralAgreementID     *string  `json:"bilateral_agreement_id,omitempty"`
	PricePerUnitHourOverride *float64 `json:"price_per_unit_hour_override,omitempty"`
}

func (h *Handlers) CreateGrant(w http.ResponseWriter, r *http.Request) {
	offerID, err := uuid.Parse(chi.URLParam(r, "offerID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req createGrantRequest
	if err := decodeJSON(r, &req); err != nil || req.EnterpriseTenantID == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	tenantID, err := uuid.Parse(req.EnterpriseTenantID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var agreementID *uuid.UUID
	if req.BilateralAgreementID != nil {
		id, err := uuid.Parse(*req.BilateralAgreementID)
		if err != nil {
			apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
			return
		}
		agreementID = &id
	}
	if req.PricePerUnitHourOverride != nil && *req.PricePerUnitHourOverride < 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	g, err := h.svc.CreateGrant(r.Context(), offerID, CreateGrantInput{
		EnterpriseTenantID: tenantID, BilateralAgreementID: agreementID, PricePerUnitHourOverride: req.PricePerUnitHourOverride,
	})
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, g)
}

func (h *Handlers) ListGrantsForOffer(w http.ResponseWriter, r *http.Request) {
	offerID, err := uuid.Parse(chi.URLParam(r, "offerID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListGrantsForOffer(r.Context(), offerID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list capacity offer grants", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) RevokeGrant(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "grantID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.RevokeGrant(r.Context(), id); err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "revoked"})
}
