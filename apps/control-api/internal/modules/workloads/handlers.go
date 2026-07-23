package workloads

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
	case errors.Is(err, ErrWorkloadNotFound), errors.Is(err, ErrVersionNotFound):
		apierror.WriteJSON(w, r, logger, apierror.ErrNotFound)
	case errors.Is(err, ErrWorkloadKeyExists):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	case errors.Is(err, ErrNotADraft), errors.Is(err, ErrNotPendingPublish), errors.Is(err, ErrNotPublished):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	case errors.Is(err, ErrCannotSelfApprove):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusForbidden, apierror.CodeForbidden, err.Error()))
	case errors.Is(err, ErrImageNotApproved), errors.Is(err, ErrModelVersionNotApproved), errors.Is(err, ErrModelGeographyMismatch):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, err.Error()))
	default:
		apierror.WriteJSON(w, r, logger, apierror.Wrap(500, apierror.CodeInternal, "workload registry operation failed", err))
	}
}

func (h *Handlers) ListWorkloads(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListWorkloads(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list workloads", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) GetWorkload(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "workloadID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	wl, err := h.svc.GetWorkload(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, wl)
}

type createWorkloadRequest struct {
	WorkloadKey  string `json:"workload_key"`
	WorkloadType string `json:"workload_type"`
	Name         string `json:"name"`
	Description  string `json:"description"`
}

func (h *Handlers) CreateWorkload(w http.ResponseWriter, r *http.Request) {
	var req createWorkloadRequest
	if err := decodeJSON(r, &req); err != nil || req.WorkloadKey == "" || req.WorkloadType == "" || req.Name == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	wl, err := h.svc.CreateWorkload(r.Context(), req.WorkloadKey, req.WorkloadType, req.Name, req.Description)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, wl)
}

func (h *Handlers) RetireWorkload(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "workloadID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	wl, err := h.svc.RetireWorkload(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, wl)
}

func (h *Handlers) ListVersions(w http.ResponseWriter, r *http.Request) {
	workloadID, err := uuid.Parse(chi.URLParam(r, "workloadID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListVersions(r.Context(), workloadID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list workload versions", err))
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
	ContainerImageID           *uuid.UUID     `json:"container_image_id"`
	ModelVersionID             *uuid.UUID     `json:"model_version_id"`
	ResourceRequirements       map[string]any `json:"resource_requirements"`
	NetworkRequirements        map[string]any `json:"network_requirements"`
	StorageRequirements        map[string]any `json:"storage_requirements"`
	SecurityRequirements       map[string]any `json:"security_requirements"`
	ResidencyRequirements      map[string]any `json:"residency_requirements"`
	ScalingPolicy              map[string]any `json:"scaling_policy"`
	RetentionPolicy            map[string]any `json:"retention_policy"`
	DeploymentApprovalRequired bool           `json:"deployment_approval_required"`
}

func (r versionInputRequest) toInput() VersionInput {
	return VersionInput(r)
}

func (h *Handlers) CreateDraftVersion(w http.ResponseWriter, r *http.Request) {
	workloadID, err := uuid.Parse(chi.URLParam(r, "workloadID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req versionInputRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	v, err := h.svc.CreateDraftVersion(r.Context(), workloadID, req.toInput())
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
	if err := decodeJSON(r, &req); err != nil {
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

func (h *Handlers) RequestPublish(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	v, err := h.svc.RequestPublish(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, v)
}

func (h *Handlers) ApprovePublish(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	v, err := h.svc.ApprovePublish(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, v)
}

func (h *Handlers) DeprecateVersion(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	v, err := h.svc.DeprecateVersion(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, v)
}

type reasonRequest struct {
	Reason string `json:"reason"`
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

type addComponentRequest struct {
	ComponentKey     string         `json:"component_key"`
	Name             string         `json:"name"`
	ContainerImageID uuid.UUID      `json:"container_image_id"`
	Command          []string       `json:"command"`
	Args             []string       `json:"args"`
	Env              map[string]any `json:"env"`
	IsPrimary        bool           `json:"is_primary"`
}

func (h *Handlers) AddComponent(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req addComponentRequest
	if err := decodeJSON(r, &req); err != nil || req.ComponentKey == "" || req.ContainerImageID == uuid.Nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	comp, err := h.svc.AddComponent(r.Context(), versionID, req.ContainerImageID, req.ComponentKey, req.Name, req.Command, req.Args, req.Env, req.IsPrimary)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, comp)
}

func (h *Handlers) ListComponents(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListComponents(r.Context(), versionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list components", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type addHealthCheckRequest struct {
	CheckType        string   `json:"check_type"`
	Path             string   `json:"path"`
	Port             *int     `json:"port"`
	Command          []string `json:"command"`
	IntervalSeconds  int      `json:"interval_seconds"`
	TimeoutSeconds   int      `json:"timeout_seconds"`
	FailureThreshold int      `json:"failure_threshold"`
}

func (h *Handlers) AddHealthCheck(w http.ResponseWriter, r *http.Request) {
	componentID, err := uuid.Parse(chi.URLParam(r, "componentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req addHealthCheckRequest
	if err := decodeJSON(r, &req); err != nil || req.CheckType == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if req.IntervalSeconds <= 0 {
		req.IntervalSeconds = 10
	}
	if req.TimeoutSeconds <= 0 {
		req.TimeoutSeconds = 5
	}
	if req.FailureThreshold <= 0 {
		req.FailureThreshold = 3
	}
	hc, err := h.svc.AddHealthCheck(r.Context(), componentID, req.CheckType, req.Path, req.Port, req.Command, req.IntervalSeconds, req.TimeoutSeconds, req.FailureThreshold)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, hc)
}

func (h *Handlers) ListHealthChecks(w http.ResponseWriter, r *http.Request) {
	componentID, err := uuid.Parse(chi.URLParam(r, "componentID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListHealthChecks(r.Context(), componentID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list health checks", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type linkArtefactRequest struct {
	ArtefactUploadID uuid.UUID `json:"artefact_upload_id"`
	Role             string    `json:"role"`
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
	link, err := h.svc.LinkArtefact(r.Context(), versionID, req.ArtefactUploadID, req.Role)
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

type linkSBOMRequest struct {
	SBOMID uuid.UUID `json:"sbom_id"`
}

func (h *Handlers) LinkSBOM(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req linkSBOMRequest
	if err := decodeJSON(r, &req); err != nil || req.SBOMID == uuid.Nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	link, err := h.svc.LinkSBOM(r.Context(), versionID, req.SBOMID)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, link)
}

func (h *Handlers) ListSBOMLinks(w http.ResponseWriter, r *http.Request) {
	versionID, err := uuid.Parse(chi.URLParam(r, "versionID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListSBOMLinks(r.Context(), versionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list sbom links", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}
