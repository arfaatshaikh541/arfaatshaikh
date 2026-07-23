package registry

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

// conn is satisfied by both *pgxpool.Pool and pgx.Tx, matching the pattern
// every other module's repository layer uses.
type conn interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

// ---------------------------------------------------------------------
// Jurisdictions / Regions -- global reference data, no operator scope.
// ---------------------------------------------------------------------

func createJurisdiction(ctx context.Context, c conn, countryCode, name, notes string) (Jurisdiction, error) {
	var j Jurisdiction
	err := c.QueryRow(ctx, `
		INSERT INTO jurisdictions (country_code, name, notes)
		VALUES ($1, $2, $3)
		RETURNING id, country_code, name, notes, created_at
	`, countryCode, name, notes).Scan(&j.ID, &j.CountryCode, &j.Name, &j.Notes, &j.CreatedAt)
	if err != nil {
		return Jurisdiction{}, fmt.Errorf("insert jurisdiction: %w", err)
	}
	return j, nil
}

func listJurisdictions(ctx context.Context, c conn) ([]Jurisdiction, error) {
	rows, err := c.Query(ctx, `SELECT id, country_code, name, notes, created_at FROM jurisdictions ORDER BY name`)
	if err != nil {
		return nil, fmt.Errorf("list jurisdictions: %w", err)
	}
	defer rows.Close()

	var out []Jurisdiction
	for rows.Next() {
		var j Jurisdiction
		if err := rows.Scan(&j.ID, &j.CountryCode, &j.Name, &j.Notes, &j.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan jurisdiction: %w", err)
		}
		out = append(out, j)
	}
	return out, rows.Err()
}

func createRegion(ctx context.Context, c conn, key, name string, jurisdictionID uuid.UUID) (Region, error) {
	var r Region
	err := c.QueryRow(ctx, `
		INSERT INTO regions (key, name, jurisdiction_id)
		VALUES ($1, $2, $3)
		RETURNING id, key, name, jurisdiction_id, status, created_at
	`, key, name, jurisdictionID).Scan(&r.ID, &r.Key, &r.Name, &r.JurisdictionID, &r.Status, &r.CreatedAt)
	if err != nil {
		return Region{}, fmt.Errorf("insert region: %w", err)
	}
	return r, nil
}

