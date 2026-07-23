package registry

import (
	"context"
	"errors"
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
)

var (
	ErrUnknownRegion      = errors.New("unknown region")
	ErrParentNotFound     = errors.New("referenced data centre, edge site, cluster, or node pool does not exist for this operator")
	ErrExactlyOneLocation = errors.New("exactly one of data_centre_id or edge_site_id must be set")
)

type Service struct {
	store *dbpkg.Store
}

func NewService(store *dbpkg.Store) *Service {
	return &Service{store: store}
}

func actorFromContext(ctx context.Context) *uuid.UUID {
	if authUser, ok := httpserver.AuthUser(ctx); ok {
		return &authUser.UserID
	}
	return nil
}

// ---------------------------------------------------------------------
// Jurisdictions / Regions -- global, read by any authenticated user,
// written only under platform.regions.manage.
// ---------------------------------------------------------------------

func (s *Service) ListJurisdictions(ctx context.Context) ([]Jurisdiction, error) {
	return listJurisdictions(ctx, s.store.Pool)
}

func (s *Service) CreateJurisdiction(ctx context.Context, countryCode, name, notes string) (Jurisdiction, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	j, err := createJurisdiction(ctx, scopedTx.Tx, countryCode, name, notes)
	if err != nil {
		return Jurisdiction{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actorFromContext(ctx),
		ScopeType:   audit.ScopePlatform,
		Action:      "registry.jurisdiction_created",
		TargetType:  "jurisdiction",
		TargetID:    &j.ID,
		Evidence:    map[string]any{"country_code": countryCode, "name": name},
	}); err != nil {
		return Jurisdiction{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Jurisdiction{}, err
	}
	return j, nil
}

func (s *Service) ListRegions(ctx context.Context) ([]Region, error) {
	return listRegions(ctx, s.store.Pool)
}

func (s *Service) CreateRegion(ctx context.Context, key, name string, jurisdictionID uuid.UUID) (Region, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	r, err := createRegion(ctx, scopedTx.Tx, key, name, jurisdictionID)
	if err != nil {
		return Region{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actorFromContext(ctx),
		ScopeType:   audit.ScopePlatform,
		Action:      "registry.region_created",
		TargetType:  "region",
		TargetID:    &r.ID,
		Evidence:    map[string]any{"key": key, "name": name},
	}); err != nil {
		return Region{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Region{}, err
	}
	return r, nil
}

// ---------------------------------------------------------------------
// Operator contracts
// ---------------------------------------------------------------------

func (s *Service) ListOperatorContracts(ctx context.Context) ([]OperatorContract, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listOperatorContracts(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) CreateOperatorContract(ctx context.Context, contractRef string, effectiveAt time.Time, terminatesAt *time.Time, notes string) (OperatorContract, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	oc, err := createOperatorContract(ctx, scopedTx.Tx, *scope.OperatorID, contractRef, effectiveAt, terminatesAt, notes)
	if err != nil {
		return OperatorContract{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actorFromContext(ctx),
		ScopeType:   audit.ScopeOperator,
		ScopeID:     scope.OperatorID,
		Action:      "registry.operator_contract_created",
		TargetType:  "operator_contract",
		TargetID:    &oc.ID,
		Evidence:    map[string]any{"contract_reference": contractRef},
	}); err != nil {
		return OperatorContract{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return OperatorContract{}, err
	}
	return oc, nil
}

// ---------------------------------------------------------------------
// Data centres / Edge sites
// ---------------------------------------------------------------------

func (s *Service) ListDataCentres(ctx context.Context) ([]DataCentre, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listDataCentres(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) CreateDataCentre(ctx context.Context, regionID uuid.UUID, name, locality string) (DataCentre, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	ok, err := regionExists(ctx, scopedTx.Tx, regionID)
	if err != nil {
		return DataCentre{}, err
	}
	if !ok {
		return DataCentre{}, ErrUnknownRegion
	}

	dc, err := createDataCentre(ctx, scopedTx.Tx, *scope.OperatorID, regionID, name, locality)
	if err != nil {
		return DataCentre{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actorFromContext(ctx),
		ScopeType:   audit.ScopeOperator,
		ScopeID:     scope.OperatorID,
		Action:      "registry.data_centre_created",
		TargetType:  "data_centre",
		TargetID:    &dc.ID,
		Evidence:    map[string]any{"name": name, "region_id": regionID},
	}); err != nil {
		return DataCentre{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return DataCentre{}, err
	}
	return dc, nil
}

func (s *Service) ListEdgeSites(ctx context.Context) ([]EdgeSite, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listEdgeSites(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) CreateEdgeSite(ctx context.Context, regionID uuid.UUID, name, locality string) (EdgeSite, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	ok, err := regionExists(ctx, scopedTx.Tx, regionID)
	if err != nil {
		return EdgeSite{}, err
	}
	if !ok {
		return EdgeSite{}, ErrUnknownRegion
	}

	es, err := createEdgeSite(ctx, scopedTx.Tx, *scope.OperatorID, regionID, name, locality)
	if err != nil {
		return EdgeSite{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actorFromContext(ctx),
		ScopeType:   audit.ScopeOperator,
		ScopeID:     scope.OperatorID,
		Action:      "registry.edge_site_created",
		TargetType:  "edge_site",
		TargetID:    &es.ID,
		Evidence:    map[string]any{"name": name, "region_id": regionID},
	}); err != nil {
		return EdgeSite{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return EdgeSite{}, err
	}
	return es, nil
}

// ---------------------------------------------------------------------
// Clusters / Node pools / Accelerators
// ---------------------------------------------------------------------

// resolveOneLocation validates that exactly one of dataCentreID/edgeSiteID
// is set and that it belongs to the caller's own operator -- never trusting
// a client-supplied parent location ID without checking ownership first,
// even though RLS would also reject a cross-operator row if this check were
// skipped (defense in depth, not the sole control).
func (s *Service) resolveOneLocation(ctx context.Context, c conn, operatorID uuid.UUID, dataCentreID, edgeSiteID *uuid.UUID) error {
	if (dataCentreID == nil) == (edgeSiteID == nil) {
		return ErrExactlyOneLocation
	}
	if dataCentreID != nil {
		ok, err := dataCentreBelongsToOperator(ctx, c, *dataCentreID, operatorID)
		if err != nil {
			return err
		}
		if !ok {
			return ErrParentNotFound
		}
		return nil
	}
	ok, err := edgeSiteBelongsToOperator(ctx, c, *edgeSiteID, operatorID)
	if err != nil {
		return err
	}
	if !ok {
		return ErrParentNotFound
	}
	return nil
}

func (s *Service) ListClusters(ctx context.Context) ([]Cluster, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listClusters(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) CreateCluster(ctx context.Context, dataCentreID, edgeSiteID *uuid.UUID, name, k8sVersion string) (Cluster, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	if err := s.resolveOneLocation(ctx, scopedTx.Tx, *scope.OperatorID, dataCentreID, edgeSiteID); err != nil {
		return Cluster{}, err
	}

	cl, err := createCluster(ctx, scopedTx.Tx, *scope.OperatorID, dataCentreID, edgeSiteID, name, k8sVersion)
	if err != nil {
		return Cluster{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actorFromContext(ctx),
		ScopeType:   audit.ScopeOperator,
		ScopeID:     scope.OperatorID,
		Action:      "registry.cluster_created",
		TargetType:  "cluster",
		TargetID:    &cl.ID,
		Evidence:    map[string]any{"name": name},
	}); err != nil {
		return Cluster{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Cluster{}, err
	}
	return cl, nil
}

func (s *Service) ListNodePools(ctx context.Context) ([]NodePool, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listNodePools(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) CreateNodePool(ctx context.Context, clusterID uuid.UUID, name string, nodeCount, cpuCores, memoryGB int) (NodePool, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	ok, err := clusterBelongsToOperator(ctx, scopedTx.Tx, clusterID, *scope.OperatorID)
	if err != nil {
		return NodePool{}, err
	}
	if !ok {
		return NodePool{}, ErrParentNotFound
	}

	np, err := createNodePool(ctx, scopedTx.Tx, *scope.OperatorID, clusterID, name, nodeCount, cpuCores, memoryGB)
	if err != nil {
		return NodePool{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actorFromContext(ctx),
		ScopeType:   audit.ScopeOperator,
		ScopeID:     scope.OperatorID,
		Action:      "registry.node_pool_created",
		TargetType:  "node_pool",
		TargetID:    &np.ID,
		Evidence:    map[string]any{"name": name, "node_count": nodeCount},
	}); err != nil {
		return NodePool{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return NodePool{}, err
	}
	return np, nil
}

func (s *Service) ListAccelerators(ctx context.Context) ([]Accelerator, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listAccelerators(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) CreateAccelerator(ctx context.Context, nodePoolID uuid.UUID, acceleratorType string, countPerNode, memoryGB int) (Accelerator, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	ok, err := nodePoolBelongsToOperator(ctx, scopedTx.Tx, nodePoolID, *scope.OperatorID)
	if err != nil {
		return Accelerator{}, err
	}
	if !ok {
		return Accelerator{}, ErrParentNotFound
	}

	a, err := createAccelerator(ctx, scopedTx.Tx, *scope.OperatorID, nodePoolID, acceleratorType, countPerNode, memoryGB)
	if err != nil {
		return Accelerator{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actorFromContext(ctx),
		ScopeType:   audit.ScopeOperator,
		ScopeID:     scope.OperatorID,
		Action:      "registry.accelerator_created",
		TargetType:  "accelerator",
		TargetID:    &a.ID,
		Evidence:    map[string]any{"accelerator_type": acceleratorType, "count_per_node": countPerNode},
	}); err != nil {
		return Accelerator{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Accelerator{}, err
	}
	return a, nil
}

// ---------------------------------------------------------------------
// Storage pools / Network capabilities
// ---------------------------------------------------------------------

func (s *Service) ListStoragePools(ctx context.Context) ([]StoragePool, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listStoragePools(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) CreateStoragePool(ctx context.Context, dataCentreID, edgeSiteID *uuid.UUID, name, storageType string, capacityGB int64, encryptedAtRest bool) (StoragePool, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	if err := s.resolveOneLocation(ctx, scopedTx.Tx, *scope.OperatorID, dataCentreID, edgeSiteID); err != nil {
		return StoragePool{}, err
	}

	sp, err := createStoragePool(ctx, scopedTx.Tx, *scope.OperatorID, dataCentreID, edgeSiteID, name, storageType, capacityGB, encryptedAtRest)
	if err != nil {
		return StoragePool{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actorFromContext(ctx),
		ScopeType:   audit.ScopeOperator,
		ScopeID:     scope.OperatorID,
		Action:      "registry.storage_pool_created",
		TargetType:  "storage_pool",
		TargetID:    &sp.ID,
		Evidence:    map[string]any{"name": name, "storage_type": storageType, "capacity_gb": capacityGB},
	}); err != nil {
		return StoragePool{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return StoragePool{}, err
	}
	return sp, nil
}

func (s *Service) ListNetworkCapabilities(ctx context.Context) ([]NetworkCapability, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listNetworkCapabilities(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) CreateNetworkCapability(ctx context.Context, dataCentreID, edgeSiteID *uuid.UUID, capabilityType string, bandwidthGbps float64, estimatedLatencyMs *float64) (NetworkCapability, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	if err := s.resolveOneLocation(ctx, scopedTx.Tx, *scope.OperatorID, dataCentreID, edgeSiteID); err != nil {
		return NetworkCapability{}, err
	}

	nc, err := createNetworkCapability(ctx, scopedTx.Tx, *scope.OperatorID, dataCentreID, edgeSiteID, capabilityType, bandwidthGbps, estimatedLatencyMs)
	if err != nil {
		return NetworkCapability{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actorFromContext(ctx),
		ScopeType:   audit.ScopeOperator,
		ScopeID:     scope.OperatorID,
		Action:      "registry.network_capability_created",
		TargetType:  "network_capability",
		TargetID:    &nc.ID,
		Evidence:    map[string]any{"capability_type": capabilityType, "bandwidth_gbps": bandwidthGbps},
	}); err != nil {
		return NetworkCapability{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return NetworkCapability{}, err
	}
	return nc, nil
}
