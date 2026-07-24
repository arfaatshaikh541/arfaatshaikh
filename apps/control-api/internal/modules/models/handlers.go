package models

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
	case errors.Is(err, ErrModelNotFound), errors.Is(err, ErrVersionNotFound), errors.Is(err, ErrLicenceNotFound),
		errors.Is(err, ErrGrantNotFound), errors.Is(err, ErrProviderNotFound):
		apierror.WriteJSON(w, r, logger, apierror.ErrNotFound)
	case errors.Is(err, ErrModelKeyExists), errors.Is(err, ErrProviderKeyExists):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	case errors.Is(err, ErrNotADraft), errors.Is(err, ErrNotPendingApproval), errors.Is(err, ErrNotApproved), errors.Is(err, ErrNotApprovedOrRetired),
		errors.Is(err, ErrNotPublishable), errors.Is(err, ErrNotPublished), errors.Is(err, ErrProviderNotActive), errors.Is(err, ErrProviderNotSuspended):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	case errors.Is(err, ErrCannotSelfApprove), errors.Is(err, ErrLicenceForbidsCommercial):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusForbidden, apierror.CodeForbidden, err.Error()))
	default:
		apierror.WriteJSON(w, r, logger, apierror.Wrap(500, apierror.CodeInternal, "model registry operation failed", err))
	}
}

