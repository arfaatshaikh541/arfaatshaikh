// Package images implements the container-image supply-chain registry:
// approved-registry allowlisting, digest-pinned image registration,
// cryptographic signature verification, provenance recording, SBOM
// ingestion, vulnerability-scan ingestion, and vulnerability-policy
// evaluation gating image approval (with a dual-control exception
// workflow) -- approved architecture's Milestone 4 scope.
package images

import (
	"time"

	"github.com/google/uuid"
)

type ApprovedRegistry struct {
	ID           uuid.UUID  `json:"id"`
	RegistryHost string     `json:"registry_host"`
	IsActive     bool       `json:"is_active"`
	Notes        string     `json:"notes"`
	AddedBy      *uuid.UUID `json:"added_by,omitempty"`
	CreatedAt    time.Time  `json:"created_at"`
}

type ContainerImage struct {
	ID               uuid.UUID  `json:"id"`
	TenantID         uuid.UUID  `json:"enterprise_tenant_id"`
	RegistryHost     string     `json:"registry_host"`
	Repository       string     `json:"repository"`
	Digest           string     `json:"digest"`
	Tag              string     `json:"tag"`
	Status           string     `json:"status"`
	RegisteredBy     uuid.UUID  `json:"registered_by"`
	ApprovedBy       *uuid.UUID `json:"approved_by,omitempty"`
	ApprovedAt       *time.Time `json:"approved_at,omitempty"`
	RevokedAt        *time.Time `json:"revoked_at,omitempty"`
	RevocationReason *string    `json:"revocation_reason,omitempty"`
	CreatedAt        time.Time  `json:"created_at"`
	UpdatedAt        time.Time  `json:"updated_at"`
}

type Signature struct {
	ID               uuid.UUID  `json:"id"`
	ContainerImageID uuid.UUID  `json:"container_image_id"`
	Signer           string     `json:"signer"`
	PublicKeyPEM     string     `json:"public_key_pem"`
	SignatureBase64  string     `json:"signature_base64"`
	Status           string     `json:"status"`
	SignedAt         *time.Time `json:"signed_at,omitempty"`
	VerifiedAt       time.Time  `json:"verified_at"`
	CreatedAt        time.Time  `json:"created_at"`
}

type Provenance struct {
	ID               uuid.UUID      `json:"id"`
	ContainerImageID uuid.UUID      `json:"container_image_id"`
	Builder          string         `json:"builder"`
	SourceRepository string         `json:"source_repository"`
	BuildCommit      string         `json:"build_commit"`
	BuildPipelineURL string         `json:"build_pipeline_url"`
	Attestation      map[string]any `json:"attestation"`
	RecordedBy       uuid.UUID      `json:"recorded_by"`
	CreatedAt        time.Time      `json:"created_at"`
}

type SBOM struct {
	ID               uuid.UUID      `json:"id"`
	ContainerImageID uuid.UUID      `json:"container_image_id"`
	Format           string         `json:"format"`
	Document         map[string]any `json:"document"`
	GeneratedBy      string         `json:"generated_by"`
	IngestedBy       uuid.UUID      `json:"ingested_by"`
	IngestedAt       time.Time      `json:"ingested_at"`
	CreatedAt        time.Time      `json:"created_at"`
}

type VulnerabilityScan struct {
	ID               uuid.UUID      `json:"id"`
	ContainerImageID uuid.UUID      `json:"container_image_id"`
	Scanner          string         `json:"scanner"`
	ScannedAt        time.Time      `json:"scanned_at"`
	Summary          map[string]any `json:"summary"`
	IngestedBy       uuid.UUID      `json:"ingested_by"`
	CreatedAt        time.Time      `json:"created_at"`
}

type VulnerabilityFinding struct {
	ID                  uuid.UUID `json:"id"`
	VulnerabilityScanID uuid.UUID `json:"vulnerability_scan_id"`
	CVEID               string    `json:"cve_id"`
	Severity            string    `json:"severity"`
	PackageName         string    `json:"package_name"`
	PackageVersion      string    `json:"package_version"`
	FixedVersion        string    `json:"fixed_version"`
	Description         string    `json:"description"`
	CreatedAt           time.Time `json:"created_at"`
}

type VulnerabilityPolicy struct {
	ID                  uuid.UUID  `json:"id"`
	TenantID            uuid.UUID  `json:"enterprise_tenant_id"`
	MaxAllowedSeverity  string     `json:"max_allowed_severity"`
	BlockUnsignedImages bool       `json:"block_unsigned_images"`
	RequireSBOM         bool       `json:"require_sbom"`
	UpdatedBy           *uuid.UUID `json:"updated_by,omitempty"`
	CreatedAt           time.Time  `json:"created_at"`
	UpdatedAt           time.Time  `json:"updated_at"`
}

type VulnerabilityException struct {
	ID               uuid.UUID  `json:"id"`
	TenantID         uuid.UUID  `json:"enterprise_tenant_id"`
	ContainerImageID uuid.UUID  `json:"container_image_id"`
	FindingID        *uuid.UUID `json:"finding_id,omitempty"`
	RequestedBy      uuid.UUID  `json:"requested_by"`
	Reason           string     `json:"reason"`
	RequestedAt      time.Time  `json:"requested_at"`
	ApprovedBy       *uuid.UUID `json:"approved_by,omitempty"`
	ApprovedAt       *time.Time `json:"approved_at,omitempty"`
	ExpiresAt        time.Time  `json:"expires_at"`
	Status           string     `json:"status"`
	CreatedAt        time.Time  `json:"created_at"`
	UpdatedAt        time.Time  `json:"updated_at"`
}

// EffectiveStatus derives "expired" at read time from expires_at rather
// than storing it -- no background job is needed to keep it accurate.
func (e VulnerabilityException) EffectiveStatus() string {
	if e.Status == "approved" && time.Now().After(e.ExpiresAt) {
		return "expired"
	}
	return e.Status
}
