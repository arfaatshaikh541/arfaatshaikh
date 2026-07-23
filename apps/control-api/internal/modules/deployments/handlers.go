package deployments

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
	case errors.Is(err, ErrReservationNotCommitted), errors.Is(err, ErrReservationAlreadyDeployed),
		errors.Is(err, ErrPlanNotDraft), errors.Is(err, ErrPlanNotPendingApproval), errors.Is(err, ErrNoApprovedPlan),
		errors.Is(err, ErrDeploymentNotRunning), errors.Is(err, ErrDeploymentNotPaused), errors.Is(err, ErrDeploymentNotFailed),
		errors.Is(err, ErrNoRollbackTarget), errors.Is(err, ErrNoPlanToRetry), errors.Is(err, ErrReplay):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	case errors.Is(err, ErrReservationNotFound), errors.Is(err, ErrDeploymentNotFound), errors.Is(err, ErrPlanNotFound),
		errors.Is(err, ErrSecretNotFound), errors.Is(err, ErrNoActiveClusterAgent), errors.Is(err, ErrControlMessageNotFound):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusNotFound, apierror.CodeNotFound, err.Error()))
	case errors.Is(err, ErrCannotSelfApprovePlan), errors.Is(err, ErrNotAssignedAgent):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusForbidden, apierror.CodeForbidden, err.Error()))
	case errors.Is(err, ErrNoTrustedCertificate), errors.Is(err, ErrInvalidSignature):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusUnauthorized, apierror.CodeUnauthenticated, err.Error()))
	case errors.Is(err, ErrActionMismatch):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, err.Error()))
	default:
		apierror.WriteJSON(w, r, logger, apierror.Wrap(500, apierror.CodeInternal, "deployment operation failed", err))
	}
}

// ---------------------------------------------------------------------
// Deployments (enterprise-scoped)
// ---------------------------------------------------------------------

type createDeploymentRequest struct {
	CapacityReservationID string `json:"capacity_reservation_id"`
	Namespace             string `json:"namespace"`
	ReplicaCount          int    `json:"replica_count"`
}

func (h *Handlers) CreateDeployment(w http.ResponseWriter, r *http.Request) {
	var req createDeploymentRequest
	if err := decodeJSON(r, &req); err != nil || req.Namespace == "" || req.ReplicaCount <= 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	reservationID, err := uuid.Parse(req.CapacityReservationID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	d, err := h.svc.CreateDeployment(r.Context(), reservationID, req.Namespace, req.ReplicaCount)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, d)
}

