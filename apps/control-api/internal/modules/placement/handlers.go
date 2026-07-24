package placement

import (
	"encoding/json"
	"errors"
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
	case errors.Is(err, ErrVersionNotPublished), errors.Is(err, ErrApprovalNotRequired), errors.Is(err, ErrCannotCancel):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, err.Error()))
	case errors.Is(err, ErrVersionNotFound), errors.Is(err, ErrReservationNotFound):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusNotFound, apierror.CodeNotFound, err.Error()))
	case errors.Is(err, ErrNotHeld), errors.Is(err, ErrCannotSelfApprove):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	default:
		apierror.WriteJSON(w, r, logger, apierror.Wrap(500, apierror.CodeInternal, "placement operation failed", err))
	}
}

func (h *Handlers) ListActiveOffers(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListActiveOffers(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list capacity offers", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListMyAgreements(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListMyAgreements(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list bilateral agreements", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type createPlacementRequestRequest struct {
	WorkloadVersionID   string     `json:"workload_version_id"`
	Quantity            int        `json:"quantity"`
	Simulate            bool       `json:"simulate"`
	NonUrgent           bool       `json:"non_urgent"`
	ScheduleWindowStart *time.Time `json:"schedule_window_start"`
	ScheduleWindowEnd   *time.Time `json:"schedule_window_end"`
}

func (h *Handlers) EvaluatePlacement(w http.ResponseWriter, r *http.Request) {
	var req createPlacementRequestRequest
	if err := decodeJSON(r, &req); err != nil || req.Quantity <= 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	versionID, err := uuid.Parse(req.WorkloadVersionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	result, err := h.svc.EvaluatePlacement(r.Context(), versionID, req.Quantity, req.Simulate, req.NonUrgent, req.ScheduleWindowStart, req.ScheduleWindowEnd)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, result)
}

func (h *Handlers) ListPlacementRequests(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListPlacementRequests(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list placement requests", err))
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
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list placement evaluations", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListReservations(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListReservations(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list capacity reservations", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ApproveCommitReservation(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "reservationID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	res, err := h.svc.ApproveCommitReservation(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, res)
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
