package networkservices

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
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
	case errors.Is(err, ErrReservationNotActive):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	case errors.Is(err, ErrCapabilityNotFound), errors.Is(err, ErrOfferNotFound), errors.Is(err, ErrRequestNotFound),
		errors.Is(err, ErrReservationNotFound), errors.Is(err, ErrControlMessageNotFound):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusNotFound, apierror.CodeNotFound, err.Error()))
	case errors.Is(err, ErrNoTrustedCertificate), errors.Is(err, ErrInvalidSignature):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusUnauthorized, apierror.CodeUnauthenticated, err.Error()))
	case errors.Is(err, ErrReplay), errors.Is(err, ErrActionMismatch), errors.Is(err, ErrReservationMismatch):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, err.Error()))
	default:
		apierror.WriteJSON(w, r, logger, apierror.Wrap(500, apierror.CodeInternal, "network service operation failed", err))
	}
}

// ---------------------------------------------------------------------
// Network service offers (operator-scoped)
// ---------------------------------------------------------------------

type createOfferRequest struct {
	NetworkCapabilityID string   `json:"network_capability_id"`
	ServiceClass        string   `json:"service_class"`
	TotalBandwidthGbps  float64  `json:"total_bandwidth_gbps"`
	MaxLatencyMs        *float64 `json:"max_latency_ms,omitempty"`
	PricePerUnitHour    float64  `json:"price_per_unit_hour"`
	Currency            string   `json:"currency"`
}

func (h *Handlers) CreateOffer(w http.ResponseWriter, r *http.Request) {
	var req createOfferRequest
	if err := decodeJSON(r, &req); err != nil || req.ServiceClass == "" || req.TotalBandwidthGbps <= 0 ||
		req.PricePerUnitHour <= 0 || req.Currency == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	capabilityID, err := uuid.Parse(req.NetworkCapabilityID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	o, err := h.svc.CreateOffer(r.Context(), CreateOfferInput{
		NetworkCapabilityID: capabilityID, ServiceClass: req.ServiceClass, TotalBandwidthGbps: req.TotalBandwidthGbps,
		MaxLatencyMs: req.MaxLatencyMs, PricePerUnitHour: req.PricePerUnitHour, Currency: req.Currency,
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
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list network service offers", err))
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
	AvailableBandwidthGbps *float64 `json:"available_bandwidth_gbps,omitempty"`
	PricePerUnitHour       *float64 `json:"price_per_unit_hour,omitempty"`
	Status                 *string  `json:"status,omitempty"`
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
	o, err := h.svc.UpdateOffer(r.Context(), id, UpdateOfferInput(req))
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, o)
}

func (h *Handlers) ListOperatorReservations(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListOperatorReservations(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list network reservations", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListOperatorHealthEvents(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListOperatorHealthEvents(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list network health events", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// Enterprise-facing
// ---------------------------------------------------------------------

func (h *Handlers) ListActiveOffers(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListActiveOffers(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list network service offers", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type evaluateNetworkServiceRequest struct {
	DeploymentID          *string  `json:"deployment_id,omitempty"`
	RequiredBandwidthGbps float64  `json:"required_bandwidth_gbps"`
	MaxLatencyMs          *float64 `json:"max_latency_ms,omitempty"`
	ServiceClass          *string  `json:"service_class,omitempty"`
	Simulate              bool     `json:"simulate"`
}

func (h *Handlers) EvaluateAndReserve(w http.ResponseWriter, r *http.Request) {
	var req evaluateNetworkServiceRequest
	if err := decodeJSON(r, &req); err != nil || req.RequiredBandwidthGbps <= 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var deploymentID *uuid.UUID
	if req.DeploymentID != nil {
		id, err := uuid.Parse(*req.DeploymentID)
		if err != nil {
			apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
			return
		}
		deploymentID = &id
	}
	result, err := h.svc.EvaluateAndReserve(r.Context(), deploymentID, req.RequiredBandwidthGbps, req.MaxLatencyMs, req.ServiceClass, req.Simulate)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, result)
}

func (h *Handlers) ListRequests(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListRequests(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list network service requests", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListEvaluations(w http.ResponseWriter, r *http.Request) {
	requestID, err := uuid.Parse(chi.URLParam(r, "requestID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListEvaluations(r.Context(), requestID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list network service evaluations", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListTenantReservations(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListTenantReservations(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list network reservations", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListTenantHealthEvents(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListTenantHealthEvents(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list network health events", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type cancelReservationRequest struct {
	Reason string `json:"reason"`
}

func (h *Handlers) CancelReservation(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "reservationID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req cancelReservationRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	res, err := h.svc.CancelReservation(r.Context(), id, req.Reason)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, res)
}

// ---------------------------------------------------------------------
// Machine-authenticated (no session)
// ---------------------------------------------------------------------

const maxProvisionResultBodyBytes = 1 << 20 // 1 MiB, generous for a result payload.

// AgentReportProvisionResult reads the raw body first (the signature covers
// those exact bytes, the same discipline internal/modules/deployments'
// AgentReportCommandResult uses) and only afterward parses it as JSON.
func (h *Handlers) AgentReportProvisionResult(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "clusterAgentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	messageID, err := uuid.Parse(chi.URLParam(r, "messageID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	signature := r.Header.Get("X-Agent-Signature")
	if signature == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusUnauthorized, apierror.CodeUnauthenticated, "X-Agent-Signature header is required."))
		return
	}
	rawBody, err := io.ReadAll(io.LimitReader(r.Body, maxProvisionResultBodyBytes+1))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if len(rawBody) > maxProvisionResultBodyBytes {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var probe networkProvisionResult
	dec := json.NewDecoder(bytes.NewReader(rawBody))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&probe); err != nil || probe.Action == "" || probe.Nonce == "" || probe.SignedAt == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	event, err := h.svc.AgentReportProvisionResult(r.Context(), agentID, messageID, rawBody, signature)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, event)
}
