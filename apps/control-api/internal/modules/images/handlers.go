package images

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
	case errors.Is(err, ErrImageNotFound), errors.Is(err, ErrExceptionNotFound):
		apierror.WriteJSON(w, r, logger, apierror.ErrNotFound)
	case errors.Is(err, ErrRegistryNotApproved):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, err.Error()))
	case errors.Is(err, ErrImageNotPending), errors.Is(err, ErrImageNotApproved),
		errors.Is(err, ErrExceptionNotPending), errors.Is(err, ErrBlockedByVulnerabilityPolicy):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	case errors.Is(err, ErrCannotSelfApproveException):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusForbidden, apierror.CodeForbidden, err.Error()))
	default:
		apierror.WriteJSON(w, r, logger, apierror.Wrap(500, apierror.CodeInternal, "image registry operation failed", err))
	}
}

// --- platform-scoped: approved registries ---

func (h *Handlers) ListApprovedRegistries(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListApprovedRegistries(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list approved registries", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type addApprovedRegistryRequest struct {
	RegistryHost string `json:"registry_host"`
	Notes        string `json:"notes"`
}

func (h *Handlers) AddApprovedRegistry(w http.ResponseWriter, r *http.Request) {
	var req addApprovedRegistryRequest
	if err := decodeJSON(r, &req); err != nil || req.RegistryHost == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	reg, err := h.svc.AddApprovedRegistry(r.Context(), req.RegistryHost, req.Notes)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, reg)
}

type setRegistryActiveRequest struct {
	IsActive bool `json:"is_active"`
}

func (h *Handlers) SetApprovedRegistryActive(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "registryID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req setRegistryActiveRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.SetApprovedRegistryActive(r.Context(), id, req.IsActive); err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]bool{"is_active": req.IsActive})
}

// --- tenant-scoped: container images ---

func (h *Handlers) ListImages(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListImages(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list images", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) GetImage(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "imageID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	img, err := h.svc.GetImage(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, img)
}

type registerImageRequest struct {
	RegistryHost string `json:"registry_host"`
	Repository   string `json:"repository"`
	Digest       string `json:"digest"`
	Tag          string `json:"tag"`
}

func (h *Handlers) RegisterImage(w http.ResponseWriter, r *http.Request) {
	var req registerImageRequest
	if err := decodeJSON(r, &req); err != nil || req.RegistryHost == "" || req.Repository == "" || req.Digest == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	img, err := h.svc.RegisterImage(r.Context(), req.RegistryHost, req.Repository, req.Digest, req.Tag)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, img)
}

func (h *Handlers) ApproveImage(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "imageID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	img, err := h.svc.ApproveImage(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, img)
}

type reasonRequest struct {
	Reason string `json:"reason"`
}

func (h *Handlers) RevokeImage(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "imageID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req reasonRequest
	if err := decodeJSON(r, &req); err != nil || req.Reason == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	img, err := h.svc.RevokeImage(r.Context(), id, req.Reason)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, img)
}

type recordSignatureRequest struct {
	Signer          string     `json:"signer"`
	PublicKeyPEM    string     `json:"public_key_pem"`
	SignatureBase64 string     `json:"signature_base64"`
	SignedAt        *time.Time `json:"signed_at"`
}

