package workloads

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
// workloads
// ---------------------------------------------------------------------

const workloadColumns = `id, enterprise_tenant_id, workload_key, workload_type, name, description, owner_user_id, status, created_at, updated_at`

func scanWorkload(row pgx.Row) (Workload, error) {
	var w Workload
	err := row.Scan(&w.ID, &w.TenantID, &w.WorkloadKey, &w.WorkloadType, &w.Name, &w.Description, &w.OwnerUserID, &w.Status, &w.CreatedAt, &w.UpdatedAt)
	return w, err
}

func createWorkload(ctx context.Context, c conn, tenantID uuid.UUID, workloadKey, workloadType, name, description string, ownerUserID uuid.UUID) (Workload, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO workloads (enterprise_tenant_id, workload_key, workload_type, name, description, owner_user_id)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING `+workloadColumns,
		tenantID, workloadKey, workloadType, name, description, ownerUserID,
	)
	w, err := scanWorkload(row)
	if err != nil {
		return Workload{}, fmt.Errorf("insert workload: %w", err)
	}
	return w, nil
}

func getWorkloadByID(ctx context.Context, c conn, tenantID, id uuid.UUID) (Workload, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+workloadColumns+` FROM workloads WHERE enterprise_tenant_id = $1 AND id = $2`, tenantID, id)
	w, err := scanWorkload(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Workload{}, false, nil
		}
		return Workload{}, false, fmt.Errorf("get workload: %w", err)
	}
	return w, true, nil
}

func getWorkloadByKey(ctx context.Context, c conn, tenantID uuid.UUID, workloadKey string) (Workload, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+workloadColumns+` FROM workloads WHERE enterprise_tenant_id = $1 AND workload_key = $2`, tenantID, workloadKey)
	w, err := scanWorkload(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Workload{}, false, nil
		}
		return Workload{}, false, fmt.Errorf("get workload by key: %w", err)
	}
	return w, true, nil
}

func listWorkloads(ctx context.Context, c conn, tenantID uuid.UUID) ([]Workload, error) {
	rows, err := c.Query(ctx, `SELECT `+workloadColumns+` FROM workloads WHERE enterprise_tenant_id = $1 ORDER BY created_at DESC`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list workloads: %w", err)
	}
	defer rows.Close()
	out := []Workload{}
	for rows.Next() {
		w, err := scanWorkload(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, w)
	}
	return out, rows.Err()
}

func markWorkloadRetired(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `UPDATE workloads SET status = 'retired', updated_at = now() WHERE id = $1 AND status = 'active'`, id)
	if err != nil {
		return false, fmt.Errorf("mark workload retired: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

// ---------------------------------------------------------------------
// workload_versions
// ---------------------------------------------------------------------

const versionColumns = `
	id, workload_id, enterprise_tenant_id, version, status, container_image_id, model_version_id,
	resource_requirements, network_requirements, storage_requirements, security_requirements,
	residency_requirements, scaling_policy, retention_policy, deployment_approval_required,
	requested_by, approved_by, published_at, retired_at, retirement_reason, created_at, updated_at
`

func scanVersion(row pgx.Row) (WorkloadVersion, error) {
	var v WorkloadVersion
	var resourceRaw, networkRaw, storageRaw, securityRaw, residencyRaw, scalingRaw, retentionRaw []byte
	err := row.Scan(
		&v.ID, &v.WorkloadID, &v.TenantID, &v.Version, &v.Status, &v.ContainerImageID, &v.ModelVersionID,
		&resourceRaw, &networkRaw, &storageRaw, &securityRaw,
		&residencyRaw, &scalingRaw, &retentionRaw, &v.DeploymentApprovalRequired,
		&v.RequestedBy, &v.ApprovedBy, &v.PublishedAt, &v.RetiredAt, &v.RetirementReason, &v.CreatedAt, &v.UpdatedAt,
	)
	if err != nil {
		return WorkloadVersion{}, err
	}
	for _, pair := range []struct {
		raw []byte
		dst any
	}{
		{resourceRaw, &v.ResourceRequirements}, {networkRaw, &v.NetworkRequirements}, {storageRaw, &v.StorageRequirements},
		{securityRaw, &v.SecurityRequirements}, {residencyRaw, &v.ResidencyRequirements}, {scalingRaw, &v.ScalingPolicy},
		{retentionRaw, &v.RetentionPolicy},
	} {
		if err := json.Unmarshal(pair.raw, pair.dst); err != nil {
			return WorkloadVersion{}, fmt.Errorf("unmarshal workload version field: %w", err)
		}
	}
	return v, nil
}

// VersionInput carries every field a new draft (or draft edit) sets.
type VersionInput struct {
	ContainerImageID           *uuid.UUID
	ModelVersionID             *uuid.UUID
	ResourceRequirements       map[string]any
	NetworkRequirements        map[string]any
	StorageRequirements        map[string]any
	SecurityRequirements       map[string]any
	ResidencyRequirements      map[string]any
	ScalingPolicy              map[string]any
	RetentionPolicy            map[string]any
	DeploymentApprovalRequired bool
}

func marshalOrEmpty(v any) ([]byte, error) {
	if v == nil {
		return []byte("{}"), nil
	}
	return json.Marshal(v)
}

func createVersionDraft(ctx context.Context, c conn, tenantID, workloadID uuid.UUID, requestedBy uuid.UUID, in VersionInput) (WorkloadVersion, error) {
	resourceJSON, err := marshalOrEmpty(in.ResourceRequirements)
	if err != nil {
		return WorkloadVersion{}, err
	}
	networkJSON, err := marshalOrEmpty(in.NetworkRequirements)
	if err != nil {
		return WorkloadVersion{}, err
	}
	storageJSON, err := marshalOrEmpty(in.StorageRequirements)
	if err != nil {
		return WorkloadVersion{}, err
	}
	securityJSON, err := marshalOrEmpty(in.SecurityRequirements)
	if err != nil {
		return WorkloadVersion{}, err
	}
	residencyJSON, err := marshalOrEmpty(in.ResidencyRequirements)
	if err != nil {
		return WorkloadVersion{}, err
	}
	scalingJSON, err := marshalOrEmpty(in.ScalingPolicy)
	if err != nil {
		return WorkloadVersion{}, err
	}
	retentionJSON, err := marshalOrEmpty(in.RetentionPolicy)
	if err != nil {
		return WorkloadVersion{}, err
	}

	row := c.QueryRow(ctx, `
		INSERT INTO workload_versions (
			workload_id, enterprise_tenant_id, version, container_image_id, model_version_id,
			resource_requirements, network_requirements, storage_requirements, security_requirements,
			residency_requirements, scaling_policy, retention_policy, deployment_approval_required, requested_by
		)
		VALUES (
			$1, $2,
			COALESCE((SELECT max(version) FROM workload_versions WHERE workload_id = $1), 0) + 1,
			$3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
		)
		RETURNING `+versionColumns,
		workloadID, tenantID, in.ContainerImageID, in.ModelVersionID,
		resourceJSON, networkJSON, storageJSON, securityJSON,
		residencyJSON, scalingJSON, retentionJSON, in.DeploymentApprovalRequired, requestedBy,
	)
	v, err := scanVersion(row)
	if err != nil {
		return WorkloadVersion{}, fmt.Errorf("insert workload version draft: %w", err)
	}
	return v, nil
}

func updateVersionDraft(ctx context.Context, c conn, id uuid.UUID, in VersionInput) (bool, error) {
	resourceJSON, err := marshalOrEmpty(in.ResourceRequirements)
	if err != nil {
		return false, err
	}
	networkJSON, err := marshalOrEmpty(in.NetworkRequirements)
	if err != nil {
		return false, err
	}
	storageJSON, err := marshalOrEmpty(in.StorageRequirements)
	if err != nil {
		return false, err
	}
	securityJSON, err := marshalOrEmpty(in.SecurityRequirements)
	if err != nil {
		return false, err
	}
	residencyJSON, err := marshalOrEmpty(in.ResidencyRequirements)
	if err != nil {
		return false, err
	}
	scalingJSON, err := marshalOrEmpty(in.ScalingPolicy)
	if err != nil {
		return false, err
	}
	retentionJSON, err := marshalOrEmpty(in.RetentionPolicy)
	if err != nil {
		return false, err
	}

	tag, err := c.Exec(ctx, `
		UPDATE workload_versions SET
			container_image_id = $2, model_version_id = $3, resource_requirements = $4,
			network_requirements = $5, storage_requirements = $6, security_requirements = $7,
			residency_requirements = $8, scaling_policy = $9, retention_policy = $10,
			deployment_approval_required = $11, updated_at = now()
		WHERE id = $1 AND status = 'draft'
	`, id, in.ContainerImageID, in.ModelVersionID, resourceJSON,
		networkJSON, storageJSON, securityJSON,
		residencyJSON, scalingJSON, retentionJSON, in.DeploymentApprovalRequired,
	)
	if err != nil {
		return false, fmt.Errorf("update workload version draft: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func getVersionByID(ctx context.Context, c conn, tenantID, id uuid.UUID) (WorkloadVersion, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+versionColumns+` FROM workload_versions WHERE enterprise_tenant_id = $1 AND id = $2`, tenantID, id)
	v, err := scanVersion(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return WorkloadVersion{}, false, nil
		}
		return WorkloadVersion{}, false, fmt.Errorf("get workload version: %w", err)
	}
	return v, true, nil
}

func listVersions(ctx context.Context, c conn, tenantID, workloadID uuid.UUID) ([]WorkloadVersion, error) {
	rows, err := c.Query(ctx, `
		SELECT `+versionColumns+` FROM workload_versions
		WHERE enterprise_tenant_id = $1 AND workload_id = $2 ORDER BY version DESC
	`, tenantID, workloadID)
	if err != nil {
		return nil, fmt.Errorf("list workload versions: %w", err)
	}
	defer rows.Close()
	out := []WorkloadVersion{}
	for rows.Next() {
		v, err := scanVersion(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, v)
	}
	return out, rows.Err()
}

func markRequestedPublish(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE workload_versions SET status = 'pending_publish', updated_at = now()
		WHERE id = $1 AND status = 'draft'
	`, id)
	if err != nil {
		return false, fmt.Errorf("mark requested publish: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func markPublished(ctx context.Context, c conn, id, approvedBy uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE workload_versions SET status = 'published', approved_by = $2, published_at = now(), updated_at = now()
		WHERE id = $1 AND status = 'pending_publish'
	`, id, approvedBy)
	if err != nil {
		return false, fmt.Errorf("mark published: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func markDeprecated(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE workload_versions SET status = 'deprecated', updated_at = now()
		WHERE id = $1 AND status = 'published'
	`, id)
	if err != nil {
		return false, fmt.Errorf("mark deprecated: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func markVersionRetired(ctx context.Context, c conn, id uuid.UUID, reason string) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE workload_versions SET status = 'retired', retirement_reason = $2, retired_at = now(), updated_at = now()
		WHERE id = $1 AND status IN ('published', 'deprecated')
	`, id, reason)
	if err != nil {
		return false, fmt.Errorf("mark version retired: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

// ---------------------------------------------------------------------
// cross-module validation: image/model-version selectability
// ---------------------------------------------------------------------

// imageIsApproved reports whether a container image exists in this tenant
// and is currently in the 'approved' state -- a pending, blocked, or
// revoked image can never be selected for a new workload version.
func imageIsApproved(ctx context.Context, c conn, tenantID, imageID uuid.UUID) (bool, error) {
	var status string
	err := c.QueryRow(ctx, `SELECT status FROM container_images WHERE enterprise_tenant_id = $1 AND id = $2`, tenantID, imageID).Scan(&status)
	if err != nil {
		if err == pgx.ErrNoRows {
			return false, nil
		}
		return false, fmt.Errorf("check image approval status: %w", err)
	}
	return status == "approved", nil
}

// modelVersionApprovalAndGeography returns the model version's status and
// permitted/prohibited geography lists, used to enforce that only an
// approved model version can be selected, and that the workload's declared
// residency requirements are compatible with the model's geographic
// restrictions.
func modelVersionApprovalAndGeography(ctx context.Context, c conn, tenantID, modelVersionID uuid.UUID) (status string, permitted, prohibited []string, err error) {
	var permittedRaw, prohibitedRaw []byte
	err = c.QueryRow(ctx, `
		SELECT status, permitted_geographies, prohibited_geographies
		FROM model_versions WHERE enterprise_tenant_id = $1 AND id = $2
	`, tenantID, modelVersionID).Scan(&status, &permittedRaw, &prohibitedRaw)
	if err != nil {
		if err == pgx.ErrNoRows {
			return "", nil, nil, nil
		}
		return "", nil, nil, fmt.Errorf("get model version for validation: %w", err)
	}
	if err := json.Unmarshal(permittedRaw, &permitted); err != nil {
		return "", nil, nil, fmt.Errorf("unmarshal permitted geographies: %w", err)
	}
	if err := json.Unmarshal(prohibitedRaw, &prohibited); err != nil {
		return "", nil, nil, fmt.Errorf("unmarshal prohibited geographies: %w", err)
	}
	return status, permitted, prohibited, nil
}

// ---------------------------------------------------------------------
// workload_components / workload_health_checks
// ---------------------------------------------------------------------

func createComponent(ctx context.Context, c conn, tenantID, versionID, containerImageID uuid.UUID, componentKey, name string, command, args []string, env map[string]any, isPrimary bool) (Component, error) {
	commandJSON, _ := json.Marshal(command)
	argsJSON, _ := json.Marshal(args)
	envJSON, err := marshalOrEmpty(env)
	if err != nil {
		return Component{}, err
	}
	var comp Component
	var commandRaw, argsRaw, envRaw []byte
	err = c.QueryRow(ctx, `
		INSERT INTO workload_components (enterprise_tenant_id, workload_version_id, component_key, name, container_image_id, command, args, env, is_primary)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		RETURNING id, workload_version_id, component_key, name, container_image_id, command, args, env, is_primary, created_at
	`, tenantID, versionID, componentKey, name, containerImageID, commandJSON, argsJSON, envJSON, isPrimary).Scan(
		&comp.ID, &comp.WorkloadVersionID, &comp.ComponentKey, &comp.Name, &comp.ContainerImageID,
		&commandRaw, &argsRaw, &envRaw, &comp.IsPrimary, &comp.CreatedAt)
	if err != nil {
		return Component{}, fmt.Errorf("insert workload component: %w", err)
	}
	if err := json.Unmarshal(commandRaw, &comp.Command); err != nil {
		return Component{}, fmt.Errorf("unmarshal command: %w", err)
	}
	if err := json.Unmarshal(argsRaw, &comp.Args); err != nil {
		return Component{}, fmt.Errorf("unmarshal args: %w", err)
	}
	if err := json.Unmarshal(envRaw, &comp.Env); err != nil {
		return Component{}, fmt.Errorf("unmarshal env: %w", err)
	}
	return comp, nil
}

func listComponents(ctx context.Context, c conn, tenantID, versionID uuid.UUID) ([]Component, error) {
	rows, err := c.Query(ctx, `
		SELECT id, workload_version_id, component_key, name, container_image_id, command, args, env, is_primary, created_at
		FROM workload_components WHERE enterprise_tenant_id = $1 AND workload_version_id = $2 ORDER BY component_key
	`, tenantID, versionID)
	if err != nil {
		return nil, fmt.Errorf("list workload components: %w", err)
	}
	defer rows.Close()
	out := []Component{}
	for rows.Next() {
		var comp Component
		var commandRaw, argsRaw, envRaw []byte
		if err := rows.Scan(&comp.ID, &comp.WorkloadVersionID, &comp.ComponentKey, &comp.Name, &comp.ContainerImageID,
			&commandRaw, &argsRaw, &envRaw, &comp.IsPrimary, &comp.CreatedAt); err != nil {
			return nil, err
		}
		if err := json.Unmarshal(commandRaw, &comp.Command); err != nil {
			return nil, fmt.Errorf("unmarshal command: %w", err)
		}
		if err := json.Unmarshal(argsRaw, &comp.Args); err != nil {
			return nil, fmt.Errorf("unmarshal args: %w", err)
		}
		if err := json.Unmarshal(envRaw, &comp.Env); err != nil {
			return nil, fmt.Errorf("unmarshal env: %w", err)
		}
		out = append(out, comp)
	}
	return out, rows.Err()
}

func createHealthCheck(ctx context.Context, c conn, tenantID, componentID uuid.UUID, checkType, path string, port *int, command []string, intervalSeconds, timeoutSeconds, failureThreshold int) (HealthCheck, error) {
	commandJSON, _ := json.Marshal(command)
	var hc HealthCheck
	var commandRaw []byte
	err := c.QueryRow(ctx, `
		INSERT INTO workload_health_checks (enterprise_tenant_id, workload_component_id, check_type, path, port, command, interval_seconds, timeout_seconds, failure_threshold)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		RETURNING id, workload_component_id, check_type, path, port, command, interval_seconds, timeout_seconds, failure_threshold, created_at
	`, tenantID, componentID, checkType, path, port, commandJSON, intervalSeconds, timeoutSeconds, failureThreshold).Scan(
		&hc.ID, &hc.WorkloadComponentID, &hc.CheckType, &hc.Path, &hc.Port, &commandRaw, &hc.IntervalSeconds, &hc.TimeoutSeconds, &hc.FailureThreshold, &hc.CreatedAt)
	if err != nil {
		return HealthCheck{}, fmt.Errorf("insert workload health check: %w", err)
	}
	if err := json.Unmarshal(commandRaw, &hc.Command); err != nil {
		return HealthCheck{}, fmt.Errorf("unmarshal health check command: %w", err)
	}
	return hc, nil
}

func listHealthChecks(ctx context.Context, c conn, tenantID, componentID uuid.UUID) ([]HealthCheck, error) {
	rows, err := c.Query(ctx, `
		SELECT id, workload_component_id, check_type, path, port, command, interval_seconds, timeout_seconds, failure_threshold, created_at
		FROM workload_health_checks WHERE enterprise_tenant_id = $1 AND workload_component_id = $2 ORDER BY created_at
	`, tenantID, componentID)
	if err != nil {
		return nil, fmt.Errorf("list workload health checks: %w", err)
	}
	defer rows.Close()
	out := []HealthCheck{}
	for rows.Next() {
		var hc HealthCheck
		var commandRaw []byte
		if err := rows.Scan(&hc.ID, &hc.WorkloadComponentID, &hc.CheckType, &hc.Path, &hc.Port, &commandRaw, &hc.IntervalSeconds, &hc.TimeoutSeconds, &hc.FailureThreshold, &hc.CreatedAt); err != nil {
			return nil, err
		}
		if err := json.Unmarshal(commandRaw, &hc.Command); err != nil {
			return nil, fmt.Errorf("unmarshal health check command: %w", err)
		}
		out = append(out, hc)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// workload_artefacts / workload_version_sboms
// ---------------------------------------------------------------------

func linkArtefact(ctx context.Context, c conn, tenantID, versionID, artefactUploadID uuid.UUID, role string) (ArtefactLink, error) {
	var l ArtefactLink
	err := c.QueryRow(ctx, `
		INSERT INTO workload_artefacts (enterprise_tenant_id, workload_version_id, artefact_upload_id, role)
		VALUES ($1, $2, $3, $4)
		RETURNING id, workload_version_id, artefact_upload_id, role, created_at
	`, tenantID, versionID, artefactUploadID, role).Scan(&l.ID, &l.WorkloadVersionID, &l.ArtefactUploadID, &l.Role, &l.CreatedAt)
	if err != nil {
		return ArtefactLink{}, fmt.Errorf("link workload artefact: %w", err)
	}
	return l, nil
}

func listArtefactLinks(ctx context.Context, c conn, tenantID, versionID uuid.UUID) ([]ArtefactLink, error) {
	rows, err := c.Query(ctx, `
		SELECT id, workload_version_id, artefact_upload_id, role, created_at
		FROM workload_artefacts WHERE enterprise_tenant_id = $1 AND workload_version_id = $2 ORDER BY created_at
	`, tenantID, versionID)
	if err != nil {
		return nil, fmt.Errorf("list workload artefact links: %w", err)
	}
	defer rows.Close()
	out := []ArtefactLink{}
	for rows.Next() {
		var l ArtefactLink
		if err := rows.Scan(&l.ID, &l.WorkloadVersionID, &l.ArtefactUploadID, &l.Role, &l.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, l)
	}
	return out, rows.Err()
}

func linkSBOM(ctx context.Context, c conn, tenantID, versionID, sbomID uuid.UUID) (SBOMLink, error) {
	var l SBOMLink
	err := c.QueryRow(ctx, `
		INSERT INTO workload_version_sboms (enterprise_tenant_id, workload_version_id, sbom_id)
		VALUES ($1, $2, $3)
		RETURNING id, workload_version_id, sbom_id, created_at
	`, tenantID, versionID, sbomID).Scan(&l.ID, &l.WorkloadVersionID, &l.SBOMID, &l.CreatedAt)
	if err != nil {
		return SBOMLink{}, fmt.Errorf("link workload sbom: %w", err)
	}
	return l, nil
}

func listSBOMLinks(ctx context.Context, c conn, tenantID, versionID uuid.UUID) ([]SBOMLink, error) {
	rows, err := c.Query(ctx, `
		SELECT id, workload_version_id, sbom_id, created_at
		FROM workload_version_sboms WHERE enterprise_tenant_id = $1 AND workload_version_id = $2 ORDER BY created_at
	`, tenantID, versionID)
	if err != nil {
		return nil, fmt.Errorf("list workload sbom links: %w", err)
	}
	defer rows.Close()
	out := []SBOMLink{}
	for rows.Next() {
		var l SBOMLink
		if err := rows.Scan(&l.ID, &l.WorkloadVersionID, &l.SBOMID, &l.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, l)
	}
	return out, rows.Err()
}
