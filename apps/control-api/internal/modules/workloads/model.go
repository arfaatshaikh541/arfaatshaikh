// Package workloads implements the workload registry: enterprise-owned
// workload headers, immutable-once-published workload versions (resource/
// network/storage/security/residency requirements, scaling policy,
// digest-pinned container image and approved-model-version references),
// components, health checks, and artefact/SBOM linkage -- approved
// architecture's Milestone 4 scope. It never schedules, ranks, reserves, or
// deploys anything -- that is later milestones' job; this module only
// builds and versions the trusted, referenceable definition of a workload.
package workloads

import (
	"time"

	"github.com/google/uuid"
)

type Workload struct {
	ID           uuid.UUID `json:"id"`
	TenantID     uuid.UUID `json:"enterprise_tenant_id"`
	WorkloadKey  string    `json:"workload_key"`
	WorkloadType string    `json:"workload_type"`
	Name         string    `json:"name"`
	Description  string    `json:"description"`
	OwnerUserID  uuid.UUID `json:"owner_user_id"`
	Status       string    `json:"status"`
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}

type WorkloadVersion struct {
	ID                         uuid.UUID      `json:"id"`
	WorkloadID                 uuid.UUID      `json:"workload_id"`
	TenantID                   uuid.UUID      `json:"enterprise_tenant_id"`
	Version                    int            `json:"version"`
	Status                     string         `json:"status"`
	ContainerImageID           *uuid.UUID     `json:"container_image_id,omitempty"`
	ModelVersionID             *uuid.UUID     `json:"model_version_id,omitempty"`
	ResourceRequirements       map[string]any `json:"resource_requirements"`
	NetworkRequirements        map[string]any `json:"network_requirements"`
	StorageRequirements        map[string]any `json:"storage_requirements"`
	SecurityRequirements       map[string]any `json:"security_requirements"`
	ResidencyRequirements      map[string]any `json:"residency_requirements"`
	ScalingPolicy              map[string]any `json:"scaling_policy"`
	RetentionPolicy            map[string]any `json:"retention_policy"`
	DeploymentApprovalRequired bool           `json:"deployment_approval_required"`
	RequestedBy                uuid.UUID      `json:"requested_by"`
	ApprovedBy                 *uuid.UUID     `json:"approved_by,omitempty"`
	PublishedAt                *time.Time     `json:"published_at,omitempty"`
	RetiredAt                  *time.Time     `json:"retired_at,omitempty"`
	RetirementReason           *string        `json:"retirement_reason,omitempty"`
	CreatedAt                  time.Time      `json:"created_at"`
	UpdatedAt                  time.Time      `json:"updated_at"`
}

type Component struct {
	ID                uuid.UUID      `json:"id"`
	WorkloadVersionID uuid.UUID      `json:"workload_version_id"`
	ComponentKey      string         `json:"component_key"`
	Name              string         `json:"name"`
	ContainerImageID  uuid.UUID      `json:"container_image_id"`
	Command           []string       `json:"command"`
	Args              []string       `json:"args"`
	Env               map[string]any `json:"env"`
	IsPrimary         bool           `json:"is_primary"`
	CreatedAt         time.Time      `json:"created_at"`
}

type HealthCheck struct {
	ID                  uuid.UUID `json:"id"`
	WorkloadComponentID uuid.UUID `json:"workload_component_id"`
	CheckType           string    `json:"check_type"`
	Path                string    `json:"path"`
	Port                *int      `json:"port,omitempty"`
	Command             []string  `json:"command"`
	IntervalSeconds     int       `json:"interval_seconds"`
	TimeoutSeconds      int       `json:"timeout_seconds"`
	FailureThreshold    int       `json:"failure_threshold"`
	CreatedAt           time.Time `json:"created_at"`
}

type ArtefactLink struct {
	ID                uuid.UUID `json:"id"`
	WorkloadVersionID uuid.UUID `json:"workload_version_id"`
	ArtefactUploadID  uuid.UUID `json:"artefact_upload_id"`
	Role              string    `json:"role"`
	CreatedAt         time.Time `json:"created_at"`
}

type SBOMLink struct {
	ID                uuid.UUID `json:"id"`
	WorkloadVersionID uuid.UUID `json:"workload_version_id"`
	SBOMID            uuid.UUID `json:"sbom_id"`
	CreatedAt         time.Time `json:"created_at"`
}