func listRegions(ctx context.Context, c conn) ([]Region, error) {
	rows, err := c.Query(ctx, `SELECT id, key, name, jurisdiction_id, status, created_at FROM regions ORDER BY key`)
	if err != nil {
		return nil, fmt.Errorf("list regions: %w", err)
	}
	defer rows.Close()

	var out []Region
	for rows.Next() {
		var r Region
		if err := rows.Scan(&r.ID, &r.Key, &r.Name, &r.JurisdictionID, &r.Status, &r.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan region: %w", err)
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func regionExists(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	var exists bool
	err := c.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM regions WHERE id = $1)`, id).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("check region exists: %w", err)
	}
	return exists, nil
}

// ---------------------------------------------------------------------
// Operator contracts
// ---------------------------------------------------------------------

func createOperatorContract(ctx context.Context, c conn, operatorID uuid.UUID, contractRef string, effectiveAt time.Time, terminatesAt *time.Time, notes string) (OperatorContract, error) {
	var oc OperatorContract
	err := c.QueryRow(ctx, `
		INSERT INTO operator_contracts (operator_id, contract_reference, effective_at, terminates_at, notes)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, operator_id, contract_reference, effective_at, terminates_at, status, notes, created_at, updated_at
	`, operatorID, contractRef, effectiveAt, terminatesAt, notes).Scan(
		&oc.ID, &oc.OperatorID, &oc.ContractReference, &oc.EffectiveAt, &oc.TerminatesAt, &oc.Status, &oc.Notes, &oc.CreatedAt, &oc.UpdatedAt)
	if err != nil {
		return OperatorContract{}, fmt.Errorf("insert operator contract: %w", err)
	}
	return oc, nil
}

func listOperatorContracts(ctx context.Context, c conn, operatorID uuid.UUID) ([]OperatorContract, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, contract_reference, effective_at, terminates_at, status, notes, created_at, updated_at
		FROM operator_contracts WHERE operator_id = $1 ORDER BY effective_at DESC
	`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list operator contracts: %w", err)
	}
	defer rows.Close()

	var out []OperatorContract
	for rows.Next() {
		var oc OperatorContract
		if err := rows.Scan(&oc.ID, &oc.OperatorID, &oc.ContractReference, &oc.EffectiveAt, &oc.TerminatesAt, &oc.Status, &oc.Notes, &oc.CreatedAt, &oc.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan operator contract: %w", err)
		}
		out = append(out, oc)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Data centres / Edge sites
// ---------------------------------------------------------------------

func createDataCentre(ctx context.Context, c conn, operatorID, regionID uuid.UUID, name, locality string) (DataCentre, error) {
	var dc DataCentre
	err := c.QueryRow(ctx, `
		INSERT INTO data_centres (operator_id, region_id, name, locality)
		VALUES ($1, $2, $3, $4)
		RETURNING id, operator_id, region_id, name, locality, status, created_at, updated_at
	`, operatorID, regionID, name, locality).Scan(&dc.ID, &dc.OperatorID, &dc.RegionID, &dc.Name, &dc.Locality, &dc.Status, &dc.CreatedAt, &dc.UpdatedAt)
	if err != nil {
		return DataCentre{}, fmt.Errorf("insert data centre: %w", err)
	}
	return dc, nil
}

func listDataCentres(ctx context.Context, c conn, operatorID uuid.UUID) ([]DataCentre, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, region_id, name, locality, status, created_at, updated_at
		FROM data_centres WHERE operator_id = $1 ORDER BY name
	`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list data centres: %w", err)
	}
	defer rows.Close()

	var out []DataCentre
	for rows.Next() {
		var dc DataCentre
		if err := rows.Scan(&dc.ID, &dc.OperatorID, &dc.RegionID, &dc.Name, &dc.Locality, &dc.Status, &dc.CreatedAt, &dc.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan data centre: %w", err)
		}
		out = append(out, dc)
	}
	return out, rows.Err()
}

func dataCentreBelongsToOperator(ctx context.Context, c conn, id, operatorID uuid.UUID) (bool, error) {
	var exists bool
	err := c.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM data_centres WHERE id = $1 AND operator_id = $2)`, id, operatorID).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("check data centre ownership: %w", err)
	}
	return exists, nil
}

func createEdgeSite(ctx context.Context, c conn, operatorID, regionID uuid.UUID, name, locality string) (EdgeSite, error) {
	var es EdgeSite
	err := c.QueryRow(ctx, `
		INSERT INTO edge_sites (operator_id, region_id, name, locality)
		VALUES ($1, $2, $3, $4)
		RETURNING id, operator_id, region_id, name, locality, status, created_at, updated_at
	`, operatorID, regionID, name, locality).Scan(&es.ID, &es.OperatorID, &es.RegionID, &es.Name, &es.Locality, &es.Status, &es.CreatedAt, &es.UpdatedAt)
	if err != nil {
		return EdgeSite{}, fmt.Errorf("insert edge site: %w", err)
	}
	return es, nil
}

func listEdgeSites(ctx context.Context, c conn, operatorID uuid.UUID) ([]EdgeSite, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, region_id, name, locality, status, created_at, updated_at
		FROM edge_sites WHERE operator_id = $1 ORDER BY name
	`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list edge sites: %w", err)
	}
	defer rows.Close()

	var out []EdgeSite
	for rows.Next() {
		var es EdgeSite
		if err := rows.Scan(&es.ID, &es.OperatorID, &es.RegionID, &es.Name, &es.Locality, &es.Status, &es.CreatedAt, &es.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan edge site: %w", err)
		}
		out = append(out, es)
	}
	return out, rows.Err()
}

func edgeSiteBelongsToOperator(ctx context.Context, c conn, id, operatorID uuid.UUID) (bool, error) {
	var exists bool
	err := c.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM edge_sites WHERE id = $1 AND operator_id = $2)`, id, operatorID).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("check edge site ownership: %w", err)
	}
	return exists, nil
}

// ---------------------------------------------------------------------
// Clusters / Node pools / Accelerators
// ---------------------------------------------------------------------

func createCluster(ctx context.Context, c conn, operatorID uuid.UUID, dataCentreID, edgeSiteID *uuid.UUID, name, k8sVersion string) (Cluster, error) {
	var cl Cluster
	err := c.QueryRow(ctx, `
		INSERT INTO clusters (operator_id, data_centre_id, edge_site_id, name, kubernetes_version)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, operator_id, data_centre_id, edge_site_id, name, kubernetes_version, status, created_at, updated_at
	`, operatorID, dataCentreID, edgeSiteID, name, k8sVersion).Scan(
		&cl.ID, &cl.OperatorID, &cl.DataCentreID, &cl.EdgeSiteID, &cl.Name, &cl.KubernetesVersion, &cl.Status, &cl.CreatedAt, &cl.UpdatedAt)
	if err != nil {
		return Cluster{}, fmt.Errorf("insert cluster: %w", err)
	}
	return cl, nil
}

