package policies

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"gridkeep/control-api/internal/platform/apierror"
	"gridkeep/control-api/internal/platform/policyengine"
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
	case errors.Is(err, ErrPolicyNotFound):
		apierror.WriteJSON(w, r, logger, apierror.ErrNotFound)
	case errors.Is(err, ErrDraftAlreadyExists):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	case errors.Is(err, ErrNotADraft), errors.Is(err, ErrNotPendingPublish), errors.Is(err, ErrPolicyNotPublished):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	case errors.Is(err, ErrCannotSelfApprove):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusForbidden, apierror.CodeForbidden, err.Error()))
	case errors.Is(err, ErrPublishBlockedByConflict):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	default:
		apierror.WriteJSON(w, r, logger, apierror.Wrap(500, apierror.CodeInternal, "policies operation failed", err))
	}
}

func (h *Handlers) ListPolicies(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListPolicies(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list policies", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListVersions(w http.ResponseWriter, r *http.Request) {
	policyKey := chi.URLParam(r, "policyKey")
	out, err := h.svc.ListVersions(r.Context(), policyKey)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list policy versions", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) GetPolicy(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "policyID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	p, err := h.svc.GetPolicy(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, p)
}

type createDraftRequest struct {
	PolicyKey string                      `json:"policy_key"`
	Name      string                      `json:"name"`
	Document  policyengine.PolicyDocument `json:"document"`
}

func (h *Handlers) CreateDraft(w http.ResponseWriter, r *http.Request) {
	var req createDraftRequest
	if err := decodeJSON(r, &req); err != nil || req.PolicyKey == "" || req.Name == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	p, err := h.svc.CreateDraft(r.Context(), req.PolicyKey, req.Name, req.Document)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, p)
}

type editDraftRequest struct {
	Name     string                      `json:"name"`
	Document policyengine.PolicyDocument `json:"document"`
}

func (h *Handlers) EditDraft(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "policyID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req editDraftRequest
	if err := decodeJSON(r, &req); err != nil || req.Name == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	p, err := h.svc.EditDraft(r.Context(), id, req.Name, req.Document)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, p)
}

func (h *Handlers) RequestPublish(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "policyID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	p, err := h.svc.RequestPublish(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, p)
}

func (h *Handlers) ApprovePublish(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "policyID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	p, err := h.svc.ApprovePublish(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, p)
}

type rollbackRequest struct {
	ToVersion int `json:"to_version"`
}

func (h *Handlers) Rollback(w http.ResponseWriter, r *http.Request) {
	policyKey := chi.URLParam(r, "policyKey")
	var req rollbackRequest
	if err := decodeJSON(r, &req); err != nil || req.ToVersion <= 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	p, err := h.svc.Rollback(r.Context(), policyKey, req.ToVersion)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, p)
}

type evaluationCandidateRequest struct {
	Candidate policyengine.EvaluationCandidate `json:"candidate"`
}

func (h *Handlers) Simulate(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "policyID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req evaluationCandidateRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	result, err := h.svc.Simulate(r.Context(), id, req.Candidate)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, result)
}

func (h *Handlers) Evaluate(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "policyID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req evaluationCandidateRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	result, err := h.svc.Evaluate(r.Context(), id, req.Candidate)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, result)
}

func (h *Handlers) ListEvaluationRecords(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListEvaluationRecords(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list evaluation records", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}