func (h *Handlers) ListDeployments(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListDeployments(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list deployments", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func deploymentIDParam(r *http.Request) (uuid.UUID, error) {
	return uuid.Parse(chi.URLParam(r, "deploymentID"))
}

func (h *Handlers) GetDeployment(w http.ResponseWriter, r *http.Request) {
	id, err := deploymentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	d, err := h.svc.GetDeployment(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, d)
}

func (h *Handlers) ListDeploymentEvents(w http.ResponseWriter, r *http.Request) {
	id, err := deploymentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListDeploymentEvents(r.Context(), id)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list deployment events", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// Deployments (operator-scoped read access)
// ---------------------------------------------------------------------

func (h *Handlers) ListOperatorDeployments(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListOperatorDeployments(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list deployments", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListOperatorDeploymentEvents(w http.ResponseWriter, r *http.Request) {
	id, err := deploymentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListOperatorDeploymentEvents(r.Context(), id)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list deployment events", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// Deployment plans
// ---------------------------------------------------------------------

func (h *Handlers) CreatePlan(w http.ResponseWriter, r *http.Request) {
	deploymentID, err := deploymentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	plan, err := h.svc.CreatePlan(r.Context(), deploymentID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, plan)
}

func (h *Handlers) ListPlans(w http.ResponseWriter, r *http.Request) {
	deploymentID, err := deploymentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListPlans(r.Context(), deploymentID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list deployment plans", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func planIDParams(r *http.Request) (deploymentID, planID uuid.UUID, err error) {
	deploymentID, err = deploymentIDParam(r)
	if err != nil {
		return uuid.Nil, uuid.Nil, err
	}
	planID, err = uuid.Parse(chi.URLParam(r, "planID"))
	return deploymentID, planID, err
}

func (h *Handlers) RequestPlanApproval(w http.ResponseWriter, r *http.Request) {
	deploymentID, planID, err := planIDParams(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	plan, err := h.svc.RequestPlanApproval(r.Context(), deploymentID, planID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, plan)
}

func (h *Handlers) ApprovePlan(w http.ResponseWriter, r *http.Request) {
	deploymentID, planID, err := planIDParams(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	plan, err := h.svc.ApprovePlan(r.Context(), deploymentID, planID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, plan)
}

type rejectPlanRequest struct {
	Reason string `json:"reason"`
}

func (h *Handlers) RejectPlan(w http.ResponseWriter, r *http.Request) {
	deploymentID, planID, err := planIDParams(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req rejectPlanRequest
	if err := decodeJSON(r, &req); err != nil || req.Reason == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	plan, err := h.svc.RejectPlan(r.Context(), deploymentID, planID, req.Reason)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, plan)
}

func (h *Handlers) SubmitPlan(w http.ResponseWriter, r *http.Request) {
	deploymentID, planID, err := planIDParams(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	d, err := h.svc.SubmitPlan(r.Context(), deploymentID, planID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, d)
}

// ---------------------------------------------------------------------
// Lifecycle actions
// ---------------------------------------------------------------------

type scaleRequest struct {
	ReplicaCount int `json:"replica_count"`
}

func (h *Handlers) Scale(w http.ResponseWriter, r *http.Request) {
	deploymentID, err := deploymentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req scaleRequest
	if err := decodeJSON(r, &req); err != nil || req.ReplicaCount <= 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	d, err := h.svc.Scale(r.Context(), deploymentID, req.ReplicaCount)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, d)
}

func (h *Handlers) Pause(w http.ResponseWriter, r *http.Request) {
	deploymentID, err := deploymentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	d, err := h.svc.Pause(r.Context(), deploymentID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, d)
}

func (h *Handlers) Resume(w http.ResponseWriter, r *http.Request) {
	deploymentID, err := deploymentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	d, err := h.svc.Resume(r.Context(), deploymentID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, d)
}

func (h *Handlers) Terminate(w http.ResponseWriter, r *http.Request) {
	deploymentID, err := deploymentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	d, err := h.svc.Terminate(r.Context(), deploymentID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, d)
}

type rollbackRequest struct {
	TargetVersion int `json:"target_version"`
}

func (h *Handlers) Rollback(w http.ResponseWriter, r *http.Request) {
	deploymentID, err := deploymentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req rollbackRequest
	if err := decodeJSON(r, &req); err != nil || req.TargetVersion <= 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	d, err := h.svc.Rollback(r.Context(), deploymentID, req.TargetVersion)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, d)
}

func (h *Handlers) Retry(w http.ResponseWriter, r *http.Request) {
	deploymentID, err := deploymentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	d, err := h.svc.Retry(r.Context(), deploymentID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, d)
}

// ---------------------------------------------------------------------
// Workload secrets
// ---------------------------------------------------------------------

// workloadVersionIDParam reads the same "versionID" URL param name
// internal/modules/workloads' routes already use at this path position --
// chi requires a consistent param name at a shared routing position.
func workloadVersionIDParam(r *http.Request) (uuid.UUID, error) {
	return uuid.Parse(chi.URLParam(r, "versionID"))
}

type createWorkloadSecretRequest struct {
	Key   string `json:"key"`
	Value string `json:"value"`
}

func (h *Handlers) CreateWorkloadSecret(w http.ResponseWriter, r *http.Request) {
	workloadVersionID, err := workloadVersionIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req createWorkloadSecretRequest
	if err := decodeJSON(r, &req); err != nil || req.Key == "" || req.Value == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	secret, err := h.svc.CreateWorkloadSecret(r.Context(), workloadVersionID, req.Key, req.Value)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, secret)
}

func (h *Handlers) ListWorkloadSecrets(w http.ResponseWriter, r *http.Request) {
	workloadVersionID, err := workloadVersionIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListWorkloadSecrets(r.Context(), workloadVersionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list workload secrets", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) DeleteWorkloadSecret(w http.ResponseWriter, r *http.Request) {
	workloadVersionID, err := workloadVersionIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	secretID, err := uuid.Parse(chi.URLParam(r, "secretID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.DeleteWorkloadSecret(r.Context(), workloadVersionID, secretID); err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "deleted"})
}

// ---------------------------------------------------------------------
// Machine-authenticated (no session)
// ---------------------------------------------------------------------

// AgentFetchSecrets is called by the one cluster agent assigned to a
// deployment to retrieve its workload version's decrypted secret values.
// Identity is proved the same way Milestone 6's PollPendingControlMessages
// proves it: a signature over a canonical challenge built from headers the
// agent itself supplies.
func (h *Handlers) AgentFetchSecrets(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "clusterAgentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	deploymentID, err := deploymentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	nonce := r.Header.Get("X-Agent-Nonce")
	signedAt := r.Header.Get("X-Agent-Signed-At")
	signature := r.Header.Get("X-Agent-Signature")
	if nonce == "" || signedAt == "" || signature == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusUnauthorized, apierror.CodeUnauthenticated, "X-Agent-Nonce, X-Agent-Signed-At, and X-Agent-Signature headers are required."))
		return
	}
	secrets, err := h.svc.AgentFetchSecrets(r.Context(), agentID, deploymentID, nonce, signedAt, signature)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"secrets": secrets})
}

const maxCommandResultBodyBytes = 1 << 20 // 1 MiB, generous for a result payload.

// AgentReportCommandResult reads the raw body first (the signature covers
// those exact bytes, same discipline as every other agent-signed endpoint
// in this codebase) and only afterward parses it as JSON.
func (h *Handlers) AgentReportCommandResult(w http.ResponseWriter, r *http.Request) {
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
	rawBody, err := io.ReadAll(io.LimitReader(r.Body, maxCommandResultBodyBytes+1))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if len(rawBody) > maxCommandResultBodyBytes {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var probe deploymentCommandResult
	dec := json.NewDecoder(bytes.NewReader(rawBody))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&probe); err != nil || probe.Action == "" || probe.Nonce == "" || probe.SignedAt == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	event, err := h.svc.AgentReportCommandResult(r.Context(), agentID, messageID, rawBody, signature)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, event)
}