func listClusters(ctx context.Context, c conn, operatorID uuid.UUID) ([]Cluster, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, data_centre_id, edge_site_id, name, kubernetes_version, status, created_at, updated_at
		FROM clusters WHERE operator_id = $1 ORDER BY name
	`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list clusters: %w", err)
	}
	defer rows.Close()

	var out []Cluster
	for rows.Next() {
		var cl Cluster
		if err := rows.Scan(&cl.ID, &cl.OperatorID, &cl.DataCentreID, &cl.EdgeSiteID, &cl.Name, &cl.KubernetesVersion, &cl.Status, &cl.CreatedAt, &cl.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan cluster: %w", err)
		}
		out = append(out, cl)
	}
	return out, rows.Err()
}

// ClusterBelongsToOperator is exported for the agents module, which must
// verify a capacity snapshot's claimed cluster_id actually belongs to the
// submitting agent's own operator before accepting the snapshot.
func ClusterBelongsToOperator(ctx context.Context, c conn, id, operatorID uuid.UUID) (bool, error) {
	return clusterBelongsToOperator(ctx, c, id, operatorID)
}

func clusterBelongsToOperator(ctx context.Context, c conn, id, operatorID uuid.UUID) (bool, error) {
	var exists bool
	err := c.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM clusters WHERE id = $1 AND operator_id = $2)`, id, operatorID).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("check cluster ownership: %w", err)
	}
	return exists, nil
}

func createNodePool(ctx context.Context, c conn, operatorID, clusterID uuid.UUID, name string, nodeCount, cpuCores, memoryGB int) (NodePool, error) {
	var np NodePool
	err := c.QueryRow(ctx, `
		INSERT INTO node_pools (operator_id, cluster_id, name, node_count, cpu_cores_per_node, memory_gb_per_node)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, operator_id, cluster_id, name, node_count, cpu_cores_per_node, memory_gb_per_node, status, created_at, updated_at
	`, operatorID, clusterID, name, nodeCount, cpuCores, memoryGB).Scan(
		&np.ID, &np.OperatorID, &np.ClusterID, &np.Name, &np.NodeCount, &np.CPUCoresPerNode, &np.MemoryGBPerNode, &np.Status, &np.CreatedAt, &np.UpdatedAt)
	if err != nil {
		return NodePool{}, fmt.Errorf("insert node pool: %w", err)
	}
	return np, nil
}

func listNodePools(ctx context.Context, c conn, operatorID uuid.UUID) ([]NodePool, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, cluster_id, name, node_count, cpu_cores_per_node, memory_gb_per_node, status, created_at, updated_at
		FROM node_pools WHERE operator_id = $1 ORDER BY name
	`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list node pools: %w", err)
	}
	defer rows.Close()

	var out []NodePool
	for rows.Next() {
		var np NodePool
		if err := rows.Scan(&np.ID, &np.OperatorID, &np.ClusterID, &np.Name, &np.NodeCount, &np.CPUCoresPerNode, &np.MemoryGBPerNode, &np.Status, &np.CreatedAt, &np.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan node pool: %w", err)
		}
		out = append(out, np)
	}
	return out, rows.Err()
}

func nodePoolBelongsToOperator(ctx context.Context, c conn, id, operatorID uuid.UUID) (bool, error) {
	var exists bool
	err := c.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM node_pools WHERE id = $1 AND operator_id = $2)`, id, operatorID).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("check node pool ownership: %w", err)
	}
	return exists, nil
}

func createAccelerator(ctx context.Context, c conn, operatorID, nodePoolID uuid.UUID, acceleratorType string, countPerNode, memoryGB int) (Accelerator, error) {
	var a Accelerator
	err := c.QueryRow(ctx, `
		INSERT INTO accelerators (operator_id, node_pool_id, accelerator_type, count_per_node, memory_gb)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, operator_id, node_pool_id, accelerator_type, count_per_node, memory_gb, created_at, updated_at
	`, operatorID, nodePoolID, acceleratorType, countPerNode, memoryGB).Scan(
		&a.ID, &a.OperatorID, &a.NodePoolID, &a.AcceleratorType, &a.CountPerNode, &a.MemoryGB, &a.CreatedAt, &a.UpdatedAt)
	if err != nil {
		return Accelerator{}, fmt.Errorf("insert accelerator: %w", err)
	}
	return a, nil
}

