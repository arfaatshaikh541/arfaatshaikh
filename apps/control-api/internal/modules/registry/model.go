// Package registry implements the Milestone 2 infrastructure inventory:
// the platform-curated regions/jurisdictions taxonomy, and the
// operator-owned location (data centres, edge sites, contracts) and
// technical inventory (clusters, node pools, accelerators, storage pools,
// network capabilities) layers. Every operator-owned resource here is
// scoped exactly like every operator-owned resource in Milestone 1: the
// operator_id is always resolved server-side from the authenticated
// caller's membership + the URL's already-authorized {operatorID}, never
// trusted from a request body, and enforced again by PostgreSQL RLS.
package registry

import (
	"time"

	"github.com/google/uuid"
)

type Jurisdiction struct {
	ID          uuid.UUID `json:"id"`
	CountryCode string    `json:"country_code"`
	Name        string    `json:"name"`
	Notes       string    `json:"notes"`
	CreatedAt   time.Time `json:"created_at"`
}

type Region struct {
	ID             uuid.UUID `json:"id"`
	Key            string    `json:"key"`
	Name           string    `json:"name"`
	JurisdictionID uuid.UUID `json:"jurisdiction_id"`
	Status         string    `json:"status"`
	CreatedAt      time.Time `json:"created_at"`
}

type OperatorContract struct {
	ID                uuid.UUID  `json:"id"`
	OperatorID        uuid.UUID  `json:"operator_id"`
	ContractReference string     `json:"contract_reference"`
	EffectiveAt       time.Time  `json:"effective_at"`
	TerminatesAt      *time.Time `json:"terminates_at,omitempty"`
	Status            string     `json:"status"`
	Notes             string     `json:"notes"`
	CreatedAt         time.Time  `json:"created_at"`
	UpdatedAt         time.Time  `json:"updated_at"`
}

type DataCentre struct {
	ID         uuid.UUID `json:"id"`
	OperatorID uuid.UUID `json:"operator_id"`
	RegionID   uuid.UUID `json:"region_id"`
	Name       string    `json:"name"`
	Locality   string    `json:"locality"`
	Status     string    `json:"status"`
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

type EdgeSite struct {
	ID         uuid.UUID `json:"id"`
	OperatorID uuid.UUID `json:"operator_id"`
	RegionID   uuid.UUID `json:"region_id"`
	Name       string    `json:"name"`
	Locality   string    `json:"locality"`
	Status     string    `json:"status"`
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

type Cluster struct {
	ID                uuid.UUID  `json:"id"`
	OperatorID        uuid.UUID  `json:"operator_id"`
	DataCentreID      *uuid.UUID `json:"data_centre_id,omitempty"`
	EdgeSiteID        *uuid.UUID `json:"edge_site_id,omitempty"`
	Name              string     `json:"name"`
	KubernetesVersion string     `json:"kubernetes_version"`
	Status            string     `json:"status"`
	CreatedAt         time.Time  `json:"created_at"`
	UpdatedAt         time.Time  `json:"updated_at"`
}

type NodePool struct {
	ID              uuid.UUID `json:"id"`
	OperatorID      uuid.UUID `json:"operator_id"`
	ClusterID       uuid.UUID `json:"cluster_id"`
	Name            string    `json:"name"`
	NodeCount       int       `json:"node_count"`
	CPUCoresPerNode int       `json:"cpu_cores_per_node"`
	MemoryGBPerNode int       `json:"memory_gb_per_node"`
	Status          string    `json:"status"`
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`
}

type Accelerator struct {
	ID              uuid.UUID `json:"id"`
	OperatorID      uuid.UUID `json:"operator_id"`
	NodePoolID      uuid.UUID `json:"node_pool_id"`
	AcceleratorType string    `json:"accelerator_type"`
	CountPerNode    int       `json:"count_per_node"`
	MemoryGB        int       `json:"memory_gb"`
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`
}

type StoragePool struct {
	ID              uuid.UUID  `json:"id"`
	OperatorID      uuid.UUID  `json:"operator_id"`
	DataCentreID    *uuid.UUID `json:"data_centre_id,omitempty"`
	EdgeSiteID      *uuid.UUID `json:"edge_site_id,omitempty"`
	Name            string     `json:"name"`
	StorageType     string     `json:"storage_type"`
	CapacityGB      int64      `json:"capacity_gb"`
	EncryptedAtRest bool       `json:"encrypted_at_rest"`
	Status          string     `json:"status"`
	CreatedAt       time.Time  `json:"created_at"`
	UpdatedAt       time.Time  `json:"updated_at"`
}

type NetworkCapability struct {
	ID                 uuid.UUID  `json:"id"`
	OperatorID         uuid.UUID  `json:"operator_id"`
	DataCentreID       *uuid.UUID `json:"data_centre_id,omitempty"`
	EdgeSiteID         *uuid.UUID `json:"edge_site_id,omitempty"`
	CapabilityType     string     `json:"capability_type"`
	BandwidthGbps      float64    `json:"bandwidth_gbps"`
	EstimatedLatencyMs *float64   `json:"estimated_latency_ms,omitempty"`
	Status             string     `json:"status"`
	CreatedAt          time.Time  `json:"created_at"`
	UpdatedAt          time.Time  `json:"updated_at"`
}
