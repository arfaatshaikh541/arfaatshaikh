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
	case errors.Is(err, ErrOfferNotFound):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusNotFound, apierror.CodeNotFound, err.Error()))
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
	o, err := h.svc.CreateOffer(r.Context(), CreateOfferInput{
		ClusterID:                      clusterID,
		AcceleratorType:                acceleratorType,
		TotalCapacity:                  req.TotalCapacity,
		PricePerUnitHour:               req.PricePerUnitHour,
		Currency:                       currency,
		ConfidentialComputingAvailable: req.ConfidentialComputingAvailable,
		EstimatedKWhPerUnitHour:        req.EstimatedKWhPerUnitHour,
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
