package agents

import (
	"bytes"
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
	case errors.Is(err, ErrInvalidBootstrapToken), errors.Is(err, ErrInvalidCSR):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusUnauthorized, apierror.CodeUnauthenticated, "The bootstrap token or certificate request is invalid or expired."))
	case errors.Is(err, ErrAgentNotFound):
		apierror.WriteJSON(w, r, logger, apierror.ErrNotFound)
	case errors.Is(err, ErrNoTrustedCertificate), errors.Is(err, ErrInvalidSignature):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusUnauthorized, apierror.CodeUnauthenticated, "Signature verification failed."))
	case errors.Is(err, ErrUnknownCluster):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, "Cluster does not exist for this operator."))
	default:
		apierror.WriteJSON(w, r, logger, apierror.Wrap(500, apierror.CodeInternal, "agents operation failed", err))
	}
}

// ---------------------------------------------------------------------
// Session-authenticated, operator-scoped
// ---------------------------------------------------------------------

type registerAgentRequest struct {
	Name string `json:"name"`
}

func (h *Handlers) RegisterAgent(w http.ResponseWriter, r *http.Request) {
	var req registerAgentRequest
	if err := decodeJSON(r, &req); err != nil || req.Name == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	agent, rawToken, err := h.svc.RegisterAgent(r.Context(), req.Name)
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

func (h *Handlers) ListAgents(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListAgents(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list agents", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListAgentCertificates(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "agentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListAgentCertificates(r.Context(), agentID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type revokeAgentRequest struct {
	Reason string `json:"reason"`
}

func (h *Handlers) RevokeAgent(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "agentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req revokeAgentRequest
	if err := decodeJSON(r, &req); err != nil || req.Reason == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.RevokeAgent(r.Context(), agentID, req.Reason); err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "revoked"})
}

func (h *Handlers) ListCapacitySnapshots(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListCapacitySnapshots(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list capacity snapshots", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// Machine-authenticated (no session): bootstrap and signed ingestion
// ---------------------------------------------------------------------

type bootstrapRequest struct {
	BootstrapToken string `json:"bootstrap_token"`
	CSRPEM         string `json:"csr_pem"`
}

func (h *Handlers) Bootstrap(w http.ResponseWriter, r *http.Request) {
	var req bootstrapRequest
	if err := decodeJSON(r, &req); err != nil || req.BootstrapToken == "" || req.CSRPEM == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	certPEM, serial, expiresAt, err := h.svc.Bootstrap(r.Context(), req.BootstrapToken, []byte(req.CSRPEM))
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

type capacitySnapshotRequest struct {
	ClusterID   string         `json:"cluster_id"`
	CollectedAt string         `json:"collected_at"`
	Payload     map[string]any `json:"payload"`
}

const maxCapacitySnapshotBodyBytes = 1 << 20 // 1 MiB -- generous for a facts payload, bounded to avoid unbounded reads.

// SubmitCapacitySnapshot reads the raw request body first (the signature
// covers those exact bytes) and only afterward parses it as JSON -- signing
// then re-serializing would not reliably reproduce byte-for-byte what the
// agent actually signed.
func (h *Handlers) SubmitCapacitySnapshot(w http.ResponseWriter, r *http.Request) {
	agentID, err := uuid.Parse(chi.URLParam(r, "agentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	signature := r.Header.Get("X-Agent-Signature")
	if signature == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusUnauthorized, apierror.CodeUnauthenticated, "X-Agent-Signature header is required."))
		return
	}

	rawBody, err := io.ReadAll(io.LimitReader(r.Body, maxCapacitySnapshotBodyBytes+1))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if len(rawBody) > maxCapacitySnapshotBodyBytes {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}

	var req capacitySnapshotRequest
	dec := json.NewDecoder(bytes.NewReader(rawBody))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&req); err != nil || req.ClusterID == "" || req.CollectedAt == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	clusterID, err := uuid.Parse(req.ClusterID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	collectedAt, err := time.Parse(time.RFC3339, req.CollectedAt)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}

	cs, err := h.svc.SubmitCapacitySnapshot(r.Context(), agentID, clusterID, rawBody, signature, req.Payload, collectedAt)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, cs)
}
