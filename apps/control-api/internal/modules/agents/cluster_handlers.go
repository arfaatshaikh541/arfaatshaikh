package agents

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"gridkeep/control-api/internal/platform/apierror"
)

// ---------------------------------------------------------------------
// Session-authenticated, operator-scoped
// ---------------------------------------------------------------------

type registerClusterAgentRequest struct {
	ClusterID string `json:"cluster_id"`
	Name      string `json:"name"`
}

func (h *Handlers) RegisterClusterAgent(w http.ResponseWriter, r *http.Request) {
	var req registerClusterAgentRequest
	if err := decodeJSON(r, &req); err != nil || req.Name == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	clusterID, err := uuid.Parse(req.ClusterID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	agent, rawToken, err := h.svc.RegisterClusterAgent(r.Context(), clusterID, req.Name)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, map[string]any{
		"agent":            agent,
		"bootstrap_token":  rawToken,
		"bootstrap_notice": "This token is shown once. Provide it to the agent out of band; it cannot be retrieved again.",
	})
}

func (h *Handlers) ListClusterAgents(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListClusterAgents(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list cluster agents", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListClusterAgentCertificates(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "clusterAgentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListClusterAgentCertificates(r.Context(), agentID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) RevokeClusterAgent(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "clusterAgentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req revokeAgentRequest
	if err := decodeJSON(r, &req); err != nil || req.Reason == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.RevokeClusterAgent(r.Context(), agentID, req.Reason); err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "revoked"})
}

func (h *Handlers) ListControlMessages(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "clusterAgentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListControlMessages(r.Context(), agentID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListDeploymentPlanValidations(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "clusterAgentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListDeploymentPlanValidations(r.Context(), agentID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type deploymentPlanRequestRequest struct {
	ClusterID             string         `json:"cluster_id"`
	WorkloadVersionID     string         `json:"workload_version_id"`
	CapacityReservationID string         `json:"capacity_reservation_id"`
	Namespace             string         `json:"namespace"`
	ResourceQuota         map[string]any `json:"resource_quota"`
	NetworkPolicy         map[string]any `json:"network_policy"`
	SecurityContext       map[string]any `json:"security_context"`
}

// RequestDeploymentPlanValidation is an operator-triggered stand-in for
// what Milestone 7's real orchestrator will eventually call automatically
// once a placement is reserved -- see Service.RequestDeploymentPlanValidation's
// doc comment.
func (h *Handlers) RequestDeploymentPlanValidation(w http.ResponseWriter, r *http.Request) {
	var req deploymentPlanRequestRequest
	if err := decodeJSON(r, &req); err != nil || req.Namespace == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	clusterID, err := uuid.Parse(req.ClusterID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var workloadVersionID, capacityReservationID *uuid.UUID
	if req.WorkloadVersionID != "" {
		id, err := uuid.Parse(req.WorkloadVersionID)
		if err != nil {
			apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
			return
		}
		workloadVersionID = &id
	}
	if req.CapacityReservationID != "" {
		id, err := uuid.Parse(req.CapacityReservationID)
		if err != nil {
			apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
			return
		}
		capacityReservationID = &id
	}
	msg, err := h.svc.RequestDeploymentPlanValidation(r.Context(), clusterID, workloadVersionID, capacityReservationID,
		req.Namespace, req.ResourceQuota, req.NetworkPolicy, req.SecurityContext)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, msg)
}

// ---------------------------------------------------------------------
// Machine-authenticated (no session)
// ---------------------------------------------------------------------

func (h *Handlers) ClusterAgentBootstrap(w http.ResponseWriter, r *http.Request) {
	var req bootstrapRequest
	if err := decodeJSON(r, &req); err != nil || req.BootstrapToken == "" || req.CSRPEM == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	certPEM, serial, expiresAt, err := h.svc.ClusterAgentBootstrap(r.Context(), req.BootstrapToken, []byte(req.CSRPEM))
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, map[string]any{
		"certificate_pem": certPEM,
		"serial_number":   serial,
		"expires_at":      expiresAt,
	})
}

type rotateCertificateRequest struct {
	CSRPEM    string `json:"csr_pem"`
	Signature string `json:"signature"`
}

func (h *Handlers) RotateClusterAgentCertificate(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "clusterAgentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req rotateCertificateRequest
	if err := decodeJSON(r, &req); err != nil || req.CSRPEM == "" || req.Signature == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	certPEM, serial, expiresAt, err := h.svc.RotateClusterAgentCertificate(r.Context(), agentID, []byte(req.CSRPEM), req.Signature)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, map[string]any{
		"certificate_pem": certPEM,
		"serial_number":   serial,
		"expires_at":      expiresAt,
	})
}

func (h *Handlers) RotateOperatorAgentCertificate(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "agentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req rotateCertificateRequest
	if err := decodeJSON(r, &req); err != nil || req.CSRPEM == "" || req.Signature == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	certPEM, serial, expiresAt, err := h.svc.RotateOperatorAgentCertificate(r.Context(), agentID, []byte(req.CSRPEM), req.Signature)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, map[string]any{
		"certificate_pem": certPEM,
		"serial_number":   serial,
		"expires_at":      expiresAt,
	})
}

// PollPendingControlMessages is called by a cluster agent (outbound-only
// connectivity from its side -- it polls, control-api never opens a
// connection to it) to fetch messages awaiting a response. Identity is
// proved by a signature over a canonical challenge string built from the
// nonce and signed_at the agent itself supplies as headers.
func (h *Handlers) PollPendingControlMessages(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "clusterAgentID"))
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
	out, err := h.svc.PollPendingControlMessages(r.Context(), agentID, nonce, signedAt, signature)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, out)
}

const maxControlMessageResponseBodyBytes = 1 << 20 // 1 MiB, generous for a decision payload.

// RespondToControlMessage reads the raw body first (the signature covers
// those exact bytes, same discipline as SubmitCapacitySnapshot) and only
// afterward parses it as JSON.
func (h *Handlers) RespondToControlMessage(w http.ResponseWriter, r *http.Request) {
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
	rawBody, err := io.ReadAll(io.LimitReader(r.Body, maxControlMessageResponseBodyBytes+1))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if len(rawBody) > maxControlMessageResponseBodyBytes {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var probe respondInput
	dec := json.NewDecoder(bytes.NewReader(rawBody))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&probe); err != nil || probe.Nonce == "" || probe.SignedAt == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}

	validation, err := h.svc.RespondToControlMessage(r.Context(), agentID, messageID, rawBody, signature)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, validation)
}

// PlatformCACertificate exposes the platform CA's own certificate -- public
// information any cluster agent needs once, before it can verify any
// control-message signature, exactly as any TLS client needs a CA's public
// certificate. Mounted unauthenticated, like the jurisdiction/region
// taxonomy.
func (h *Handlers) PlatformCACertificate(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"certificate_pem": h.svc.PlatformCACertificatePEM()})
}
