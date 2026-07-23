package registry

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"time"

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

// parseOptionalUUID parses s into a *uuid.UUID, returning nil (not an
// error) for an empty string -- used for the "exactly one of two optional
// parent IDs" request fields.
func parseOptionalUUID(s string) (*uuid.UUID, error) {
	if s == "" {
		return nil, nil
	}
	id, err := uuid.Parse(s)
	if err != nil {
		return nil, err
	}
	return &id, nil
}

func writeServiceError(w http.ResponseWriter, r *http.Request, logger *slog.Logger, err error, notFoundMsg string) {
	switch {
	case errors.Is(err, ErrUnknownRegion), errors.Is(err, ErrExactlyOneLocation):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, err.Error()))
	case errors.Is(err, ErrParentNotFound):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, notFoundMsg))
	default:
		apierror.WriteJSON(w, r, logger, apierror.Wrap(500, apierror.CodeInternal, "registry operation failed", err))
	}
}

// ---------------------------------------------------------------------
// Jurisdictions / Regions
// ---------------------------------------------------------------------

func (h *Handlers) ListJurisdictions(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListJurisdictions(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list jurisdictions", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type createJurisdictionRequest struct {
	CountryCode string `json:"country_code"`
	Name        string `json:"name"`
	Notes       string `json:"notes"`
}

func (h *Handlers) CreateJurisdiction(w http.ResponseWriter, r *http.Request) {
	var req createJurisdictionRequest
	if err := decodeJSON(r, &req); err != nil || req.CountryCode == "" || req.Name == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	j, err := h.svc.CreateJurisdiction(r.Context(), req.CountryCode, req.Name, req.Notes)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to create jurisdiction", err))
		return
	}
	writeJSON(w, http.StatusCreated, j)
}

