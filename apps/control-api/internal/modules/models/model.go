// Package models implements the AI model registry: enterprise-owned model
// headers, immutable-once-approved model versions (checksum, signature
// status, provenance, licence, geography restrictions, supported
// languages/hardware, retention/pricing metadata), capabilities,
// benchmarks, safety evaluations, deployment profiles, and the
// dual-control approval/retirement/revocation workflow (approved
// architecture's Milestone 4 scope). Milestone 13 (AI Model Exchange) adds
// the cross-tenant layer on top: publishing an approved version to the
// marketplace (public or granted-private visibility), structured pricing,
// per-tenant access grants with price overrides, and provider onboarding --
// see PublishVersion, CreateAccessGrant, and CreateProvider.
package models

import (
	"time"

	"github.com/google/uuid"
)

type Model struct {
	ID          uuid.UUID  `json:"id"`
	TenantID    uuid.UUID  `json:"enterprise_tenant_id"`
	ModelKey    string     `json:"model_key"`
	Name        string     `json:"name"`
	Description string     `json:"description"`
	ProviderID  *uuid.UUID `json:"provider_id,omitempty"`
	Status      string     `json:"status"`
	CreatedAt   time.Time  `json:"created_at"`
	UpdatedAt   time.Time  `json:"updated_at"`
}

// ModelVersion's Visibility/PricePerUnit/PricingUnit/Currency/PublishedAt are
// Milestone 13's AI Model Exchange fields: a version is only selectable by
// another tenant's workload once it is 'approved' AND either 'public' or
// covered by an active ModelAccessGrant for that tenant -- see
// EvaluateMarketplaceEligibility and the model_versions_marketplace_read RLS
// policy (migration 0037). Every other field here predates this milestone.
type ModelVersion struct {
	ID                         uuid.UUID      `json:"id"`
	ModelID                    uuid.UUID      `json:"model_id"`
	TenantID                   uuid.UUID      `json:"enterprise_tenant_id"`
	Version                    int            `json:"version"`
	Status                     string         `json:"status"`
	Visibility                 string         `json:"visibility"`
	ProviderID                 *uuid.UUID     `json:"provider_id,omitempty"`
	LicenceID                  uuid.UUID      `json:"licence_id"`
	ChecksumSHA256             string         `json:"checksum_sha256"`
	SignatureStatus            string         `json:"signature_status"`
	Provenance                 map[string]any `json:"provenance"`
	PermittedGeographies       []string       `json:"permitted_geographies"`
	ProhibitedGeographies      []string       `json:"prohibited_geographies"`
	SupportedWorkloadTypes     []string       `json:"supported_workload_types"`
	SupportedLanguages         []string       `json:"supported_languages"`
	HardwareRequirements       map[string]any `json:"hardware_requirements"`
	MinimumAcceleratorMemoryGB *int           `json:"minimum_accelerator_memory_gb,omitempty"`
	SecurityProfile            map[string]any `json:"security_profile"`
	PerformanceMetadata        map[string]any `json:"performance_metadata"`
	InputTypes                 []string       `json:"input_types"`
	OutputTypes                []string       `json:"output_types"`
	RetentionPolicy            map[string]any `json:"retention_policy"`
	PricingMetadata            map[string]any `json:"pricing_metadata"`
	PricePerUnit               *float64       `json:"price_per_unit,omitempty"`
	PricingUnit                string         `json:"pricing_unit"`
	Currency                   string         `json:"currency"`
	PublishedAt                *time.Time     `json:"published_at,omitempty"`
	RequestedBy                uuid.UUID      `json:"requested_by"`
	ApprovedBy                 *uuid.UUID     `json:"approved_by,omitempty"`
	ApprovedAt                 *time.Time     `json:"approved_at,omitempty"`
	RejectedReason             *string        `json:"rejected_reason,omitempty"`
	RetiredAt                  *time.Time     `json:"retired_at,omitempty"`
	RetirementReason           *string        `json:"retirement_reason,omitempty"`
	RevokedAt                  *time.Time     `json:"revoked_at,omitempty"`
	RevocationReason           *string        `json:"revocation_reason,omitempty"`
	CreatedAt                  time.Time      `json:"created_at"`
	UpdatedAt                  time.Time      `json:"updated_at"`
}

