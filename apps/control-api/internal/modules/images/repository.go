package images

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

type conn interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

// ---------------------------------------------------------------------
// approved_container_registries (global, no RLS)
// ---------------------------------------------------------------------

func listApprovedRegistries(ctx context.Context, c conn) ([]ApprovedRegistry, error) {
	rows, err := c.Query(ctx, `SELECT id, registry_host, is_active, notes, added_by, created_at FROM approved_container_registries ORDER BY registry_host`)
	if err != nil {
		return nil, fmt.Errorf("list approved registries: %w", err)
	}
	defer rows.Close()
	out := []ApprovedRegistry{}
	for rows.Next() {
		var reg ApprovedRegistry
		if err := rows.Scan(&reg.ID, &reg.RegistryHost, &reg.IsActive, &reg.Notes, &reg.AddedBy, &reg.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, reg)
	}
	return out, rows.Err()
}

func isRegistryApproved(ctx context.Context, c conn, registryHost string) (bool, error) {
	var isActive bool
	err := c.QueryRow(ctx, `SELECT is_active FROM approved_container_registries WHERE registry_host = $1`, registryHost).Scan(&isActive)
	if err != nil {
		if err == pgx.ErrNoRows {
			return false, nil
		}
		return false, fmt.Errorf("check approved registry: %w", err)
	}
	return isActive, nil
}

func addApprovedRegistry(ctx context.Context, c conn, registryHost, notes string, addedBy uuid.UUID) (ApprovedRegistry, error) {
	var reg ApprovedRegistry
	err := c.QueryRow(ctx, `
		INSERT INTO approved_container_registries (registry_host, notes, added_by)
		VALUES ($1, $2, $3)
		RETURNING id, registry_host, is_active, notes, added_by, created_at
	`, registryHost, notes, addedBy).Scan(&reg.ID, &reg.RegistryHost, &reg.IsActive, &reg.Notes, &reg.AddedBy, &reg.CreatedAt)
	if err != nil {
		return ApprovedRegistry{}, fmt.Errorf("insert approved registry: %w", err)
	}
	return reg, nil
}