func (h *Handlers) ListProviders(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListProviders(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list model providers", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListLicences(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListLicences(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list model licences", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListModels(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListModels(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list models", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) GetModel(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "modelID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	m, err := h.svc.GetModel(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, m)
}

type createModelRequest struct {
	ModelKey    string     `json:"model_key"`
	Name        string     `json:"name"`
	Description string     `json:"description"`
	ProviderID  *uuid.UUID `json:"provider_id"`
}

func (h *Handlers) CreateModel(w http.ResponseWriter, r *http.Request) {
	var req createModelRequest
	if err := decodeJSON(r, &req); err != nil || req.ModelKey == "" || req.Name == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	m, err := h.svc.CreateModel(r.Context(), req.ModelKey, req.Name, req.Description, req.ProviderID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, m)
}

func (h *Handlers) ListVersions(w http.ResponseWriter, r *http.Request) {
	modelID, err := uuid.Parse(chi.URLParam(r, "modelID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListVersions(r.Context(), modelID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list model versions", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) GetVersion(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	v, err := h.svc.GetVersion(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, v)
}

type versionInputRequest struct {
	ProviderID                 *uuid.UUID     `json:"provider_id"`
	LicenceID                  uuid.UUID      `json:"licence_id"`
	ChecksumSHA256             string         `json:"checksum_sha256"`
	Provenance                 map[string]any `json:"provenance"`
	PermittedGeographies       []string       `json:"permitted_geographies"`
	ProhibitedGeographies      []string       `json:"prohibited_geographies"`
	SupportedWorkloadTypes     []string       `json:"supported_workload_types"`
	SupportedLanguages         []string       `json:"supported_languages"`
	HardwareRequirements       map[string]any `json:"hardware_requirements"`
	MinimumAcceleratorMemoryGB *int           `json:"minimum_accelerator_memory_gb"`
	SecurityProfile            map[string]any `json:"security_profile"`
	PerformanceMetadata        map[string]any `json:"performance_metadata"`
	InputTypes                 []string       `json:"input_types"`
	OutputTypes                []string       `json:"output_types"`
	RetentionPolicy            map[string]any `json:"retention_policy"`
	PricingMetadata            map[string]any `json:"pricing_metadata"`
}

func (r versionInputRequest) toInput() ModelVersionInput {
	return ModelVersionInput(r)
}

func (h *Handlers) CreateDraftVersion(w http.ResponseWriter, r *http.Request) {
	modelID, err := uuid.Parse(chi.URLParam(r, "modelID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req versionInputRequest
	if err := decodeJSON(r, &req); err != nil || req.LicenceID == uuid.Nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	v, err := h.svc.CreateDraftVersion(r.Context(), modelID, req.toInput())
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, v)
}

func (h *Handlers) EditDraftVersion(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req versionInputRequest
	if err := decodeJSON(r, &req); err != nil || req.LicenceID == uuid.Nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	v, err := h.svc.EditDraftVersion(r.Context(), id, req.toInput())
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, v)
}

func (h *Handlers) RequestApproval(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	v, err := h.svc.RequestApproval(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, v)
}

func (h *Handlers) ApproveVersion(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	v, err := h.svc.ApproveVersion(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, v)
}

type reasonRequest struct {
	Reason string `json:"reason"`
}

func (h *Handlers) RejectVersion(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req reasonRequest
	if err := decodeJSON(r, &req); err != nil || req.Reason == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	v, err := h.svc.RejectVersion(r.Context(), id, req.Reason)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, v)
}

func (h *Handlers) RetireVersion(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req reasonRequest
	if err := decodeJSON(r, &req); err != nil || req.Reason == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	v, err := h.svc.RetireVersion(r.Context(), id, req.Reason)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, v)
}

func (h *Handlers) RevokeVersion(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req reasonRequest
	if err := decodeJSON(r, &req); err != nil || req.Reason == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	v, err := h.svc.RevokeVersion(r.Context(), id, req.Reason)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, v)
}

type capabilityRequest struct {
	CapabilityKey string `json:"capability_key"`
	Description   string `json:"description"`
}

func (h *Handlers) AddCapability(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req capabilityRequest
	if err := decodeJSON(r, &req); err != nil || req.CapabilityKey == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	c, err := h.svc.AddCapability(r.Context(), versionID, req.CapabilityKey, req.Description)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, c)
}

func (h *Handlers) ListCapabilities(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListCapabilities(r.Context(), versionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list capabilities", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type benchmarkRequest struct {
	BenchmarkName string    `json:"benchmark_name"`
	MetricName    string    `json:"metric_name"`
	MetricValue   float64   `json:"metric_value"`
	EvaluatedAt   time.Time `json:"evaluated_at"`
}

func (h *Handlers) AddBenchmark(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req benchmarkRequest
	if err := decodeJSON(r, &req); err != nil || req.BenchmarkName == "" || req.MetricName == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	b, err := h.svc.AddBenchmark(r.Context(), versionID, req.BenchmarkName, req.MetricName, req.MetricValue, req.EvaluatedAt)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, b)
}

func (h *Handlers) ListBenchmarks(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListBenchmarks(r.Context(), versionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list benchmarks", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type safetyEvaluationRequest struct {
	Evaluator   string         `json:"evaluator"`
	Methodology string         `json:"methodology"`
	Result      string         `json:"result"`
	Findings    map[string]any `json:"findings"`
	EvaluatedAt time.Time      `json:"evaluated_at"`
}

func (h *Handlers) AddSafetyEvaluation(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req safetyEvaluationRequest
	if err := decodeJSON(r, &req); err != nil || req.Evaluator == "" || req.Result == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	se, err := h.svc.AddSafetyEvaluation(r.Context(), versionID, req.Evaluator, req.Methodology, req.Result, req.Findings, req.EvaluatedAt)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, se)
}

func (h *Handlers) ListSafetyEvaluations(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListSafetyEvaluations(r.Context(), versionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list safety evaluations", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type deploymentProfileRequest struct {
	ProfileKey           string         `json:"profile_key"`
	Name                 string         `json:"name"`
	ResourceRequirements map[string]any `json:"resource_requirements"`
}

func (h *Handlers) AddDeploymentProfile(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req deploymentProfileRequest
	if err := decodeJSON(r, &req); err != nil || req.ProfileKey == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	p, err := h.svc.AddDeploymentProfile(r.Context(), versionID, req.ProfileKey, req.Name, req.ResourceRequirements)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, p)
}

func (h *Handlers) ListDeploymentProfiles(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListDeploymentProfiles(r.Context(), versionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list deployment profiles", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type linkArtefactRequest struct {
	ArtefactUploadID uuid.UUID `json:"artefact_upload_id"`
	Role             string    `json:"role"`
	ChecksumSHA256   string    `json:"checksum_sha256"`
}

func (h *Handlers) LinkArtefact(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req linkArtefactRequest
	if err := decodeJSON(r, &req); err != nil || req.ArtefactUploadID == uuid.Nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	link, err := h.svc.LinkArtefact(r.Context(), versionID, req.ArtefactUploadID, req.Role, req.ChecksumSHA256)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, link)
}

func (h *Handlers) ListArtefactLinks(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListArtefactLinks(r.Context(), versionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list artefact links", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// marketplace (Milestone 13: AI Model Exchange)
// ---------------------------------------------------------------------

type publishVersionRequest struct {
	PricePerUnit *float64 `json:"price_per_unit"`
	PricingUnit  string   `json:"pricing_unit"`
	Currency     string   `json:"currency"`
}

func (h *Handlers) PublishVersion(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req publishVersionRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	currency := req.Currency
	if currency == "" {
		currency = "USD"
	}
	v, err := h.svc.PublishVersion(r.Context(), id, req.PricePerUnit, req.PricingUnit, currency)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, v)
}

func (h *Handlers) UnpublishVersion(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	v, err := h.svc.UnpublishVersion(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, v)
}

type createAccessGrantRequest struct {
	GranteeTenantID      uuid.UUID `json:"grantee_tenant_id"`
	PricePerUnitOverride *float64  `json:"price_per_unit_override"`
}

func (h *Handlers) CreateAccessGrant(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req createAccessGrantRequest
	if err := decodeJSON(r, &req); err != nil || req.GranteeTenantID == uuid.Nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	g, err := h.svc.CreateAccessGrant(r.Context(), versionID, CreateAccessGrantInput(req))
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, g)
}

func (h *Handlers) ListAccessGrantsForVersion(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListAccessGrantsForVersion(r.Context(), versionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list model access grants", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListMyModelAccessGrants(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListMyModelAccessGrants(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list received model access grants", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) RevokeAccessGrant(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "grantID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.RevokeAccessGrant(r.Context(), id); err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (h *Handlers) ListMarketplaceModelVersions(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListMarketplaceModelVersions(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list marketplace model versions", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) GetMarketplaceModelVersion(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	v, err := h.svc.GetMarketplaceModelVersion(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, v)
}

func (h *Handlers) ListMarketplaceCapabilities(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListMarketplaceCapabilities(r.Context(), versionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list marketplace capabilities", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListMarketplaceBenchmarks(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListMarketplaceBenchmarks(r.Context(), versionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list marketplace benchmarks", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListMarketplaceSafetyEvaluations(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListMarketplaceSafetyEvaluations(r.Context(), versionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list marketplace safety evaluations", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ListMarketplaceDeploymentProfiles(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListMarketplaceDeploymentProfiles(r.Context(), versionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list marketplace deployment profiles", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// provider onboarding (Milestone 13)
// ---------------------------------------------------------------------

type createProviderRequest struct {
	Key     string `json:"key"`
	Name    string `json:"name"`
	Website string `json:"website"`
}

func (h *Handlers) CreateProvider(w http.ResponseWriter, r *http.Request) {
	var req createProviderRequest
	if err := decodeJSON(r, &req); err != nil || req.Key == "" || req.Name == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	p, err := h.svc.CreateProvider(r.Context(), CreateProviderInput(req))
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, p)
}

func (h *Handlers) SuspendProvider(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "providerID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.SuspendProvider(r.Context(), id); err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (h *Handlers) ReactivateProvider(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "providerID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.ReactivateProvider(r.Context(), id); err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