type Capability struct {
	ID             uuid.UUID `json:"id"`
	ModelVersionID uuid.UUID `json:"model_version_id"`
	CapabilityKey  string    `json:"capability_key"`
	Description    string    `json:"description"`
	CreatedAt      time.Time `json:"created_at"`
}

type Benchmark struct {
	ID             uuid.UUID `json:"id"`
	ModelVersionID uuid.UUID `json:"model_version_id"`
	BenchmarkName  string    `json:"benchmark_name"`
	MetricName     string    `json:"metric_name"`
	MetricValue    float64   `json:"metric_value"`
	EvaluatedAt    time.Time `json:"evaluated_at"`
	CreatedAt      time.Time `json:"created_at"`
}

type SafetyEvaluation struct {
	ID             uuid.UUID      `json:"id"`
	ModelVersionID uuid.UUID      `json:"model_version_id"`
	Evaluator      string         `json:"evaluator"`
	Methodology    string         `json:"methodology"`
	Result         string         `json:"result"`
	Findings       map[string]any `json:"findings"`
	EvaluatedAt    time.Time      `json:"evaluated_at"`
	CreatedAt      time.Time      `json:"created_at"`
}

type DeploymentProfile struct {
	ID                   uuid.UUID      `json:"id"`
	ModelVersionID       uuid.UUID      `json:"model_version_id"`
	ProfileKey           string         `json:"profile_key"`
	Name                 string         `json:"name"`
	ResourceRequirements map[string]any `json:"resource_requirements"`
	CreatedAt            time.Time      `json:"created_at"`
}

type Provider struct {
	ID          uuid.UUID  `json:"id"`
	Key         string     `json:"key"`
	Name        string     `json:"name"`
	Website     string     `json:"website"`
	Status      string     `json:"status"`
	OnboardedBy *uuid.UUID `json:"onboarded_by,omitempty"`
	CreatedAt   time.Time  `json:"created_at"`
}

type CreateProviderInput struct {
	Key     string
	Name    string
	Website string
}

// ModelAccessGrant is the per-tenant "invitation" a private model version
// needs before another tenant's workloads may select it -- the same shape
// and purpose as capacityoffers.CapacityOfferGrant (Milestone 12).
type ModelAccessGrant struct {
	ID                   uuid.UUID `json:"id"`
	ModelVersionID       uuid.UUID `json:"model_version_id"`
	OwnerTenantID        uuid.UUID `json:"owner_tenant_id"`
	GranteeTenantID      uuid.UUID `json:"grantee_tenant_id"`
	PricePerUnitOverride *float64  `json:"price_per_unit_override,omitempty"`
	Status               string    `json:"status"`
	CreatedBy            uuid.UUID `json:"created_by"`
	CreatedAt            time.Time `json:"created_at"`
}

type CreateAccessGrantInput struct {
	GranteeTenantID      uuid.UUID
	PricePerUnitOverride *float64
}

type Licence struct {
	ID                   uuid.UUID `json:"id"`
	Key                  string    `json:"key"`
	Name                 string    `json:"name"`
	TermsURL             string    `json:"terms_url"`
	AllowsCommercialUse  bool      `json:"allows_commercial_use"`
	AllowsRedistribution bool      `json:"allows_redistribution"`
	CreatedAt            time.Time `json:"created_at"`
}

type ArtefactLink struct {
	ID               uuid.UUID `json:"id"`
	ModelVersionID   uuid.UUID `json:"model_version_id"`
	ArtefactUploadID uuid.UUID `json:"artefact_upload_id"`
	Role             string    `json:"role"`
	ChecksumSHA256   string    `json:"checksum_sha256"`
	CreatedAt        time.Time `json:"created_at"`
}