func setApprovedRegistryActive(ctx context.Context, c conn, id uuid.UUID, isActive bool) (bool, error) {
	tag, err := c.Exec(ctx, `UPDATE approved_container_registries SET is_active = $2 WHERE id = $1`, id, isActive)
	if err != nil {
		return false, fmt.Errorf("update approved registry: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

// ---------------------------------------------------------------------
// container_images
// ---------------------------------------------------------------------

const imageColumns = `
	id, enterprise_tenant_id, registry_host, repository, digest, tag, status,
	registered_by, approved_by, approved_at, revoked_at, revocation_reason, created_at, updated_at
`

func scanImage(row pgx.Row) (ContainerImage, error) {
	var img ContainerImage
	err := row.Scan(
		&img.ID, &img.TenantID, &img.RegistryHost, &img.Repository, &img.Digest, &img.Tag, &img.Status,
		&img.RegisteredBy, &img.ApprovedBy, &img.ApprovedAt, &img.RevokedAt, &img.RevocationReason, &img.CreatedAt, &img.UpdatedAt,
	)
	return img, err
}

func createImage(ctx context.Context, c conn, tenantID uuid.UUID, registryHost, repository, digest, tag string, registeredBy uuid.UUID) (ContainerImage, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO container_images (enterprise_tenant_id, registry_host, repository, digest, tag, registered_by)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING `+imageColumns,
		tenantID, registryHost, repository, digest, tag, registeredBy,
	)
	img, err := scanImage(row)
	if err != nil {
		return ContainerImage{}, fmt.Errorf("insert container image: %w", err)
	}
	return img, nil
}

func getImageByID(ctx context.Context, c conn, tenantID, id uuid.UUID) (ContainerImage, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+imageColumns+` FROM container_images WHERE enterprise_tenant_id = $1 AND id = $2`, tenantID, id)
	img, err := scanImage(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return ContainerImage{}, false, nil
		}
		return ContainerImage{}, false, fmt.Errorf("get container image: %w", err)
	}
	return img, true, nil
}

func listImages(ctx context.Context, c conn, tenantID uuid.UUID) ([]ContainerImage, error) {
	rows, err := c.Query(ctx, `SELECT `+imageColumns+` FROM container_images WHERE enterprise_tenant_id = $1 ORDER BY created_at DESC`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list container images: %w", err)
	}
	defer rows.Close()
	out := []ContainerImage{}
	for rows.Next() {
		img, err := scanImage(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, img)
	}
	return out, rows.Err()
}

// markImageApproved accepts an image currently 'pending' OR 'blocked' --
// 'blocked' must be re-approvable once a vulnerability exception (or an
// updated, less strict policy) removes the reason it was blocked, since
// ApproveImage re-evaluates the policy on every call rather than only once.
func markImageApproved(ctx context.Context, c conn, id, approvedBy uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE container_images SET status = 'approved', approved_by = $2, approved_at = now(), updated_at = now()
		WHERE id = $1 AND status IN ('pending', 'blocked')
	`, id, approvedBy)
	if err != nil {
		return false, fmt.Errorf("mark image approved: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func markImageBlocked(ctx context.Context, c conn, id uuid.UUID) error {
	_, err := c.Exec(ctx, `UPDATE container_images SET status = 'blocked', updated_at = now() WHERE id = $1 AND status IN ('pending', 'blocked')`, id)
	if err != nil {
		return fmt.Errorf("mark image blocked: %w", err)
	}
	return nil
}

func markImageRevoked(ctx context.Context, c conn, id uuid.UUID, reason string) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE container_images SET status = 'revoked', revocation_reason = $2, revoked_at = now(), updated_at = now()
		WHERE id = $1 AND status = 'approved'
	`, id, reason)
	if err != nil {
		return false, fmt.Errorf("mark image revoked: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

// ---------------------------------------------------------------------
// image_signatures
// ---------------------------------------------------------------------

func createSignature(ctx context.Context, c conn, tenantID, imageID uuid.UUID, signer, publicKeyPEM, signatureBase64, status string, signedAt *time.Time) (Signature, error) {
	var sig Signature
	err := c.QueryRow(ctx, `
		INSERT INTO image_signatures (enterprise_tenant_id, container_image_id, signer, public_key_pem, signature_base64, status, signed_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING id, container_image_id, signer, public_key_pem, signature_base64, status, signed_at, verified_at, created_at
	`, tenantID, imageID, signer, publicKeyPEM, signatureBase64, status, signedAt).Scan(
		&sig.ID, &sig.ContainerImageID, &sig.Signer, &sig.PublicKeyPEM, &sig.SignatureBase64, &sig.Status, &sig.SignedAt, &sig.VerifiedAt, &sig.CreatedAt)
	if err != nil {
		return Signature{}, fmt.Errorf("insert image signature: %w", err)
	}
	return sig, nil
}

func listSignatures(ctx context.Context, c conn, tenantID, imageID uuid.UUID) ([]Signature, error) {
	rows, err := c.Query(ctx, `
		SELECT id, container_image_id, signer, public_key_pem, signature_base64, status, signed_at, verified_at, created_at
		FROM image_signatures WHERE enterprise_tenant_id = $1 AND container_image_id = $2 ORDER BY created_at DESC
	`, tenantID, imageID)
	if err != nil {
		return nil, fmt.Errorf("list image signatures: %w", err)
	}
	defer rows.Close()
	out := []Signature{}
	for rows.Next() {
		var sig Signature
		if err := rows.Scan(&sig.ID, &sig.ContainerImageID, &sig.Signer, &sig.PublicKeyPEM, &sig.SignatureBase64, &sig.Status, &sig.SignedAt, &sig.VerifiedAt, &sig.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, sig)
	}
	return out, rows.Err()
}

func hasVerifiedSignature(ctx context.Context, c conn, imageID uuid.UUID) (bool, error) {
	var count int
	err := c.QueryRow(ctx, `SELECT count(*) FROM image_signatures WHERE container_image_id = $1 AND status = 'verified'`, imageID).Scan(&count)
	if err != nil {
		return false, fmt.Errorf("check verified signature: %w", err)
	}
	return count > 0, nil
}

// ---------------------------------------------------------------------
// image_provenance
// ---------------------------------------------------------------------

func upsertProvenance(ctx context.Context, c conn, tenantID, imageID uuid.UUID, builder, sourceRepository, buildCommit, buildPipelineURL string, attestation map[string]any, recordedBy uuid.UUID) (Provenance, error) {
	attestationJSON, err := json.Marshal(attestation)
	if err != nil {
		return Provenance{}, fmt.Errorf("marshal attestation: %w", err)
	}
	var p Provenance
	var attestationRaw []byte
	err = c.QueryRow(ctx, `
		INSERT INTO image_provenance (enterprise_tenant_id, container_image_id, builder, source_repository, build_commit, build_pipeline_url, attestation, recorded_by)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		ON CONFLICT (container_image_id) DO UPDATE SET
			builder = EXCLUDED.builder, source_repository = EXCLUDED.source_repository,
			build_commit = EXCLUDED.build_commit, build_pipeline_url = EXCLUDED.build_pipeline_url,
			attestation = EXCLUDED.attestation, recorded_by = EXCLUDED.recorded_by
		RETURNING id, container_image_id, builder, source_repository, build_commit, build_pipeline_url, attestation, recorded_by, created_at
	`, tenantID, imageID, builder, sourceRepository, buildCommit, buildPipelineURL, attestationJSON, recordedBy).Scan(
		&p.ID, &p.ContainerImageID, &p.Builder, &p.SourceRepository, &p.BuildCommit, &p.BuildPipelineURL, &attestationRaw, &p.RecordedBy, &p.CreatedAt)
	if err != nil {
		return Provenance{}, fmt.Errorf("upsert image provenance: %w", err)
	}
	if err := json.Unmarshal(attestationRaw, &p.Attestation); err != nil {
		return Provenance{}, fmt.Errorf("unmarshal attestation: %w", err)
	}
	return p, nil
}

func getProvenance(ctx context.Context, c conn, tenantID, imageID uuid.UUID) (Provenance, bool, error) {
	var p Provenance
	var attestationRaw []byte
	err := c.QueryRow(ctx, `
		SELECT id, container_image_id, builder, source_repository, build_commit, build_pipeline_url, attestation, recorded_by, created_at
		FROM image_provenance WHERE enterprise_tenant_id = $1 AND container_image_id = $2
	`, tenantID, imageID).Scan(&p.ID, &p.ContainerImageID, &p.Builder, &p.SourceRepository, &p.BuildCommit, &p.BuildPipelineURL, &attestationRaw, &p.RecordedBy, &p.CreatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Provenance{}, false, nil
		}
		return Provenance{}, false, fmt.Errorf("get image provenance: %w", err)
	}
	if err := json.Unmarshal(attestationRaw, &p.Attestation); err != nil {
		return Provenance{}, false, fmt.Errorf("unmarshal attestation: %w", err)
	}
	return p, true, nil
}

// ---------------------------------------------------------------------
// sboms
// ---------------------------------------------------------------------

func createSBOM(ctx context.Context, c conn, tenantID, imageID uuid.UUID, format string, document map[string]any, generatedBy string, ingestedBy uuid.UUID) (SBOM, error) {
	documentJSON, err := json.Marshal(document)
	if err != nil {
		return SBOM{}, fmt.Errorf("marshal sbom document: %w", err)
	}
	var s SBOM
	var documentRaw []byte
	err = c.QueryRow(ctx, `
		INSERT INTO sboms (enterprise_tenant_id, container_image_id, format, document, generated_by, ingested_by)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, container_image_id, format, document, generated_by, ingested_by, ingested_at, created_at
	`, tenantID, imageID, format, documentJSON, generatedBy, ingestedBy).Scan(
		&s.ID, &s.ContainerImageID, &s.Format, &documentRaw, &s.GeneratedBy, &s.IngestedBy, &s.IngestedAt, &s.CreatedAt)
	if err != nil {
		return SBOM{}, fmt.Errorf("insert sbom: %w", err)
	}
	if err := json.Unmarshal(documentRaw, &s.Document); err != nil {
		return SBOM{}, fmt.Errorf("unmarshal sbom document: %w", err)
	}
	return s, nil
}

func listSBOMs(ctx context.Context, c conn, tenantID, imageID uuid.UUID) ([]SBOM, error) {
	rows, err := c.Query(ctx, `
		SELECT id, container_image_id, format, document, generated_by, ingested_by, ingested_at, created_at
		FROM sboms WHERE enterprise_tenant_id = $1 AND container_image_id = $2 ORDER BY ingested_at DESC
	`, tenantID, imageID)
	if err != nil {
		return nil, fmt.Errorf("list sboms: %w", err)
	}
	defer rows.Close()
	out := []SBOM{}
	for rows.Next() {
		var s SBOM
		var documentRaw []byte
		if err := rows.Scan(&s.ID, &s.ContainerImageID, &s.Format, &documentRaw, &s.GeneratedBy, &s.IngestedBy, &s.IngestedAt, &s.CreatedAt); err != nil {
			return nil, err
		}
		if err := json.Unmarshal(documentRaw, &s.Document); err != nil {
			return nil, fmt.Errorf("unmarshal sbom document: %w", err)
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

func hasSBOM(ctx context.Context, c conn, imageID uuid.UUID) (bool, error) {
	var count int
	err := c.QueryRow(ctx, `SELECT count(*) FROM sboms WHERE container_image_id = $1`, imageID).Scan(&count)
	if err != nil {
		return false, fmt.Errorf("check sbom presence: %w", err)
	}
	return count > 0, nil
}

// ---------------------------------------------------------------------
// vulnerability_scans / vulnerability_findings
// ---------------------------------------------------------------------

type FindingInput struct {
	CVEID          string
	Severity       string
	PackageName    string
	PackageVersion string
	FixedVersion   string
	Description    string
}

func createVulnerabilityScan(ctx context.Context, c conn, tenantID, imageID uuid.UUID, scanner string, scannedAt time.Time, findings []FindingInput, ingestedBy uuid.UUID) (VulnerabilityScan, []VulnerabilityFinding, error) {
	summary := map[string]int{}
	for _, f := range findings {
		summary[f.Severity]++
	}
	summaryJSON, err := json.Marshal(summary)
	if err != nil {
		return VulnerabilityScan{}, nil, fmt.Errorf("marshal scan summary: %w", err)
	}

	var scan VulnerabilityScan
	var summaryRaw []byte
	err = c.QueryRow(ctx, `
		INSERT INTO vulnerability_scans (enterprise_tenant_id, container_image_id, scanner, scanned_at, summary, ingested_by)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, container_image_id, scanner, scanned_at, summary, ingested_by, created_at
	`, tenantID, imageID, scanner, scannedAt, summaryJSON, ingestedBy).Scan(
		&scan.ID, &scan.ContainerImageID, &scan.Scanner, &scan.ScannedAt, &summaryRaw, &scan.IngestedBy, &scan.CreatedAt)
	if err != nil {
		return VulnerabilityScan{}, nil, fmt.Errorf("insert vulnerability scan: %w", err)
	}
	if err := json.Unmarshal(summaryRaw, &scan.Summary); err != nil {
		return VulnerabilityScan{}, nil, fmt.Errorf("unmarshal scan summary: %w", err)
	}

	createdFindings := make([]VulnerabilityFinding, 0, len(findings))
	for _, f := range findings {
		var vf VulnerabilityFinding
		err := c.QueryRow(ctx, `
			INSERT INTO vulnerability_findings (enterprise_tenant_id, vulnerability_scan_id, cve_id, severity, package_name, package_version, fixed_version, description)
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
			RETURNING id, vulnerability_scan_id, cve_id, severity, package_name, package_version, fixed_version, description, created_at
		`, tenantID, scan.ID, f.CVEID, f.Severity, f.PackageName, f.PackageVersion, f.FixedVersion, f.Description).Scan(
			&vf.ID, &vf.VulnerabilityScanID, &vf.CVEID, &vf.Severity, &vf.PackageName, &vf.PackageVersion, &vf.FixedVersion, &vf.Description, &vf.CreatedAt)
		if err != nil {
			return VulnerabilityScan{}, nil, fmt.Errorf("insert vulnerability finding: %w", err)
		}
		createdFindings = append(createdFindings, vf)
	}
	return scan, createdFindings, nil
}

func listVulnerabilityScans(ctx context.Context, c conn, tenantID, imageID uuid.UUID) ([]VulnerabilityScan, error) {
	rows, err := c.Query(ctx, `
		SELECT id, container_image_id, scanner, scanned_at, summary, ingested_by, created_at
		FROM vulnerability_scans WHERE enterprise_tenant_id = $1 AND container_image_id = $2 ORDER BY scanned_at DESC
	`, tenantID, imageID)
	if err != nil {
		return nil, fmt.Errorf("list vulnerability scans: %w", err)
	}
	defer rows.Close()
	out := []VulnerabilityScan{}
	for rows.Next() {
		var scan VulnerabilityScan
		var summaryRaw []byte
		if err := rows.Scan(&scan.ID, &scan.ContainerImageID, &scan.Scanner, &scan.ScannedAt, &summaryRaw, &scan.IngestedBy, &scan.CreatedAt); err != nil {
			return nil, err
		}
		if err := json.Unmarshal(summaryRaw, &scan.Summary); err != nil {
			return nil, fmt.Errorf("unmarshal scan summary: %w", err)
		}
		out = append(out, scan)
	}
	return out, rows.Err()
}

func listFindingsForScan(ctx context.Context, c conn, scanID uuid.UUID) ([]VulnerabilityFinding, error) {
	rows, err := c.Query(ctx, `
		SELECT id, vulnerability_scan_id, cve_id, severity, package_name, package_version, fixed_version, description, created_at
		FROM vulnerability_findings WHERE vulnerability_scan_id = $1 ORDER BY severity
	`, scanID)
	if err != nil {
		return nil, fmt.Errorf("list vulnerability findings: %w", err)
	}
	defer rows.Close()
	out := []VulnerabilityFinding{}
	for rows.Next() {
		var vf VulnerabilityFinding
		if err := rows.Scan(&vf.ID, &vf.VulnerabilityScanID, &vf.CVEID, &vf.Severity, &vf.PackageName, &vf.PackageVersion, &vf.FixedVersion, &vf.Description, &vf.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, vf)
	}
	return out, rows.Err()
}

// latestScanFindings returns the findings from the image's most recent
// vulnerability scan (nil, nil if the image has never been scanned).
func latestScanFindings(ctx context.Context, c conn, imageID uuid.UUID) ([]VulnerabilityFinding, error) {
	var scanID uuid.UUID
	err := c.QueryRow(ctx, `
		SELECT id FROM vulnerability_scans WHERE container_image_id = $1 ORDER BY scanned_at DESC LIMIT 1
	`, imageID).Scan(&scanID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("find latest vulnerability scan: %w", err)
	}
	return listFindingsForScan(ctx, c, scanID)
}

// ---------------------------------------------------------------------
// vulnerability_policies
// ---------------------------------------------------------------------

func getVulnerabilityPolicy(ctx context.Context, c conn, tenantID uuid.UUID) (VulnerabilityPolicy, bool, error) {
	var p VulnerabilityPolicy
	err := c.QueryRow(ctx, `
		SELECT id, enterprise_tenant_id, max_allowed_severity, block_unsigned_images, require_sbom, updated_by, created_at, updated_at
		FROM vulnerability_policies WHERE enterprise_tenant_id = $1
	`, tenantID).Scan(&p.ID, &p.TenantID, &p.MaxAllowedSeverity, &p.BlockUnsignedImages, &p.RequireSBOM, &p.UpdatedBy, &p.CreatedAt, &p.UpdatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return VulnerabilityPolicy{}, false, nil
		}
		return VulnerabilityPolicy{}, false, fmt.Errorf("get vulnerability policy: %w", err)
	}
	return p, true, nil
}

func createDefaultVulnerabilityPolicy(ctx context.Context, c conn, tenantID uuid.UUID) (VulnerabilityPolicy, error) {
	var p VulnerabilityPolicy
	err := c.QueryRow(ctx, `
		INSERT INTO vulnerability_policies (enterprise_tenant_id)
		VALUES ($1)
		ON CONFLICT (enterprise_tenant_id) DO UPDATE SET enterprise_tenant_id = EXCLUDED.enterprise_tenant_id
		RETURNING id, enterprise_tenant_id, max_allowed_severity, block_unsigned_images, require_sbom, updated_by, created_at, updated_at
	`, tenantID).Scan(&p.ID, &p.TenantID, &p.MaxAllowedSeverity, &p.BlockUnsignedImages, &p.RequireSBOM, &p.UpdatedBy, &p.CreatedAt, &p.UpdatedAt)
	if err != nil {
		return VulnerabilityPolicy{}, fmt.Errorf("create default vulnerability policy: %w", err)
	}
	return p, nil
}

func updateVulnerabilityPolicy(ctx context.Context, c conn, tenantID uuid.UUID, maxAllowedSeverity string, blockUnsigned, requireSBOM bool, updatedBy uuid.UUID) (VulnerabilityPolicy, error) {
	var p VulnerabilityPolicy
	err := c.QueryRow(ctx, `
		UPDATE vulnerability_policies
		SET max_allowed_severity = $2, block_unsigned_images = $3, require_sbom = $4, updated_by = $5, updated_at = now()
		WHERE enterprise_tenant_id = $1
		RETURNING id, enterprise_tenant_id, max_allowed_severity, block_unsigned_images, require_sbom, updated_by, created_at, updated_at
	`, tenantID, maxAllowedSeverity, blockUnsigned, requireSBOM, updatedBy).Scan(
		&p.ID, &p.TenantID, &p.MaxAllowedSeverity, &p.BlockUnsignedImages, &p.RequireSBOM, &p.UpdatedBy, &p.CreatedAt, &p.UpdatedAt)
	if err != nil {
		return VulnerabilityPolicy{}, fmt.Errorf("update vulnerability policy: %w", err)
	}
	return p, nil
}

// ---------------------------------------------------------------------
// vulnerability_exceptions
// ---------------------------------------------------------------------

const exceptionColumns = `
	id, enterprise_tenant_id, container_image_id, finding_id, requested_by, reason, requested_at,
	approved_by, approved_at, expires_at, status, created_at, updated_at
`

func scanException(row pgx.Row) (VulnerabilityException, error) {
	var e VulnerabilityException
	err := row.Scan(
		&e.ID, &e.TenantID, &e.ContainerImageID, &e.FindingID, &e.RequestedBy, &e.Reason, &e.RequestedAt,
		&e.ApprovedBy, &e.ApprovedAt, &e.ExpiresAt, &e.Status, &e.CreatedAt, &e.UpdatedAt,
	)
	return e, err
}

func createException(ctx context.Context, c conn, tenantID, imageID uuid.UUID, findingID *uuid.UUID, requestedBy uuid.UUID, reason string, expiresAt time.Time) (VulnerabilityException, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO vulnerability_exceptions (enterprise_tenant_id, container_image_id, finding_id, requested_by, reason, expires_at)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING `+exceptionColumns,
		tenantID, imageID, findingID, requestedBy, reason, expiresAt,
	)
	e, err := scanException(row)
	if err != nil {
		return VulnerabilityException{}, fmt.Errorf("insert vulnerability exception: %w", err)
	}
	return e, nil
}

func getExceptionByID(ctx context.Context, c conn, tenantID, id uuid.UUID) (VulnerabilityException, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+exceptionColumns+` FROM vulnerability_exceptions WHERE enterprise_tenant_id = $1 AND id = $2`, tenantID, id)
	e, err := scanException(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return VulnerabilityException{}, false, nil
		}
		return VulnerabilityException{}, false, fmt.Errorf("get vulnerability exception: %w", err)
	}
	return e, true, nil
}

func listExceptionsForImage(ctx context.Context, c conn, tenantID, imageID uuid.UUID) ([]VulnerabilityException, error) {
	rows, err := c.Query(ctx, `
		SELECT `+exceptionColumns+` FROM vulnerability_exceptions
		WHERE enterprise_tenant_id = $1 AND container_image_id = $2 ORDER BY requested_at DESC
	`, tenantID, imageID)
	if err != nil {
		return nil, fmt.Errorf("list vulnerability exceptions: %w", err)
	}
	defer rows.Close()
	out := []VulnerabilityException{}
	for rows.Next() {
		e, err := scanException(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

func markExceptionApproved(ctx context.Context, c conn, id, approvedBy uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE vulnerability_exceptions SET status = 'approved', approved_by = $2, approved_at = now(), updated_at = now()
		WHERE id = $1 AND status = 'pending'
	`, id, approvedBy)
	if err != nil {
		return false, fmt.Errorf("mark exception approved: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func markExceptionRejected(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE vulnerability_exceptions SET status = 'rejected', updated_at = now()
		WHERE id = $1 AND status = 'pending'
	`, id)
	if err != nil {
		return false, fmt.Errorf("mark exception rejected: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

// activeExceptionCoversFinding reports whether an approved, unexpired
// exception exists for the image that covers either the specific finding
// (findingID) or the whole image (an exception with a nil finding_id).
func activeExceptionCoversFinding(ctx context.Context, c conn, imageID uuid.UUID, findingID uuid.UUID) (bool, error) {
	var count int
	err := c.QueryRow(ctx, `
		SELECT count(*) FROM vulnerability_exceptions
		WHERE container_image_id = $1 AND status = 'approved' AND expires_at > now()
		  AND (finding_id IS NULL OR finding_id = $2)
	`, imageID, findingID).Scan(&count)
	if err != nil {
		return false, fmt.Errorf("check active vulnerability exception: %w", err)
	}
	return count > 0, nil
}
