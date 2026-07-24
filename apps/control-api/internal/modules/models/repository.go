package models

import (
	"context"
	"encoding/json"
	"fmt"

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
// models
// ---------------------------------------------------------------------

const modelColumns = `id, enterprise_tenant_id, model_key, name, description, provider_id, status, created_at, updated_at`

func scanModel(row pgx.Row) (Model, error) {
	var m Model
	err := row.Scan(&m.ID, &m.TenantID, &m.ModelKey, &m.Name, &m.Description, &m.ProviderID, &m.Status, &m.CreatedAt, &m.UpdatedAt)
	return m, err
}

func createModel(ctx context.Context, c conn, tenantID uuid.UUID, modelKey, name, description string, providerID *uuid.UUID) (Model, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO models (enterprise_tenant_id, model_key, name, description, provider_id)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING `+modelColumns,
		tenantID, modelKey, name, description, providerID,
	)
	m, err := scanModel(row)
	if err != nil {
		return Model{}, fmt.Errorf("insert model: %w", err)
	}
	return m, nil
}

func getModelByID(ctx context.Context, c conn, tenantID, id uuid.UUID) (Model, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+modelColumns+` FROM models WHERE enterprise_tenant_id = $1 AND id = $2`, tenantID, id)
	m, err := scanModel(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Model{}, false, nil
		}
		return Model{}, false, fmt.Errorf("get model: %w", err)
	}
	return m, true, nil
}

func getModelByKey(ctx context.Context, c conn, tenantID uuid.UUID, modelKey string) (Model, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+modelColumns+` FROM models WHERE enterprise_tenant_id = $1 AND model_key = $2`, tenantID, modelKey)
	m, err := scanModel(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Model{}, false, nil
		}
		return Model{}, false, fmt.Errorf("get model by key: %w", err)
	}
	return m, true, nil
}

func listModels(ctx context.Context, c conn, tenantID uuid.UUID) ([]Model, error) {
	rows, err := c.Query(ctx, `SELECT `+modelColumns+` FROM models WHERE enterprise_tenant_id = $1 ORDER BY created_at DESC`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list models: %w", err)
	}
	defer rows.Close()
	out := []Model{}
	for rows.Next() {
		m, err := scanModel(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// model_versions
// ---------------------------------------------------------------------

const modelVersionColumns = `
	id, model_id, enterprise_tenant_id, version, status, visibility, provider_id, licence_id, checksum_sha256,
	signature_status, provenance, permitted_geographies, prohibited_geographies,
	supported_workload_types, supported_languages, hardware_requirements,
	minimum_accelerator_memory_gb, security_profile, performance_metadata, input_types, output_types,
	retention_policy, pricing_metadata, price_per_unit, pricing_unit, currency, published_at,
	requested_by, approved_by, approved_at, rejected_reason,
	retired_at, retirement_reason, revoked_at, revocation_reason, created_at, updated_at
`

func scanModelVersion(row pgx.Row) (ModelVersion, error) {
	var v ModelVersion
	var provenanceRaw, permittedRaw, prohibitedRaw, workloadTypesRaw, languagesRaw, hardwareRaw, securityRaw, perfRaw, inputRaw, outputRaw, retentionRaw, pricingRaw []byte
	err := row.Scan(
		&v.ID, &v.ModelID, &v.TenantID, &v.Version, &v.Status, &v.Visibility, &v.ProviderID, &v.LicenceID, &v.ChecksumSHA256,
		&v.SignatureStatus, &provenanceRaw, &permittedRaw, &prohibitedRaw,
		&workloadTypesRaw, &languagesRaw, &hardwareRaw,
		&v.MinimumAcceleratorMemoryGB, &securityRaw, &perfRaw, &inputRaw, &outputRaw,
		&retentionRaw, &pricingRaw, &v.PricePerUnit, &v.PricingUnit, &v.Currency, &v.PublishedAt,
		&v.RequestedBy, &v.ApprovedBy, &v.ApprovedAt, &v.RejectedReason,
		&v.RetiredAt, &v.RetirementReason, &v.RevokedAt, &v.RevocationReason, &v.CreatedAt, &v.UpdatedAt,
	)
	if err != nil {
		return ModelVersion{}, err
	}
	for _, pair := range []struct {
		raw []byte
		dst any
	}{
		{provenanceRaw, &v.Provenance}, {permittedRaw, &v.PermittedGeographies}, {prohibitedRaw, &v.ProhibitedGeographies},
		{workloadTypesRaw, &v.SupportedWorkloadTypes}, {languagesRaw, &v.SupportedLanguages}, {hardwareRaw, &v.HardwareRequirements},
		{securityRaw, &v.SecurityProfile}, {perfRaw, &v.PerformanceMetadata}, {inputRaw, &v.InputTypes}, {outputRaw, &v.OutputTypes},
		{retentionRaw, &v.RetentionPolicy}, {pricingRaw, &v.PricingMetadata},
	} {
		if err := json.Unmarshal(pair.raw, pair.dst); err != nil {
			return ModelVersion{}, fmt.Errorf("unmarshal model version field: %w", err)
		}
	}
	return v, nil
}

// ModelVersionInput carries every field a new draft (or draft edit) sets.
type ModelVersionInput struct {
	ProviderID                 *uuid.UUID
	LicenceID                  uuid.UUID
	ChecksumSHA256             string
	Provenance                 map[string]any
	PermittedGeographies       []string
	ProhibitedGeographies      []string
	SupportedWorkloadTypes     []string
	SupportedLanguages         []string
	HardwareRequirements       map[string]any
	MinimumAcceleratorMemoryGB *int
	SecurityProfile            map[string]any
	PerformanceMetadata        map[string]any
	InputTypes                 []string
	OutputTypes                []string
	RetentionPolicy            map[string]any
	PricingMetadata            map[string]any
}

func marshalOrEmpty(v any) ([]byte, error) {
	if v == nil {
		return []byte("null"), nil
	}
	return json.Marshal(v)
}

func createModelVersionDraft(ctx context.Context, c conn, tenantID, modelID uuid.UUID, requestedBy uuid.UUID, in ModelVersionInput) (ModelVersion, error) {
	provenanceJSON, err := marshalOrEmpty(in.Provenance)
	if err != nil {
		return ModelVersion{}, err
	}
	permittedJSON, _ := json.Marshal(in.PermittedGeographies)
	prohibitedJSON, _ := json.Marshal(in.ProhibitedGeographies)
	workloadTypesJSON, _ := json.Marshal(in.SupportedWorkloadTypes)
	languagesJSON, _ := json.Marshal(in.SupportedLanguages)
	hardwareJSON, err := marshalOrEmpty(in.HardwareRequirements)
	if err != nil {
		return ModelVersion{}, err
	}
	securityJSON, err := marshalOrEmpty(in.SecurityProfile)
	if err != nil {
		return ModelVersion{}, err
	}
	perfJSON, err := marshalOrEmpty(in.PerformanceMetadata)
	if err != nil {
		return ModelVersion{}, err
	}
	inputJSON, _ := json.Marshal(in.InputTypes)
	outputJSON, _ := json.Marshal(in.OutputTypes)
	retentionJSON, err := marshalOrEmpty(in.RetentionPolicy)
	if err != nil {
		return ModelVersion{}, err
	}
	pricingJSON, err := marshalOrEmpty(in.PricingMetadata)
	if err != nil {
		return ModelVersion{}, err
	}

	row := c.QueryRow(ctx, `
		INSERT INTO model_versions (
			model_id, enterprise_tenant_id, version, provider_id, licence_id, checksum_sha256,
			provenance, permitted_geographies, prohibited_geographies, supported_workload_types,
			supported_languages, hardware_requirements, minimum_accelerator_memory_gb,
			security_profile, performance_metadata, input_types, output_types,
			retention_policy, pricing_metadata, requested_by
		)
		VALUES (
			$1, $2,
			COALESCE((SELECT max(version) FROM model_versions WHERE model_id = $1), 0) + 1,
			$3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19
		)
		RETURNING `+modelVersionColumns,
		modelID, tenantID, in.ProviderID, in.LicenceID, in.ChecksumSHA256,
		provenanceJSON, permittedJSON, prohibitedJSON, workloadTypesJSON,
		languagesJSON, hardwareJSON, in.MinimumAcceleratorMemoryGB,
		securityJSON, perfJSON, inputJSON, outputJSON,
		retentionJSON, pricingJSON, requestedBy,
	)
	v, err := scanModelVersion(row)
	if err != nil {
		return ModelVersion{}, fmt.Errorf("insert model version draft: %w", err)
	}
	return v, nil
}

func updateModelVersionDraft(ctx context.Context, c conn, id uuid.UUID, in ModelVersionInput) (bool, error) {
	provenanceJSON, err := marshalOrEmpty(in.Provenance)
	if err != nil {
		return false, err
	}
	permittedJSON, _ := json.Marshal(in.PermittedGeographies)
	prohibitedJSON, _ := json.Marshal(in.ProhibitedGeographies)
	workloadTypesJSON, _ := json.Marshal(in.SupportedWorkloadTypes)
	languagesJSON, _ := json.Marshal(in.SupportedLanguages)
	hardwareJSON, err := marshalOrEmpty(in.HardwareRequirements)
	if err != nil {
		return false, err
	}
	securityJSON, err := marshalOrEmpty(in.SecurityProfile)
	if err != nil {
		return false, err
	}
	perfJSON, err := marshalOrEmpty(in.PerformanceMetadata)
	if err != nil {
		return false, err
	}
	inputJSON, _ := json.Marshal(in.InputTypes)
	outputJSON, _ := json.Marshal(in.OutputTypes)
	retentionJSON, err := marshalOrEmpty(in.RetentionPolicy)
	if err != nil {
		return false, err
	}
	pricingJSON, err := marshalOrEmpty(in.PricingMetadata)
	if err != nil {
		return false, err
	}

	tag, err := c.Exec(ctx, `
		UPDATE model_versions SET
			provider_id = $2, licence_id = $3, checksum_sha256 = $4, provenance = $5,
			permitted_geographies = $6, prohibited_geographies = $7, supported_workload_types = $8,
			supported_languages = $9, hardware_requirements = $10, minimum_accelerator_memory_gb = $11,
			security_profile = $12, performance_metadata = $13, input_types = $14, output_types = $15,
			retention_policy = $16, pricing_metadata = $17, updated_at = now()
		WHERE id = $1 AND status = 'draft'
	`, id, in.ProviderID, in.LicenceID, in.ChecksumSHA256, provenanceJSON,
		permittedJSON, prohibitedJSON, workloadTypesJSON,
		languagesJSON, hardwareJSON, in.MinimumAcceleratorMemoryGB,
		securityJSON, perfJSON, inputJSON, outputJSON,
		retentionJSON, pricingJSON,
	)
	if err != nil {
		return false, fmt.Errorf("update model version draft: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func getModelVersionByID(ctx context.Context, c conn, tenantID, id uuid.UUID) (ModelVersion, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+modelVersionColumns+` FROM model_versions WHERE enterprise_tenant_id = $1 AND id = $2`, tenantID, id)
	v, err := scanModelVersion(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return ModelVersion{}, false, nil
		}
		return ModelVersion{}, false, fmt.Errorf("get model version: %w", err)
	}
	return v, true, nil
}

func listModelVersions(ctx context.Context, c conn, tenantID, modelID uuid.UUID) ([]ModelVersion, error) {
	rows, err := c.Query(ctx, `
		SELECT `+modelVersionColumns+` FROM model_versions
		WHERE enterprise_tenant_id = $1 AND model_id = $2 ORDER BY version DESC
	`, tenantID, modelID)
	if err != nil {
		return nil, fmt.Errorf("list model versions: %w", err)
	}
	defer rows.Close()
	out := []ModelVersion{}
	for rows.Next() {
		v, err := scanModelVersion(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, v)
	}
	return out, rows.Err()
}

func markRequestedApproval(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE model_versions SET status = 'pending_approval', updated_at = now()
		WHERE id = $1 AND status = 'draft'
	`, id)
	if err != nil {
		return false, fmt.Errorf("mark requested approval: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func markApproved(ctx context.Context, c conn, id, approvedBy uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE model_versions SET status = 'approved', approved_by = $2, approved_at = now(), updated_at = now()
		WHERE id = $1 AND status = 'pending_approval'
	`, id, approvedBy)
	if err != nil {
		return false, fmt.Errorf("mark approved: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func markRejected(ctx context.Context, c conn, id uuid.UUID, reason string) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE model_versions SET status = 'rejected', rejected_reason = $2, updated_at = now()
		WHERE id = $1 AND status = 'pending_approval'
	`, id, reason)
	if err != nil {
		return false, fmt.Errorf("mark rejected: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func markRetired(ctx context.Context, c conn, id uuid.UUID, reason string) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE model_versions SET status = 'retired', retirement_reason = $2, retired_at = now(), updated_at = now()
		WHERE id = $1 AND status = 'approved'
	`, id, reason)
	if err != nil {
		return false, fmt.Errorf("mark retired: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func markRevoked(ctx context.Context, c conn, id uuid.UUID, reason string) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE model_versions SET status = 'revoked', revocation_reason = $2, revoked_at = now(), updated_at = now()
		WHERE id = $1 AND status IN ('approved', 'retired')
	`, id, reason)
	if err != nil {
		return false, fmt.Errorf("mark revoked: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

// ---------------------------------------------------------------------
// marketplace (Milestone 13: AI Model Exchange)
// ---------------------------------------------------------------------

func publishModelVersion(ctx context.Context, c conn, id uuid.UUID, pricePerUnit *float64, pricingUnit, currency string) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE model_versions SET
			visibility = 'public', price_per_unit = $2, pricing_unit = $3, currency = $4,
			published_at = COALESCE(published_at, now()), updated_at = now()
		WHERE id = $1 AND status = 'approved'
	`, id, pricePerUnit, pricingUnit, currency)
	if err != nil {
		return false, fmt.Errorf("publish model version: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func unpublishModelVersion(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE model_versions SET visibility = 'private', updated_at = now()
		WHERE id = $1 AND visibility = 'public'
	`, id)
	if err != nil {
		return false, fmt.Errorf("unpublish model version: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

// getMarketplaceModelVersion looks up a version by ID alone, with no tenant
// filter -- RLS (the owner's all-commands policy OR'd with
// model_versions_marketplace_read) is what actually determines whether the
// calling tenant may see it.
func getMarketplaceModelVersion(ctx context.Context, c conn, id uuid.UUID) (ModelVersion, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+modelVersionColumns+` FROM model_versions WHERE id = $1`, id)
	v, err := scanModelVersion(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return ModelVersion{}, false, nil
		}
		return ModelVersion{}, false, fmt.Errorf("get marketplace model version: %w", err)
	}
	return v, true, nil
}

// listMarketplaceModelVersions excludes the caller's own tenant's versions
// (they already have ListModels/ListVersions for those) and relies on RLS to
// further narrow to whatever this tenant is actually allowed to see: another
// tenant's public, approved versions, or private ones it holds an active
// grant for.
func listMarketplaceModelVersions(ctx context.Context, c conn, callerTenantID uuid.UUID) ([]ModelVersion, error) {
	rows, err := c.Query(ctx, `
		SELECT `+modelVersionColumns+` FROM model_versions
		WHERE enterprise_tenant_id <> $1 AND status = 'approved'
		ORDER BY published_at DESC NULLS LAST, created_at DESC
	`, callerTenantID)
	if err != nil {
		return nil, fmt.Errorf("list marketplace model versions: %w", err)
	}
	defer rows.Close()
	out := []ModelVersion{}
	for rows.Next() {
		v, err := scanModelVersion(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, v)
	}
	return out, rows.Err()
}

func listMarketplaceCapabilities(ctx context.Context, c conn, versionID uuid.UUID) ([]Capability, error) {
	rows, err := c.Query(ctx, `
		SELECT id, model_version_id, capability_key, description, created_at
		FROM model_capabilities WHERE model_version_id = $1 ORDER BY capability_key
	`, versionID)
	if err != nil {
		return nil, fmt.Errorf("list marketplace model capabilities: %w", err)
	}
	defer rows.Close()
	out := []Capability{}
	for rows.Next() {
		var capability Capability
		if err := rows.Scan(&capability.ID, &capability.ModelVersionID, &capability.CapabilityKey, &capability.Description, &capability.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, capability)
	}
	return out, rows.Err()
}

func listMarketplaceBenchmarks(ctx context.Context, c conn, versionID uuid.UUID) ([]Benchmark, error) {
	rows, err := c.Query(ctx, `
		SELECT id, model_version_id, benchmark_name, metric_name, metric_value, evaluated_at, created_at
		FROM model_benchmarks WHERE model_version_id = $1 ORDER BY evaluated_at DESC
	`, versionID)
	if err != nil {
		return nil, fmt.Errorf("list marketplace model benchmarks: %w", err)
	}
	defer rows.Close()
	out := []Benchmark{}
	for rows.Next() {
		var b Benchmark
		if err := rows.Scan(&b.ID, &b.ModelVersionID, &b.BenchmarkName, &b.MetricName, &b.MetricValue, &b.EvaluatedAt, &b.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, b)
	}
	return out, rows.Err()
}

func listMarketplaceSafetyEvaluations(ctx context.Context, c conn, versionID uuid.UUID) ([]SafetyEvaluation, error) {
	rows, err := c.Query(ctx, `
		SELECT id, model_version_id, evaluator, methodology, result, findings, evaluated_at, created_at
		FROM model_safety_evaluations WHERE model_version_id = $1 ORDER BY evaluated_at DESC
	`, versionID)
	if err != nil {
		return nil, fmt.Errorf("list marketplace model safety evaluations: %w", err)
	}
	defer rows.Close()
	out := []SafetyEvaluation{}
	for rows.Next() {
		var se SafetyEvaluation
		var findingsRaw []byte
		if err := rows.Scan(&se.ID, &se.ModelVersionID, &se.Evaluator, &se.Methodology, &se.Result, &findingsRaw, &se.EvaluatedAt, &se.CreatedAt); err != nil {
			return nil, err
		}
		if err := json.Unmarshal(findingsRaw, &se.Findings); err != nil {
			return nil, fmt.Errorf("unmarshal safety evaluation findings: %w", err)
		}
		out = append(out, se)
	}
	return out, rows.Err()
}

func listMarketplaceDeploymentProfiles(ctx context.Context, c conn, versionID uuid.UUID) ([]DeploymentProfile, error) {
	rows, err := c.Query(ctx, `
		SELECT id, model_version_id, profile_key, name, resource_requirements, created_at
		FROM model_deployment_profiles WHERE model_version_id = $1 ORDER BY profile_key
	`, versionID)
	if err != nil {
		return nil, fmt.Errorf("list marketplace model deployment profiles: %w", err)
	}
	defer rows.Close()
	out := []DeploymentProfile{}
	for rows.Next() {
		var p DeploymentProfile
		var resourceRaw []byte
		if err := rows.Scan(&p.ID, &p.ModelVersionID, &p.ProfileKey, &p.Name, &resourceRaw, &p.CreatedAt); err != nil {
			return nil, err
		}
		if err := json.Unmarshal(resourceRaw, &p.ResourceRequirements); err != nil {
			return nil, fmt.Errorf("unmarshal deployment profile resource requirements: %w", err)
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// model_access_grants
// ---------------------------------------------------------------------

const accessGrantColumns = `id, model_version_id, owner_tenant_id, grantee_tenant_id, price_per_unit_override, status, created_by, created_at`

func scanAccessGrant(row pgx.Row) (ModelAccessGrant, error) {
	var g ModelAccessGrant
	err := row.Scan(&g.ID, &g.ModelVersionID, &g.OwnerTenantID, &g.GranteeTenantID, &g.PricePerUnitOverride, &g.Status, &g.CreatedBy, &g.CreatedAt)
	return g, err
}

// createAccessGrant upserts on (model_version_id, grantee_tenant_id): issuing
// a grant again for the same tenant (e.g. to change the price override, or
// to re-invite a previously revoked tenant) updates the existing row rather
// than erroring, the same idempotent-grant shape
// capacityoffers.createGrant already established in Milestone 12.
func createAccessGrant(ctx context.Context, c conn, versionID, ownerTenantID, granteeTenantID, createdBy uuid.UUID, priceOverride *float64) (ModelAccessGrant, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO model_access_grants (model_version_id, owner_tenant_id, grantee_tenant_id, price_per_unit_override, created_by)
		VALUES ($1, $2, $3, $4, $5)
		ON CONFLICT (model_version_id, grantee_tenant_id) DO UPDATE SET
			price_per_unit_override = EXCLUDED.price_per_unit_override, status = 'active'
		RETURNING `+accessGrantColumns,
		versionID, ownerTenantID, granteeTenantID, priceOverride, createdBy,
	)
	g, err := scanAccessGrant(row)
	if err != nil {
		return ModelAccessGrant{}, fmt.Errorf("insert model access grant: %w", err)
	}
	return g, nil
}

func listAccessGrantsForVersion(ctx context.Context, c conn, versionID uuid.UUID) ([]ModelAccessGrant, error) {
	rows, err := c.Query(ctx, `SELECT `+accessGrantColumns+` FROM model_access_grants WHERE model_version_id = $1 ORDER BY created_at DESC`, versionID)
	if err != nil {
		return nil, fmt.Errorf("list model access grants: %w", err)
	}
	defer rows.Close()
	out := []ModelAccessGrant{}
	for rows.Next() {
		g, err := scanAccessGrant(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, g)
	}
	return out, rows.Err()
}

func listReceivedAccessGrants(ctx context.Context, c conn, granteeTenantID uuid.UUID) ([]ModelAccessGrant, error) {
	rows, err := c.Query(ctx, `SELECT `+accessGrantColumns+` FROM model_access_grants WHERE grantee_tenant_id = $1 AND status = 'active' ORDER BY created_at DESC`, granteeTenantID)
	if err != nil {
		return nil, fmt.Errorf("list received model access grants: %w", err)
	}
	defer rows.Close()
	out := []ModelAccessGrant{}
	for rows.Next() {
		g, err := scanAccessGrant(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, g)
	}
	return out, rows.Err()
}

func revokeAccessGrant(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `UPDATE model_access_grants SET status = 'revoked' WHERE id = $1 AND status = 'active'`, id)
	if err != nil {
		return false, fmt.Errorf("revoke model access grant: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

// activeGrantPriceOverride returns the caller tenant's active price override
// for a specific version, if any -- used to decorate marketplace listings and
// workload eligibility checks with the tenant's actual contracted price
// instead of the version's public base price.
func activeGrantPriceOverride(ctx context.Context, c conn, versionID, granteeTenantID uuid.UUID) (*float64, error) {
	var override *float64
	err := c.QueryRow(ctx, `
		SELECT price_per_unit_override FROM model_access_grants
		WHERE model_version_id = $1 AND grantee_tenant_id = $2 AND status = 'active'
	`, versionID, granteeTenantID).Scan(&override)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("get active grant price override: %w", err)
	}
	return override, nil
}

// ---------------------------------------------------------------------
// capabilities / benchmarks / safety evaluations / deployment profiles
// ---------------------------------------------------------------------

func createCapability(ctx context.Context, c conn, tenantID, versionID uuid.UUID, capabilityKey, description string) (Capability, error) {
	var capability Capability
	err := c.QueryRow(ctx, `
		INSERT INTO model_capabilities (enterprise_tenant_id, model_version_id, capability_key, description)
		VALUES ($1, $2, $3, $4)
		RETURNING id, model_version_id, capability_key, description, created_at
	`, tenantID, versionID, capabilityKey, description).Scan(&capability.ID, &capability.ModelVersionID, &capability.CapabilityKey, &capability.Description, &capability.CreatedAt)
	if err != nil {
		return Capability{}, fmt.Errorf("insert model capability: %w", err)
	}
	return capability, nil
}

func listCapabilities(ctx context.Context, c conn, tenantID, versionID uuid.UUID) ([]Capability, error) {
	rows, err := c.Query(ctx, `
		SELECT id, model_version_id, capability_key, description, created_at
		FROM model_capabilities WHERE enterprise_tenant_id = $1 AND model_version_id = $2 ORDER BY capability_key
	`, tenantID, versionID)
	if err != nil {
		return nil, fmt.Errorf("list model capabilities: %w", err)
	}
	defer rows.Close()
	out := []Capability{}
	for rows.Next() {
		var capability Capability
		if err := rows.Scan(&capability.ID, &capability.ModelVersionID, &capability.CapabilityKey, &capability.Description, &capability.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, capability)
	}
	return out, rows.Err()
}

func createBenchmark(ctx context.Context, c conn, tenantID, versionID uuid.UUID, benchmarkName, metricName string, metricValue float64, evaluatedAt any) (Benchmark, error) {
	var b Benchmark
	err := c.QueryRow(ctx, `
		INSERT INTO model_benchmarks (enterprise_tenant_id, model_version_id, benchmark_name, metric_name, metric_value, evaluated_at)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, model_version_id, benchmark_name, metric_name, metric_value, evaluated_at, created_at
	`, tenantID, versionID, benchmarkName, metricName, metricValue, evaluatedAt).Scan(
		&b.ID, &b.ModelVersionID, &b.BenchmarkName, &b.MetricName, &b.MetricValue, &b.EvaluatedAt, &b.CreatedAt)
	if err != nil {
		return Benchmark{}, fmt.Errorf("insert model benchmark: %w", err)
	}
	return b, nil
}

func listBenchmarks(ctx context.Context, c conn, tenantID, versionID uuid.UUID) ([]Benchmark, error) {
	rows, err := c.Query(ctx, `
		SELECT id, model_version_id, benchmark_name, metric_name, metric_value, evaluated_at, created_at
		FROM model_benchmarks WHERE enterprise_tenant_id = $1 AND model_version_id = $2 ORDER BY evaluated_at DESC
	`, tenantID, versionID)
	if err != nil {
		return nil, fmt.Errorf("list model benchmarks: %w", err)
	}
	defer rows.Close()
	out := []Benchmark{}
	for rows.Next() {
		var b Benchmark
		if err := rows.Scan(&b.ID, &b.ModelVersionID, &b.BenchmarkName, &b.MetricName, &b.MetricValue, &b.EvaluatedAt, &b.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, b)
	}
	return out, rows.Err()
}

func createSafetyEvaluation(ctx context.Context, c conn, tenantID, versionID uuid.UUID, evaluator, methodology, result string, findings map[string]any, evaluatedAt any) (SafetyEvaluation, error) {
	findingsJSON, err := marshalOrEmpty(findings)
	if err != nil {
		return SafetyEvaluation{}, err
	}
	var se SafetyEvaluation
	var findingsRaw []byte
	err = c.QueryRow(ctx, `
		INSERT INTO model_safety_evaluations (enterprise_tenant_id, model_version_id, evaluator, methodology, result, findings, evaluated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING id, model_version_id, evaluator, methodology, result, findings, evaluated_at, created_at
	`, tenantID, versionID, evaluator, methodology, result, findingsJSON, evaluatedAt).Scan(
		&se.ID, &se.ModelVersionID, &se.Evaluator, &se.Methodology, &se.Result, &findingsRaw, &se.EvaluatedAt, &se.CreatedAt)
	if err != nil {
		return SafetyEvaluation{}, fmt.Errorf("insert model safety evaluation: %w", err)
	}
	if err := json.Unmarshal(findingsRaw, &se.Findings); err != nil {
		return SafetyEvaluation{}, fmt.Errorf("unmarshal safety evaluation findings: %w", err)
	}
	return se, nil
}

func listSafetyEvaluations(ctx context.Context, c conn, tenantID, versionID uuid.UUID) ([]SafetyEvaluation, error) {
	rows, err := c.Query(ctx, `
		SELECT id, model_version_id, evaluator, methodology, result, findings, evaluated_at, created_at
		FROM model_safety_evaluations WHERE enterprise_tenant_id = $1 AND model_version_id = $2 ORDER BY evaluated_at DESC
	`, tenantID, versionID)
	if err != nil {
		return nil, fmt.Errorf("list model safety evaluations: %w", err)
	}
	defer rows.Close()
	out := []SafetyEvaluation{}
	for rows.Next() {
		var se SafetyEvaluation
		var findingsRaw []byte
		if err := rows.Scan(&se.ID, &se.ModelVersionID, &se.Evaluator, &se.Methodology, &se.Result, &findingsRaw, &se.EvaluatedAt, &se.CreatedAt); err != nil {
			return nil, err
		}
		if err := json.Unmarshal(findingsRaw, &se.Findings); err != nil {
			return nil, fmt.Errorf("unmarshal safety evaluation findings: %w", err)
		}
		out = append(out, se)
	}
	return out, rows.Err()
}

func createDeploymentProfile(ctx context.Context, c conn, tenantID, versionID uuid.UUID, profileKey, name string, resourceRequirements map[string]any) (DeploymentProfile, error) {
	resourceJSON, err := marshalOrEmpty(resourceRequirements)
	if err != nil {
		return DeploymentProfile{}, err
	}
	var p DeploymentProfile
	var resourceRaw []byte
	err = c.QueryRow(ctx, `
		INSERT INTO model_deployment_profiles (enterprise_tenant_id, model_version_id, profile_key, name, resource_requirements)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, model_version_id, profile_key, name, resource_requirements, created_at
	`, tenantID, versionID, profileKey, name, resourceJSON).Scan(&p.ID, &p.ModelVersionID, &p.ProfileKey, &p.Name, &resourceRaw, &p.CreatedAt)
	if err != nil {
		return DeploymentProfile{}, fmt.Errorf("insert model deployment profile: %w", err)
	}
	if err := json.Unmarshal(resourceRaw, &p.ResourceRequirements); err != nil {
		return DeploymentProfile{}, fmt.Errorf("unmarshal deployment profile resource requirements: %w", err)
	}
	return p, nil
}

func listDeploymentProfiles(ctx context.Context, c conn, tenantID, versionID uuid.UUID) ([]DeploymentProfile, error) {
	rows, err := c.Query(ctx, `
		SELECT id, model_version_id, profile_key, name, resource_requirements, created_at
		FROM model_deployment_profiles WHERE enterprise_tenant_id = $1 AND model_version_id = $2 ORDER BY profile_key
	`, tenantID, versionID)
	if err != nil {
		return nil, fmt.Errorf("list model deployment profiles: %w", err)
	}
	defer rows.Close()
	out := []DeploymentProfile{}
	for rows.Next() {
		var p DeploymentProfile
		var resourceRaw []byte
		if err := rows.Scan(&p.ID, &p.ModelVersionID, &p.ProfileKey, &p.Name, &resourceRaw, &p.CreatedAt); err != nil {
			return nil, err
		}
		if err := json.Unmarshal(resourceRaw, &p.ResourceRequirements); err != nil {
			return nil, fmt.Errorf("unmarshal deployment profile resource requirements: %w", err)
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// providers / licences (global, read-only catalogue)
// ---------------------------------------------------------------------

func listProviders(ctx context.Context, c conn) ([]Provider, error) {
	rows, err := c.Query(ctx, `SELECT id, key, name, website, status, onboarded_by, created_at FROM model_providers ORDER BY name`)
	if err != nil {
		return nil, fmt.Errorf("list model providers: %w", err)
	}
	defer rows.Close()
	out := []Provider{}
	for rows.Next() {
		var p Provider
		if err := rows.Scan(&p.ID, &p.Key, &p.Name, &p.Website, &p.Status, &p.OnboardedBy, &p.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func getProviderByKey(ctx context.Context, c conn, key string) (Provider, bool, error) {
	var p Provider
	err := c.QueryRow(ctx, `
		SELECT id, key, name, website, status, onboarded_by, created_at FROM model_providers WHERE key = $1
	`, key).Scan(&p.ID, &p.Key, &p.Name, &p.Website, &p.Status, &p.OnboardedBy, &p.CreatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Provider{}, false, nil
		}
		return Provider{}, false, fmt.Errorf("get model provider by key: %w", err)
	}
	return p, true, nil
}

// createProvider is Milestone 13's provider onboarding: model_providers was
// previously seed-data-only reference data (Milestone 4), the same gap
// jurisdictions/regions had before Milestone 2 gave them real create
// endpoints.
func createProvider(ctx context.Context, c conn, key, name, website string, onboardedBy uuid.UUID) (Provider, error) {
	var p Provider
	err := c.QueryRow(ctx, `
		INSERT INTO model_providers (key, name, website, onboarded_by)
		VALUES ($1, $2, $3, $4)
		RETURNING id, key, name, website, status, onboarded_by, created_at
	`, key, name, website, onboardedBy).Scan(&p.ID, &p.Key, &p.Name, &p.Website, &p.Status, &p.OnboardedBy, &p.CreatedAt)
	if err != nil {
		return Provider{}, fmt.Errorf("insert model provider: %w", err)
	}
	return p, nil
}

func setProviderStatus(ctx context.Context, c conn, id uuid.UUID, newStatus, requiredCurrentStatus string) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE model_providers SET status = $2 WHERE id = $1 AND status = $3
	`, id, newStatus, requiredCurrentStatus)
	if err != nil {
		return false, fmt.Errorf("update model provider status: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func listLicences(ctx context.Context, c conn) ([]Licence, error) {
	rows, err := c.Query(ctx, `SELECT id, key, name, terms_url, allows_commercial_use, allows_redistribution, created_at FROM model_licences ORDER BY name`)
	if err != nil {
		return nil, fmt.Errorf("list model licences: %w", err)
	}
	defer rows.Close()
	out := []Licence{}
	for rows.Next() {
		var l Licence
		if err := rows.Scan(&l.ID, &l.Key, &l.Name, &l.TermsURL, &l.AllowsCommercialUse, &l.AllowsRedistribution, &l.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, l)
	}
	return out, rows.Err()
}

func getLicenceByID(ctx context.Context, c conn, id uuid.UUID) (Licence, bool, error) {
	var l Licence
	err := c.QueryRow(ctx, `
		SELECT id, key, name, terms_url, allows_commercial_use, allows_redistribution, created_at
		FROM model_licences WHERE id = $1
	`, id).Scan(&l.ID, &l.Key, &l.Name, &l.TermsURL, &l.AllowsCommercialUse, &l.AllowsRedistribution, &l.CreatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Licence{}, false, nil
		}
		return Licence{}, false, fmt.Errorf("get model licence: %w", err)
	}
	return l, true, nil
}

// ---------------------------------------------------------------------
// model_artefacts (join to artefact_uploads)
// ---------------------------------------------------------------------

func linkModelArtefact(ctx context.Context, c conn, tenantID, versionID, artefactUploadID uuid.UUID, role, checksum string) (ArtefactLink, error) {
	var l ArtefactLink
	err := c.QueryRow(ctx, `
		INSERT INTO model_artefacts (enterprise_tenant_id, model_version_id, artefact_upload_id, role, checksum_sha256)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, model_version_id, artefact_upload_id, role, checksum_sha256, created_at
	`, tenantID, versionID, artefactUploadID, role, checksum).Scan(&l.ID, &l.ModelVersionID, &l.ArtefactUploadID, &l.Role, &l.ChecksumSHA256, &l.CreatedAt)
	if err != nil {
		return ArtefactLink{}, fmt.Errorf("link model artefact: %w", err)
	}
	return l, nil
}

func listModelArtefacts(ctx context.Context, c conn, tenantID, versionID uuid.UUID) ([]ArtefactLink, error) {
	rows, err := c.Query(ctx, `
		SELECT id, model_version_id, artefact_upload_id, role, checksum_sha256, created_at
		FROM model_artefacts WHERE enterprise_tenant_id = $1 AND model_version_id = $2 ORDER BY created_at
	`, tenantID, versionID)
	if err != nil {
		return nil, fmt.Errorf("list model artefacts: %w", err)
	}
	defer rows.Close()
	out := []ArtefactLink{}
	for rows.Next() {
		var l ArtefactLink
		if err := rows.Scan(&l.ID, &l.ModelVersionID, &l.ArtefactUploadID, &l.Role, &l.ChecksumSHA256, &l.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, l)
	}
	return out, rows.Err()
}