func (h *Handlers) ListRegions(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListRegions(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list regions", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type createRegionRequest struct {
	Key            string `json:"key"`
	Name           string `json:"name"`
	JurisdictionID string `json:"jurisdiction_id"`
}

func (h *Handlers) CreateRegion(w http.ResponseWriter, r *http.Request) {
	var req createRegionRequest
	if err := decodeJSON(r, &req); err != nil || req.Key == "" || req.Name == "" || req.JurisdictionID == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	jurisdictionID, err := uuid.Parse(req.JurisdictionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	reg, err := h.svc.CreateRegion(r.Context(), req.Key, req.Name, jurisdictionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to create region", err))
		return
	}
	writeJSON(w, http.StatusCreated, reg)
}

// ---------------------------------------------------------------------
// Operator contracts
// ---------------------------------------------------------------------

func (h *Handlers) ListOperatorContracts(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListOperatorContracts(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list operator contracts", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type createOperatorContractRequest struct {
	ContractReference string  `json:"contract_reference"`
	EffectiveAt       string  `json:"effective_at"`
	TerminatesAt      *string `json:"terminates_at"`
	Notes             string  `json:"notes"`
}

func (h *Handlers) CreateOperatorContract(w http.ResponseWriter, r *http.Request) {
	var req createOperatorContractRequest
	if err := decodeJSON(r, &req); err != nil || req.ContractReference == "" || req.EffectiveAt == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	effectiveAt, err := time.Parse(time.RFC3339, req.EffectiveAt)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var terminatesAt *time.Time
	if req.TerminatesAt != nil && *req.TerminatesAt != "" {
		t, err := time.Parse(time.RFC3339, *req.TerminatesAt)
		if err != nil {
			apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
			return
		}
		terminatesAt = &t
	}
	oc, err := h.svc.CreateOperatorContract(r.Context(), req.ContractReference, effectiveAt, terminatesAt, req.Notes)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to create operator contract", err))
		return
	}
	writeJSON(w, http.StatusCreated, oc)
}

// ---------------------------------------------------------------------
// Data centres / Edge sites
// ---------------------------------------------------------------------

func (h *Handlers) ListDataCentres(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListDataCentres(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list data centres", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type createLocationRequest struct {
	RegionID string `json:"region_id"`
	Name     string `json:"name"`
	Locality string `json:"locality"`
}

func (h *Handlers) CreateDataCentre(w http.ResponseWriter, r *http.Request) {
	var req createLocationRequest
	if err := decodeJSON(r, &req); err != nil || req.RegionID == "" || req.Name == "" || req.Locality == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	regionID, err := uuid.Parse(req.RegionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	dc, err := h.svc.CreateDataCentre(r.Context(), regionID, req.Name, req.Locality)
	if err != nil {
		writeServiceError(w, r, h.logger, err, "region does not exist")
		return
	}
	writeJSON(w, http.StatusCreated, dc)
}

func (h *Handlers) ListEdgeSites(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListEdgeSites(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list edge sites", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) CreateEdgeSite(w http.ResponseWriter, r *http.Request) {
	var req createLocationRequest
	if err := decodeJSON(r, &req); err != nil || req.RegionID == "" || req.Name == "" || req.Locality == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	regionID, err := uuid.Parse(req.RegionID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	es, err := h.svc.CreateEdgeSite(r.Context(), regionID, req.Name, req.Locality)
	if err != nil {
		writeServiceError(w, r, h.logger, err, "region does not exist")
		return
	}
	writeJSON(w, http.StatusCreated, es)
}

// ---------------------------------------------------------------------
// Clusters / Node pools / Accelerators
// ---------------------------------------------------------------------

func (h *Handlers) ListClusters(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListClusters(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list clusters", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type createClusterRequest struct {
	DataCentreID      string `json:"data_centre_id"`
	EdgeSiteID        string `json:"edge_site_id"`
	Name              string `json:"name"`
	KubernetesVersion string `json:"kubernetes_version"`
}

func (h *Handlers) CreateCluster(w http.ResponseWriter, r *http.Request) {
	var req createClusterRequest
	if err := decodeJSON(r, &req); err != nil || req.Name == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	dataCentreID, err := parseOptionalUUID(req.DataCentreID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	edgeSiteID, err := parseOptionalUUID(req.EdgeSiteID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	cl, err := h.svc.CreateCluster(r.Context(), dataCentreID, edgeSiteID, req.Name, req.KubernetesVersion)
	if err != nil {
		writeServiceError(w, r, h.logger, err, "data centre or edge site does not exist for this operator")
		return
	}
	writeJSON(w, http.StatusCreated, cl)
}

func (h *Handlers) ListNodePools(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListNodePools(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list node pools", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type createNodePoolRequest struct {
	ClusterID       string `json:"cluster_id"`
	Name            string `json:"name"`
	NodeCount       int    `json:"node_count"`
	CPUCoresPerNode int    `json:"cpu_cores_per_node"`
	MemoryGBPerNode int    `json:"memory_gb_per_node"`
}

func (h *Handlers) CreateNodePool(w http.ResponseWriter, r *http.Request) {
	var req createNodePoolRequest
	if err := decodeJSON(r, &req); err != nil || req.ClusterID == "" || req.Name == "" || req.CPUCoresPerNode <= 0 || req.MemoryGBPerNode <= 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	clusterID, err := uuid.Parse(req.ClusterID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	np, err := h.svc.CreateNodePool(r.Context(), clusterID, req.Name, req.NodeCount, req.CPUCoresPerNode, req.MemoryGBPerNode)
	if err != nil {
		writeServiceError(w, r, h.logger, err, "cluster does not exist for this operator")
		return
	}
	writeJSON(w, http.StatusCreated, np)
}

func (h *Handlers) ListAccelerators(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListAccelerators(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list accelerators", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type createAcceleratorRequest struct {
	NodePoolID      string `json:"node_pool_id"`
	AcceleratorType string `json:"accelerator_type"`
	CountPerNode    int    `json:"count_per_node"`
	MemoryGB        int    `json:"memory_gb"`
}

func (h *Handlers) CreateAccelerator(w http.ResponseWriter, r *http.Request) {
	var req createAcceleratorRequest
	if err := decodeJSON(r, &req); err != nil || req.NodePoolID == "" || req.AcceleratorType == "" || req.CountPerNode <= 0 || req.MemoryGB <= 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	nodePoolID, err := uuid.Parse(req.NodePoolID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	a, err := h.svc.CreateAccelerator(r.Context(), nodePoolID, req.AcceleratorType, req.CountPerNode, req.MemoryGB)
	if err != nil {
		writeServiceError(w, r, h.logger, err, "node pool does not exist for this operator")
		return
	}
	writeJSON(w, http.StatusCreated, a)
}

// ---------------------------------------------------------------------
// Storage pools / Network capabilities
// ---------------------------------------------------------------------

func (h *Handlers) ListStoragePools(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListStoragePools(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list storage pools", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type createStoragePoolRequest struct {
	DataCentreID    string `json:"data_centre_id"`
	EdgeSiteID      string `json:"edge_site_id"`
	Name            string `json:"name"`
	StorageType     string `json:"storage_type"`
	CapacityGB      int64  `json:"capacity_gb"`
	EncryptedAtRest *bool  `json:"encrypted_at_rest"`
}

func (h *Handlers) CreateStoragePool(w http.ResponseWriter, r *http.Request) {
	var req createStoragePoolRequest
	if err := decodeJSON(r, &req); err != nil || req.Name == "" || req.StorageType == "" || req.CapacityGB <= 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	dataCentreID, err := parseOptionalUUID(req.DataCentreID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	edgeSiteID, err := parseOptionalUUID(req.EdgeSiteID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	encryptedAtRest := true
	if req.EncryptedAtRest != nil {
		encryptedAtRest = *req.EncryptedAtRest
	}
	sp, err := h.svc.CreateStoragePool(r.Context(), dataCentreID, edgeSiteID, req.Name, req.StorageType, req.CapacityGB, encryptedAtRest)
	if err != nil {
		writeServiceError(w, r, h.logger, err, "data centre or edge site does not exist for this operator")
		return
	}
	writeJSON(w, http.StatusCreated, sp)
}

func (h *Handlers) ListNetworkCapabilities(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListNetworkCapabilities(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list network capabilities", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type createNetworkCapabilityRequest struct {
	DataCentreID       string   `json:"data_centre_id"`
	EdgeSiteID         string   `json:"edge_site_id"`
	CapabilityType     string   `json:"capability_type"`
	BandwidthGbps      float64  `json:"bandwidth_gbps"`
	EstimatedLatencyMs *float64 `json:"estimated_latency_ms"`
}

func (h *Handlers) CreateNetworkCapability(w http.ResponseWriter, r *http.Request) {
	var req createNetworkCapabilityRequest
	if err := decodeJSON(r, &req); err != nil || req.CapabilityType == "" || req.BandwidthGbps <= 0 {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	dataCentreID, err := parseOptionalUUID(req.DataCentreID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	edgeSiteID, err := parseOptionalUUID(req.EdgeSiteID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	nc, err := h.svc.CreateNetworkCapability(r.Context(), dataCentreID, edgeSiteID, req.CapabilityType, req.BandwidthGbps, req.EstimatedLatencyMs)
	if err != nil {
		writeServiceError(w, r, h.logger, err, "data centre or edge site does not exist for this operator")
		return
	}
	writeJSON(w, http.StatusCreated, nc)
}