func listAccelerators(ctx context.Context, c conn, operatorID uuid.UUID) ([]Accelerator, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, node_pool_id, accelerator_type, count_per_node, memory_gb, created_at, updated_at
		FROM accelerators WHERE operator_id = $1 ORDER BY created_at
	`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list accelerators: %w", err)
	}
	defer rows.Close()

	var out []Accelerator
	for rows.Next() {
		var a Accelerator
		if err := rows.Scan(&a.ID, &a.OperatorID, &a.NodePoolID, &a.AcceleratorType, &a.CountPerNode, &a.MemoryGB, &a.CreatedAt, &a.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan accelerator: %w", err)
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Storage pools / Network capabilities
// ---------------------------------------------------------------------

func createStoragePool(ctx context.Context, c conn, operatorID uuid.UUID, dataCentreID, edgeSiteID *uuid.UUID, name, storageType string, capacityGB int64, encryptedAtRest bool) (StoragePool, error) {
	var sp StoragePool
	err := c.QueryRow(ctx, `
		INSERT INTO storage_pools (operator_id, data_centre_id, edge_site_id, name, storage_type, capacity_gb, encrypted_at_rest)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING id, operator_id, data_centre_id, edge_site_id, name, storage_type, capacity_gb, encrypted_at_rest, status, created_at, updated_at
	`, operatorID, dataCentreID, edgeSiteID, name, storageType, capacityGB, encryptedAtRest).Scan(
		&sp.ID, &sp.OperatorID, &sp.DataCentreID, &sp.EdgeSiteID, &sp.Name, &sp.StorageType, &sp.CapacityGB, &sp.EncryptedAtRest, &sp.Status, &sp.CreatedAt, &sp.UpdatedAt)
	if err != nil {
		return StoragePool{}, fmt.Errorf("insert storage pool: %w", err)
	}
	return sp, nil
}

func listStoragePools(ctx context.Context, c conn, operatorID uuid.UUID) ([]StoragePool, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, data_centre_id, edge_site_id, name, storage_type, capacity_gb, encrypted_at_rest, status, created_at, updated_at
		FROM storage_pools WHERE operator_id = $1 ORDER BY name
	`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list storage pools: %w", err)
	}
	defer rows.Close()

	var out []StoragePool
	for rows.Next() {
		var sp StoragePool
		if err := rows.Scan(&sp.ID, &sp.OperatorID, &sp.DataCentreID, &sp.EdgeSiteID, &sp.Name, &sp.StorageType, &sp.CapacityGB, &sp.EncryptedAtRest, &sp.Status, &sp.CreatedAt, &sp.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan storage pool: %w", err)
		}
		out = append(out, sp)
	}
	return out, rows.Err()
}

func createNetworkCapability(ctx context.Context, c conn, operatorID uuid.UUID, dataCentreID, edgeSiteID *uuid.UUID, capabilityType string, bandwidthGbps float64, estimatedLatencyMs *float64) (NetworkCapability, error) {
	var nc NetworkCapability
	err := c.QueryRow(ctx, `
		INSERT INTO network_capabilities (operator_id, data_centre_id, edge_site_id, capability_type, bandwidth_gbps, estimated_latency_ms)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, operator_id, data_centre_id, edge_site_id, capability_type, bandwidth_gbps, estimated_latency_ms, status, created_at, updated_at
	`, operatorID, dataCentreID, edgeSiteID, capabilityType, bandwidthGbps, estimatedLatencyMs).Scan(
		&nc.ID, &nc.OperatorID, &nc.DataCentreID, &nc.EdgeSiteID, &nc.CapabilityType, &nc.BandwidthGbps, &nc.EstimatedLatencyMs, &nc.Status, &nc.CreatedAt, &nc.UpdatedAt)
	if err != nil {
		return NetworkCapability{}, fmt.Errorf("insert network capability: %w", err)
	}
	return nc, nil
}

func listNetworkCapabilities(ctx context.Context, c conn, operatorID uuid.UUID) ([]NetworkCapability, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, data_centre_id, edge_site_id, capability_type, bandwidth_gbps, estimated_latency_ms, status, created_at, updated_at
		FROM network_capabilities WHERE operator_id = $1 ORDER BY created_at
	`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list network capabilities: %w", err)
	}
	defer rows.Close()

	var out []NetworkCapability
	for rows.Next() {
		var nc NetworkCapability
		if err := rows.Scan(&nc.ID, &nc.OperatorID, &nc.DataCentreID, &nc.EdgeSiteID, &nc.CapabilityType, &nc.BandwidthGbps, &nc.EstimatedLatencyMs, &nc.Status, &nc.CreatedAt, &nc.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan network capability: %w", err)
		}
		out = append(out, nc)
	}
	return out, rows.Err()
}
