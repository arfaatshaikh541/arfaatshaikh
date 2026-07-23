package attestation

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
	case errors.Is(err, ErrClusterNotFound), errors.Is(err, ErrPolicyNotFound),
		errors.Is(err, ErrClusterAgentNotFound), errors.Is(err, ErrDeploymentNotFound):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusNotFound, apierror.CodeNotFound, err.Error()))
	case errors.Is(err, ErrNotAssignedAgent):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusForbidden, apierror.CodeForbidden, err.Error()))
	case errors.Is(err, ErrNoTrustedCertificate), errors.Is(err, ErrInvalidSignature):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusUnauthorized, apierror.CodeUnauthenticated, err.Error()))
	case errors.Is(err, ErrReplay):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	default:
		apierror.WriteJSON(w, r, logger, apierror.Wrap(500, apierror.CodeInternal, "attestation operation failed", err))
	}
}

// ---------------------------------------------------------------------
// Attestation policies (operator-scoped)
// ---------------------------------------------------------------------

type createPolicyRequest struct {
	ClusterID            string         `json:"cluster_id"`
	ProviderType         string         `json:"provider_type"`
	ExpectedMeasurements map[string]any `json:"expected_measurements"`
}

func (h *Handlers) CreatePolicy(w http.ResponseWriter, r *http.Request) {
	var req createPolicyRequest
	if err := decodeJSON(r, &req); err != nil || req.ProviderType == "" || len(req.ExpectedMeasurements) == 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	clusterID, err := uuid.Parse(req.ClusterID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	policy, err := h.svc.CreatePolicy(r.Context(), clusterID, req.ProviderType, req.ExpectedMeasurements)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, policy)
}

func (h *Handlers) ListPolicies(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListPolicies(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list attestation policies", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type revokePolicyRequest struct {
	Reason string `json:"reason"`
}

func (h *Handlers) RevokePolicy(w http.ResponseWriter, r *http.Request) {
	policyID, err := uuid.Parse(chi.URLParam(r, "policyID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req revokePolicyRequest
	if err := decodeJSON(r, &req); err != nil || req.Reason == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	policy, err := h.svc.RevokePolicy(r.Context(), policyID, req.Reason)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, policy)
}

// ---------------------------------------------------------------------
// Results (view-only)
// ---------------------------------------------------------------------

func (h *Handlers) ListOperatorResults(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "clusterAgentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListOperatorResults(r.Context(), agentID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListTenantResults(w http.ResponseWriter, r *http.Request) {
	deploymentID, err := uuid.Parse(chi.URLParam(r, "deploymentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListTenantResults(r.Context(), deploymentID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// Machine-authenticated (no session)
// ---------------------------------------------------------------------

type requestSessionRequest struct {
	Nonce     string `json:"nonce"`
	SignedAt  string `json:"signed_at"`
	Signature string `json:"signature"`
}

// RequestSession is called by a cluster agent to obtain a fresh,
// server-issued attestation challenge. The request body itself is signed
// (rather than using header-based challenge auth like PollPendingControlMessages)
// since this is a POST that creates a row and benefits from the exact same
// signed-body discipline every other agent-signed mutation in this
// codebase uses.
func (h *Handlers) RequestSession(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "clusterAgentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req requestSessionRequest
	if err := decodeJSON(r, &req); err != nil || req.Nonce == "" || req.SignedAt == "" || req.Signature == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	session, err := h.svc.RequestSession(r.Context(), agentID, req.Nonce, req.SignedAt, req.Signature)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, session)
}

const maxEvidenceBodyBytes = 1 << 20 // 1 MiB, generous for a mock evidence blob.

// SubmitEvidence reads the raw body first (the signature covers those
// exact bytes, same discipline as every other agent-signed endpoint in
// this codebase) and only afterward parses it as JSON.
func (h *Handlers) SubmitEvidence(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "clusterAgentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	sessionID, err := uuid.Parse(chi.URLParam(r, "sessionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	signature := r.Header.Get("X-Agent-Signature")
	if signature == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusUnauthorized, apierror.CodeUnauthenticated, "X-Agent-Signature header is required."))
		return
	}
	rawBody, err := io.ReadAll(io.LimitReader(r.Body, maxEvidenceBodyBytes+1))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if len(rawBody) > maxEvidenceBodyBytes {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var probe evidenceSubmission
	dec := json.NewDecoder(bytes.NewReader(rawBody))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&probe); err != nil || probe.DeploymentID == "" || probe.Nonce == "" || probe.SignedAt == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}

	result, err := h.svc.SubmitEvidence(r.Context(), agentID, sessionID, rawBody, signature)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, result)
}