func (h *Handlers) RecordSignature(w http.ResponseWriter, r *http.Request) {
	imageID, err := uuid.Parse(chi.URLParam(r, "imageID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req recordSignatureRequest
	if err := decodeJSON(r, &req); err != nil || req.PublicKeyPEM == "" || req.SignatureBase64 == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	sig, err := h.svc.RecordSignature(r.Context(), imageID, req.Signer, req.PublicKeyPEM, req.SignatureBase64, req.SignedAt)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, sig)
}

func (h *Handlers) ListSignatures(w http.ResponseWriter, r *http.Request) {
	imageID, err := uuid.Parse(chi.URLParam(r, "imageID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListSignatures(r.Context(), imageID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list signatures", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type recordProvenanceRequest struct {
	Builder          string         `json:"builder"`
	SourceRepository string         `json:"source_repository"`
	BuildCommit      string         `json:"build_commit"`
	BuildPipelineURL string         `json:"build_pipeline_url"`
	Attestation      map[string]any `json:"attestation"`
}

func (h *Handlers) RecordProvenance(w http.ResponseWriter, r *http.Request) {
	imageID, err := uuid.Parse(chi.URLParam(r, "imageID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req recordProvenanceRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	p, err := h.svc.RecordProvenance(r.Context(), imageID, req.Builder, req.SourceRepository, req.BuildCommit, req.BuildPipelineURL, req.Attestation)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, p)
}

func (h *Handlers) GetProvenance(w http.ResponseWriter, r *http.Request) {
	imageID, err := uuid.Parse(chi.URLParam(r, "imageID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	p, err := h.svc.GetProvenance(r.Context(), imageID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, p)
}

type ingestSBOMRequest struct {
	Format      string         `json:"format"`
	Document    map[string]any `json:"document"`
	GeneratedBy string         `json:"generated_by"`
}

func (h *Handlers) IngestSBOM(w http.ResponseWriter, r *http.Request) {
	imageID, err := uuid.Parse(chi.URLParam(r, "imageID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req ingestSBOMRequest
	if err := decodeJSON(r, &req); err != nil || (req.Format != "spdx" && req.Format != "cyclonedx") {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	sbom, err := h.svc.IngestSBOM(r.Context(), imageID, req.Format, req.Document, req.GeneratedBy)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, sbom)
}

func (h *Handlers) ListSBOMs(w http.ResponseWriter, r *http.Request) {
	imageID, err := uuid.Parse(chi.URLParam(r, "imageID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListSBOMs(r.Context(), imageID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list SBOMs", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type findingRequest struct {
	CVEID          string `json:"cve_id"`
	Severity       string `json:"severity"`
	PackageName    string `json:"package_name"`
	PackageVersion string `json:"package_version"`
	FixedVersion   string `json:"fixed_version"`
	Description    string `json:"description"`
}

type ingestScanRequest struct {
	Scanner   string           `json:"scanner"`
	ScannedAt time.Time        `json:"scanned_at"`
	Findings  []findingRequest `json:"findings"`
}

func (h *Handlers) IngestVulnerabilityScan(w http.ResponseWriter, r *http.Request) {
	imageID, err := uuid.Parse(chi.URLParam(r, "imageID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req ingestScanRequest
	if err := decodeJSON(r, &req); err != nil || req.Scanner == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	findings := make([]FindingInput, 0, len(req.Findings))
	for _, f := range req.Findings {
		findings = append(findings, FindingInput(f))
	}
	scan, createdFindings, err := h.svc.IngestVulnerabilityScan(r.Context(), imageID, req.Scanner, req.ScannedAt, findings)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, map[string]any{"scan": scan, "findings": createdFindings})
}

func (h *Handlers) ListVulnerabilityScans(w http.ResponseWriter, r *http.Request) {
	imageID, err := uuid.Parse(chi.URLParam(r, "imageID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListVulnerabilityScans(r.Context(), imageID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list vulnerability scans", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListFindings(w http.ResponseWriter, r *http.Request) {
	scanID, err := uuid.Parse(chi.URLParam(r, "scanID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListFindings(r.Context(), scanID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list findings", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) GetVulnerabilityPolicy(w http.ResponseWriter, r *http.Request) {
	policy, err := h.svc.GetVulnerabilityPolicy(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to get vulnerability policy", err))
		return
	}
	writeJSON(w, http.StatusOK, policy)
}

type updateVulnerabilityPolicyRequest struct {
	MaxAllowedSeverity  string `json:"max_allowed_severity"`
	BlockUnsignedImages bool   `json:"block_unsigned_images"`
	RequireSBOM         bool   `json:"require_sbom"`
}

func (h *Handlers) UpdateVulnerabilityPolicy(w http.ResponseWriter, r *http.Request) {
	var req updateVulnerabilityPolicyRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	policy, err := h.svc.UpdateVulnerabilityPolicy(r.Context(), req.MaxAllowedSeverity, req.BlockUnsignedImages, req.RequireSBOM)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, policy)
}

type requestExceptionRequest struct {
	FindingID *uuid.UUID `json:"finding_id"`
	Reason    string     `json:"reason"`
	ExpiresAt time.Time  `json:"expires_at"`
}

func (h *Handlers) RequestException(w http.ResponseWriter, r *http.Request) {
	imageID, err := uuid.Parse(chi.URLParam(r, "imageID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req requestExceptionRequest
	if err := decodeJSON(r, &req); err != nil || req.Reason == "" || req.ExpiresAt.IsZero() {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	e, err := h.svc.RequestException(r.Context(), imageID, req.FindingID, req.Reason, req.ExpiresAt)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, e)
}

func (h *Handlers) ApproveException(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "exceptionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	e, err := h.svc.ApproveException(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, e)
}

func (h *Handlers) RejectException(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "exceptionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	e, err := h.svc.RejectException(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, e)
}

func (h *Handlers) ListExceptions(w http.ResponseWriter, r *http.Request) {
	imageID, err := uuid.Parse(chi.URLParam(r, "imageID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListExceptions(r.Context(), imageID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list exceptions", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}
