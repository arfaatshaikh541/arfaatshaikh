package deployments

import (
	"context"
	"encoding/json"
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
// Deployments
// ---------------------------------------------------------------------

const deploymentColumns = `id, enterprise_tenant_id, operator_id, cluster_agent_id, workload_version_id,
	capacity_reservation_id, namespace, replica_count, status, requested_by, created_at, updated_at`

func scanDeployment(row pgx.Row) (Deployment, error) {
	var d Deployment
	err := row.Scan(&d.ID, &d.EnterpriseTenantID, &d.OperatorID, &d.ClusterAgentID, &d.WorkloadVersionID,
		&d.CapacityReservationID, &d.Namespace, &d.ReplicaCount, &d.Status, &d.RequestedBy, &d.CreatedAt, &d.UpdatedAt)
	return d, err
}

func createDeployment(ctx context.Context, c conn, tenantID, operatorID, clusterAgentID, workloadVersionID, reservationID uuid.UUID, namespace string, replicaCount int, requestedBy uuid.UUID) (Deployment, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO deployments (
			enterprise_tenant_id, operator_id, cluster_agent_id, workload_version_id,
			capacity_reservation_id, namespace, replica_count, requested_by
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		RETURNING `+deploymentColumns, tenantID, operatorID, clusterAgentID, workloadVersionID, reservationID, namespace, replicaCount, requestedBy)
	d, err := scanDeployment(row)
	if err != nil {
		return Deployment{}, fmt.Errorf("insert deployment: %w", err)
	}
	return d, nil
}

func getDeploymentByID(ctx context.Context, c conn, tenantID, id uuid.UUID) (Deployment, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+deploymentColumns+` FROM deployments WHERE id = $1 AND enterprise_tenant_id = $2`, id, tenantID)
	d, err := scanDeployment(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Deployment{}, false, nil
		}
		return Deployment{}, false, fmt.Errorf("get deployment: %w", err)
	}
	return d, true, nil
}

func listDeploymentsForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]Deployment, error) {
	rows, err := c.Query(ctx, `SELECT `+deploymentColumns+` FROM deployments WHERE enterprise_tenant_id = $1 ORDER BY created_at DESC`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list deployments: %w", err)
	}
	defer rows.Close()
	out := []Deployment{}
	for rows.Next() {
		d, err := scanDeployment(rows)
		if err != nil {
			return nil, fmt.Errorf("scan deployment: %w", err)
		}
		out = append(out, d)
	}
	return out, rows.Err()
}

func listDeploymentsForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]Deployment, error) {
	rows, err := c.Query(ctx, `SELECT `+deploymentColumns+` FROM deployments WHERE operator_id = $1 ORDER BY created_at DESC`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list deployments for operator: %w", err)
	}
	defer rows.Close()
	out := []Deployment{}
	for rows.Next() {
		d, err := scanDeployment(rows)
		if err != nil {
			return nil, fmt.Errorf("scan deployment: %w", err)
		}
		out = append(out, d)
	}
	return out, rows.Err()
}

// getDeploymentByIDAnyScope looks a deployment up by id alone -- used only
// by machine-authenticated agent-facing paths, which prove identity by
// certificate signature rather than by presenting a tenant session, and
// therefore have no app.tenant_id RLS context to filter through.
func getDeploymentByIDAnyScope(ctx context.Context, c conn, id uuid.UUID) (Deployment, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+deploymentColumns+` FROM deployments WHERE id = $1`, id)
	d, err := scanDeployment(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Deployment{}, false, nil
		}
		return Deployment{}, false, fmt.Errorf("get deployment (any scope): %w", err)
	}
	return d, true, nil
}

func setDeploymentStatus(ctx context.Context, c conn, id uuid.UUID, status string) error {
	_, err := c.Exec(ctx, `UPDATE deployments SET status = $2, updated_at = now() WHERE id = $1`, id, status)
	if err != nil {
		return fmt.Errorf("update deployment status: %w", err)
	}
	return nil
}

func setDeploymentStatusAndReplicaCount(ctx context.Context, c conn, id uuid.UUID, status string, replicaCount int) error {
	_, err := c.Exec(ctx, `UPDATE deployments SET status = $2, replica_count = $3, updated_at = now() WHERE id = $1`, id, status, replicaCount)
	if err != nil {
		return fmt.Errorf("update deployment status and replica count: %w", err)
	}
	return nil
}

// ---------------------------------------------------------------------
// Deployment plans
// ---------------------------------------------------------------------

const deploymentPlanColumns = `id, deployment_id, enterprise_tenant_id, version, status, manifest, manifest_hash,
	signature, requested_by, approved_by, rejected_reason, created_at, updated_at`

func scanDeploymentPlan(row pgx.Row) (DeploymentPlan, error) {
	var p DeploymentPlan
	var manifestRaw []byte
	err := row.Scan(&p.ID, &p.DeploymentID, &p.EnterpriseTenantID, &p.Version, &p.Status, &manifestRaw, &p.ManifestHash,
		&p.Signature, &p.RequestedBy, &p.ApprovedBy, &p.RejectedReason, &p.CreatedAt, &p.UpdatedAt)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if err := json.Unmarshal(manifestRaw, &p.Manifest); err != nil {
		return DeploymentPlan{}, fmt.Errorf("decode manifest: %w", err)
	}
	return p, nil
}

func nextPlanVersion(ctx context.Context, c conn, deploymentID uuid.UUID) (int, error) {
	var maxVersion int
	err := c.QueryRow(ctx, `SELECT COALESCE(MAX(version), 0) FROM deployment_plans WHERE deployment_id = $1`, deploymentID).Scan(&maxVersion)
	if err != nil {
		return 0, fmt.Errorf("resolve next plan version: %w", err)
	}
	return maxVersion + 1, nil
}

func createDeploymentPlan(ctx context.Context, c conn, tenantID, deploymentID uuid.UUID, version int, manifest map[string]any, manifestHash string, requestedBy uuid.UUID) (DeploymentPlan, error) {
	manifestJSON, err := json.Marshal(manifest)
	if err != nil {
		return DeploymentPlan{}, fmt.Errorf("encode manifest: %w", err)
	}
	row := c.QueryRow(ctx, `
		INSERT INTO deployment_plans (deployment_id, enterprise_tenant_id, version, manifest, manifest_hash, requested_by)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING `+deploymentPlanColumns, deploymentID, tenantID, version, manifestJSON, manifestHash, requestedBy)
	p, err := scanDeploymentPlan(row)
	if err != nil {
		return DeploymentPlan{}, fmt.Errorf("insert deployment plan: %w", err)
	}
	return p, nil
}

func getDeploymentPlanByID(ctx context.Context, c conn, tenantID, deploymentID, id uuid.UUID) (DeploymentPlan, bool, error) {
	row := c.QueryRow(ctx, `
		SELECT `+deploymentPlanColumns+` FROM deployment_plans
		WHERE id = $1 AND deployment_id = $2 AND enterprise_tenant_id = $3
	`, id, deploymentID, tenantID)
	p, err := scanDeploymentPlan(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return DeploymentPlan{}, false, nil
		}
		return DeploymentPlan{}, false, fmt.Errorf("get deployment plan: %w", err)
	}
	return p, true, nil
}

func listDeploymentPlans(ctx context.Context, c conn, tenantID, deploymentID uuid.UUID) ([]DeploymentPlan, error) {
	rows, err := c.Query(ctx, `
		SELECT `+deploymentPlanColumns+` FROM deployment_plans
		WHERE deployment_id = $1 AND enterprise_tenant_id = $2 ORDER BY version DESC
	`, deploymentID, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list deployment plans: %w", err)
	}
	defer rows.Close()
	out := []DeploymentPlan{}
	for rows.Next() {
		p, err := scanDeploymentPlan(rows)
		if err != nil {
			return nil, fmt.Errorf("scan deployment plan: %w", err)
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func setPlanStatus(ctx context.Context, c conn, id uuid.UUID, fromStatus, toStatus string) (bool, error) {
	tag, err := c.Exec(ctx, `UPDATE deployment_plans SET status = $3, updated_at = now() WHERE id = $1 AND status = $2`, id, fromStatus, toStatus)
	if err != nil {
		return false, fmt.Errorf("update deployment plan status: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func approveDeploymentPlan(ctx context.Context, c conn, id uuid.UUID, approvedBy uuid.UUID, signature string) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE deployment_plans SET status = 'approved', approved_by = $2, signature = $3, updated_at = now()
		WHERE id = $1 AND status = 'pending_approval'
	`, id, approvedBy, signature)
	if err != nil {
		return false, fmt.Errorf("approve deployment plan: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func rejectDeploymentPlan(ctx context.Context, c conn, id uuid.UUID, reason string) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE deployment_plans SET status = 'rejected', rejected_reason = $2, updated_at = now()
		WHERE id = $1 AND status = 'pending_approval'
	`, id, reason)
	if err != nil {
		return false, fmt.Errorf("reject deployment plan: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func getDeploymentPlanByVersion(ctx context.Context, c conn, tenantID, deploymentID uuid.UUID, version int) (DeploymentPlan, bool, error) {
	row := c.QueryRow(ctx, `
		SELECT `+deploymentPlanColumns+` FROM deployment_plans
		WHERE deployment_id = $1 AND enterprise_tenant_id = $2 AND version = $3
	`, deploymentID, tenantID, version)
	p, err := scanDeploymentPlan(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return DeploymentPlan{}, false, nil
		}
		return DeploymentPlan{}, false, fmt.Errorf("get deployment plan by version: %w", err)
	}
	return p, true, nil
}

// getDeploymentPlanByVersionAnyScope is getDeploymentPlanByVersion without a
// tenant filter -- used only by the machine-authenticated command-result
// path, which authenticates by certificate signature rather than a tenant
// session.
func getDeploymentPlanByVersionAnyScope(ctx context.Context, c conn, deploymentID uuid.UUID, version int) (DeploymentPlan, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+deploymentPlanColumns+` FROM deployment_plans WHERE deployment_id = $1 AND version = $2`, deploymentID, version)
	p, err := scanDeploymentPlan(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return DeploymentPlan{}, false, nil
		}
		return DeploymentPlan{}, false, fmt.Errorf("get deployment plan by version (any scope): %w", err)
	}
	return p, true, nil
}

// latestPlanByStatuses returns the highest-version plan for a deployment
// whose status is one of statuses -- used to find "the currently active
// plan" (for Retry) or "the plan awaiting a result" without the caller
// needing to track extra state between Submit and the agent's eventual
// response.
func latestPlanByStatuses(ctx context.Context, c conn, tenantID, deploymentID uuid.UUID, statuses ...string) (DeploymentPlan, bool, error) {
	row := c.QueryRow(ctx, `
		SELECT `+deploymentPlanColumns+` FROM deployment_plans
		WHERE deployment_id = $1 AND enterprise_tenant_id = $2 AND status = ANY($3)
		ORDER BY version DESC LIMIT 1
	`, deploymentID, tenantID, statuses)
	p, err := scanDeploymentPlan(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return DeploymentPlan{}, false, nil
		}
		return DeploymentPlan{}, false, fmt.Errorf("get latest plan by status: %w", err)
	}
	return p, true, nil
}

// setPlanStatusUnconditional sets a plan's status regardless of its current
// status -- used only when a command result reports success and the plan
// (already known, by construction, to be either 'submitted' after a fresh
// deploy or 'active'/'superseded' after a rollback target lookup) becomes
// the deployment's one active plan.
func setPlanStatusUnconditional(ctx context.Context, c conn, id uuid.UUID, status string) error {
	_, err := c.Exec(ctx, `UPDATE deployment_plans SET status = $2, updated_at = now() WHERE id = $1`, id, status)
	if err != nil {
		return fmt.Errorf("set deployment plan status: %w", err)
	}
	return nil
}

func supersedeActivePlans(ctx context.Context, c conn, deploymentID, exceptPlanID uuid.UUID) error {
	_, err := c.Exec(ctx, `
		UPDATE deployment_plans SET status = 'superseded', updated_at = now()
		WHERE deployment_id = $1 AND status = 'active' AND id <> $2
	`, deploymentID, exceptPlanID)
	if err != nil {
		return fmt.Errorf("supersede active deployment plans: %w", err)
	}
	return nil
}

// ---------------------------------------------------------------------
// Deployment events (append-only)
// ---------------------------------------------------------------------

func insertDeploymentEvent(ctx context.Context, c conn, deploymentID, tenantID, operatorID uuid.UUID, eventType string, detail map[string]any, actorUserID *uuid.UUID) (DeploymentEvent, error) {
	detailJSON, err := json.Marshal(detail)
	if err != nil {
		return DeploymentEvent{}, fmt.Errorf("encode event detail: %w", err)
	}
	var e DeploymentEvent
	var detailRaw []byte
	err = c.QueryRow(ctx, `
		INSERT INTO deployment_events (deployment_id, enterprise_tenant_id, operator_id, event_type, detail, actor_user_id)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, deployment_id, enterprise_tenant_id, operator_id, event_type, detail, actor_user_id, created_at
	`, deploymentID, tenantID, operatorID, eventType, detailJSON, actorUserID).Scan(
		&e.ID, &e.DeploymentID, &e.EnterpriseTenantID, &e.OperatorID, &e.EventType, &detailRaw, &e.ActorUserID, &e.CreatedAt)
	if err != nil {
		return DeploymentEvent{}, fmt.Errorf("insert deployment event: %w", err)
	}
	if err := json.Unmarshal(detailRaw, &e.Detail); err != nil {
		return DeploymentEvent{}, fmt.Errorf("decode event detail: %w", err)
	}
	return e, nil
}

func listDeploymentEventsForTenant(ctx context.Context, c conn, tenantID, deploymentID uuid.UUID) ([]DeploymentEvent, error) {
	rows, err := c.Query(ctx, `
		SELECT id, deployment_id, enterprise_tenant_id, operator_id, event_type, detail, actor_user_id, created_at
		FROM deployment_events WHERE enterprise_tenant_id = $1 AND deployment_id = $2 ORDER BY created_at
	`, tenantID, deploymentID)
	return scanDeploymentEvents(rows, err)
}

func listDeploymentEventsForOperator(ctx context.Context, c conn, operatorID, deploymentID uuid.UUID) ([]DeploymentEvent, error) {
	rows, err := c.Query(ctx, `
		SELECT id, deployment_id, enterprise_tenant_id, operator_id, event_type, detail, actor_user_id, created_at
		FROM deployment_events WHERE operator_id = $1 AND deployment_id = $2 ORDER BY created_at
	`, operatorID, deploymentID)
	return scanDeploymentEvents(rows, err)
}

func scanDeploymentEvents(rows pgx.Rows, err error) ([]DeploymentEvent, error) {
	if err != nil {
		return nil, fmt.Errorf("list deployment events: %w", err)
	}
	defer rows.Close()
	out := []DeploymentEvent{}
	for rows.Next() {
		var e DeploymentEvent
		var detailRaw []byte
		if err := rows.Scan(&e.ID, &e.DeploymentID, &e.EnterpriseTenantID, &e.OperatorID, &e.EventType, &detailRaw, &e.ActorUserID, &e.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan deployment event: %w", err)
		}
		if err := json.Unmarshal(detailRaw, &e.Detail); err != nil {
			return nil, fmt.Errorf("decode event detail: %w", err)
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Workload secrets (values encrypted at rest -- see internal/platform/secretsvault)
// ---------------------------------------------------------------------

func createWorkloadSecret(ctx context.Context, c conn, tenantID, workloadVersionID uuid.UUID, key, encryptedValue string, createdBy uuid.UUID) (WorkloadSecret, error) {
	var s WorkloadSecret
	err := c.QueryRow(ctx, `
		INSERT INTO workload_secrets (enterprise_tenant_id, workload_version_id, key, encrypted_value, created_by)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, enterprise_tenant_id, workload_version_id, key, created_by, created_at, updated_at
	`, tenantID, workloadVersionID, key, encryptedValue, createdBy).Scan(
		&s.ID, &s.EnterpriseTenantID, &s.WorkloadVersionID, &s.Key, &s.CreatedBy, &s.CreatedAt, &s.UpdatedAt)
	if err != nil {
		return WorkloadSecret{}, fmt.Errorf("insert workload secret: %w", err)
	}
	return s, nil
}

func listWorkloadSecrets(ctx context.Context, c conn, tenantID, workloadVersionID uuid.UUID) ([]WorkloadSecret, error) {
	rows, err := c.Query(ctx, `
		SELECT id, enterprise_tenant_id, workload_version_id, key, created_by, created_at, updated_at
		FROM workload_secrets WHERE enterprise_tenant_id = $1 AND workload_version_id = $2 ORDER BY key
	`, tenantID, workloadVersionID)
	if err != nil {
		return nil, fmt.Errorf("list workload secrets: %w", err)
	}
	defer rows.Close()
	out := []WorkloadSecret{}
	for rows.Next() {
		var s WorkloadSecret
		if err := rows.Scan(&s.ID, &s.EnterpriseTenantID, &s.WorkloadVersionID, &s.Key, &s.CreatedBy, &s.CreatedAt, &s.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan workload secret: %w", err)
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

func deleteWorkloadSecret(ctx context.Context, c conn, tenantID, workloadVersionID, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		DELETE FROM workload_secrets WHERE id = $1 AND enterprise_tenant_id = $2 AND workload_version_id = $3
	`, id, tenantID, workloadVersionID)
	if err != nil {
		return false, fmt.Errorf("delete workload secret: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

// listWorkloadSecretsWithValues is used only by AgentFetchSecrets -- the one
// path in this codebase authorized to decrypt secret values, after
// independently verifying the calling cluster agent is the one actually
// assigned to the deployment referencing this workload version.
func listWorkloadSecretsWithValues(ctx context.Context, c conn, workloadVersionID uuid.UUID) ([]struct {
	Key            string
	EncryptedValue string
}, error) {
	rows, err := c.Query(ctx, `SELECT key, encrypted_value FROM workload_secrets WHERE workload_version_id = $1 ORDER BY key`, workloadVersionID)
	if err != nil {
		return nil, fmt.Errorf("list workload secrets with values: %w", err)
	}
	defer rows.Close()
	var out []struct {
		Key            string
		EncryptedValue string
	}
	for rows.Next() {
		var row struct {
			Key            string
			EncryptedValue string
		}
		if err := rows.Scan(&row.Key, &row.EncryptedValue); err != nil {
			return nil, fmt.Errorf("scan workload secret value: %w", err)
		}
		out = append(out, row)
	}
	return out, rows.Err()
}

func workloadSecretKeys(ctx context.Context, c conn, workloadVersionID uuid.UUID) ([]string, error) {
	rows, err := c.Query(ctx, `SELECT key FROM workload_secrets WHERE workload_version_id = $1 ORDER BY key`, workloadVersionID)
	if err != nil {
		return nil, fmt.Errorf("list workload secret keys: %w", err)
	}
	defer rows.Close()
	out := []string{}
	for rows.Next() {
		var key string
		if err := rows.Scan(&key); err != nil {
			return nil, fmt.Errorf("scan workload secret key: %w", err)
		}
		out = append(out, key)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Cross-module reads: capacity reservations, placement requests, capacity
// offers, cluster agents, workload versions/components/health checks,
// container images. Each of these tables is owned by another module; this
// package only ever reads them directly by SQL, the same "each module owns
// its own SQL against shared tables" convention internal/modules/placement
// already established for policy_evaluation_records and capacity_offers.
// ---------------------------------------------------------------------

// withPlatformBypass runs fn with app.platform_bypass set for the remainder
// of the current statement only -- used exactly like
// internal/modules/placement's helper of the same name: CreateDeployment
// runs inside a tenant-scoped transaction (only app.tenant_id is set), but
// resolving which cluster agent to assign requires reading cluster_agents,
// which is operator-scoped RLS (cluster_agents_operator_scope /
// cluster_agents_platform_bypass only -- no tenant-facing policy exists,
// since an operator's machine identity is not tenant data). The statements
// this wraps are fixed, read-only, and parameterized only by ids already
// resolved from the tenant's own reservation row, so the elevation is
// narrow and auditable, not a general escape hatch.
func withPlatformBypass(ctx context.Context, c conn, fn func() error) error {
	if _, err := c.Exec(ctx, `SET LOCAL app.platform_bypass = 'true'`); err != nil {
		return fmt.Errorf("enable platform bypass: %w", err)
	}
	fnErr := fn()
	if _, err := c.Exec(ctx, `SET LOCAL app.platform_bypass = 'false'`); err != nil {
		if fnErr != nil {
			return fnErr
		}
		return fmt.Errorf("disable platform bypass: %w", err)
	}
	return fnErr
}

type reservationFacts struct {
	OperatorID        uuid.UUID
	CapacityOfferID   uuid.UUID
	Status            string
	WorkloadVersionID uuid.UUID
}

func getReservationFacts(ctx context.Context, c conn, tenantID, reservationID uuid.UUID) (reservationFacts, bool, error) {
	var f reservationFacts
	err := c.QueryRow(ctx, `
		SELECT cr.operator_id, cr.capacity_offer_id, cr.status, pr.workload_version_id
		FROM capacity_reservations cr
		JOIN placement_requests pr ON pr.id = cr.placement_request_id
		WHERE cr.id = $1 AND cr.enterprise_tenant_id = $2
	`, reservationID, tenantID).Scan(&f.OperatorID, &f.CapacityOfferID, &f.Status, &f.WorkloadVersionID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return reservationFacts{}, false, nil
		}
		return reservationFacts{}, false, fmt.Errorf("look up capacity reservation: %w", err)
	}
	return f, true, nil
}

func reservationAlreadyDeployed(ctx context.Context, c conn, reservationID uuid.UUID) (bool, error) {
	var exists bool
	err := c.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM deployments WHERE capacity_reservation_id = $1)`, reservationID).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("check existing deployment for reservation: %w", err)
	}
	return exists, nil
}

func capacityOfferClusterID(ctx context.Context, c conn, offerID uuid.UUID) (uuid.UUID, error) {
	var clusterID uuid.UUID
	err := c.QueryRow(ctx, `SELECT cluster_id FROM capacity_offers WHERE id = $1`, offerID).Scan(&clusterID)
	if err != nil {
		return uuid.Nil, fmt.Errorf("look up capacity offer cluster: %w", err)
	}
	return clusterID, nil
}

// activeClusterAgentForCluster mirrors internal/modules/agents' unexported
// helper of the same name -- duplicated here rather than shared, following
// this codebase's established convention of small per-consumer primitives
// (see internal/platform/secretsvault's package doc for the same choice
// made about AES-256-GCM helpers).
func activeClusterAgentForCluster(ctx context.Context, c conn, clusterID uuid.UUID) (uuid.UUID, bool, error) {
	var agentID uuid.UUID
	err := c.QueryRow(ctx, `
		SELECT id FROM cluster_agents WHERE cluster_id = $1 AND status = 'active' ORDER BY created_at DESC LIMIT 1
	`, clusterID).Scan(&agentID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, false, nil
		}
		return uuid.Nil, false, fmt.Errorf("resolve active cluster agent: %w", err)
	}
	return agentID, true, nil
}

type workloadVersionFacts struct {
	ResourceRequirements map[string]any
	NetworkRequirements  map[string]any
	SecurityRequirements map[string]any
	Status               string
}

func getWorkloadVersionFacts(ctx context.Context, c conn, tenantID, versionID uuid.UUID) (workloadVersionFacts, bool, error) {
	var f workloadVersionFacts
	var resourceRaw, networkRaw, securityRaw []byte
	err := c.QueryRow(ctx, `
		SELECT resource_requirements, network_requirements, security_requirements, status
		FROM workload_versions WHERE id = $1 AND enterprise_tenant_id = $2
	`, versionID, tenantID).Scan(&resourceRaw, &networkRaw, &securityRaw, &f.Status)
	if err != nil {
		if err == pgx.ErrNoRows {
			return workloadVersionFacts{}, false, nil
		}
		return workloadVersionFacts{}, false, fmt.Errorf("look up workload version: %w", err)
	}
	if err := json.Unmarshal(resourceRaw, &f.ResourceRequirements); err != nil {
		return workloadVersionFacts{}, false, fmt.Errorf("decode resource requirements: %w", err)
	}
	if err := json.Unmarshal(networkRaw, &f.NetworkRequirements); err != nil {
		return workloadVersionFacts{}, false, fmt.Errorf("decode network requirements: %w", err)
	}
	if err := json.Unmarshal(securityRaw, &f.SecurityRequirements); err != nil {
		return workloadVersionFacts{}, false, fmt.Errorf("decode security requirements: %w", err)
	}
	return f, true, nil
}

type componentFacts struct {
	ComponentKey string
	Name         string
	Image        string
	Command      []string
	Args         []string
	Env          map[string]any
	IsPrimary    bool
	HealthChecks []healthCheckFacts
}

type healthCheckFacts struct {
	CheckType        string
	Path             string
	Port             *int
	Command          []string
	IntervalSeconds  int
	TimeoutSeconds   int
	FailureThreshold int
}

// listComponentsWithImagesAndHealthChecks assembles everything a manifest
// needs about a workload version's components in one place: the
// digest-pinned image reference (never a mutable tag -- see images.ContainerImage),
// command/args/non-secret env, and each component's health checks.
func listComponentsWithImagesAndHealthChecks(ctx context.Context, c conn, tenantID, versionID uuid.UUID) ([]componentFacts, error) {
	rows, err := c.Query(ctx, `
		SELECT wc.id, wc.component_key, wc.name, ci.registry_host, ci.repository, ci.digest, wc.command, wc.args, wc.env, wc.is_primary
		FROM workload_components wc
		JOIN container_images ci ON ci.id = wc.container_image_id
		WHERE wc.enterprise_tenant_id = $1 AND wc.workload_version_id = $2
		ORDER BY wc.component_key
	`, tenantID, versionID)
	if err != nil {
		return nil, fmt.Errorf("list workload components: %w", err)
	}
	defer rows.Close()

	var out []componentFacts
	var componentIDs []uuid.UUID
	for rows.Next() {
		var id uuid.UUID
		var f componentFacts
		var registryHost, repository, digest string
		var commandRaw, argsRaw, envRaw []byte
		if err := rows.Scan(&id, &f.ComponentKey, &f.Name, &registryHost, &repository, &digest, &commandRaw, &argsRaw, &envRaw, &f.IsPrimary); err != nil {
			return nil, fmt.Errorf("scan workload component: %w", err)
		}
		if err := json.Unmarshal(commandRaw, &f.Command); err != nil {
			return nil, fmt.Errorf("decode command: %w", err)
		}
		if err := json.Unmarshal(argsRaw, &f.Args); err != nil {
			return nil, fmt.Errorf("decode args: %w", err)
		}
		if err := json.Unmarshal(envRaw, &f.Env); err != nil {
			return nil, fmt.Errorf("decode env: %w", err)
		}
		f.Image = fmt.Sprintf("%s/%s@%s", registryHost, repository, digest)
		out = append(out, f)
		componentIDs = append(componentIDs, id)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	for i, componentID := range componentIDs {
		checks, err := listHealthCheckFacts(ctx, c, tenantID, componentID)
		if err != nil {
			return nil, err
		}
		out[i].HealthChecks = checks
	}
	return out, nil
}

func listHealthCheckFacts(ctx context.Context, c conn, tenantID, componentID uuid.UUID) ([]healthCheckFacts, error) {
	rows, err := c.Query(ctx, `
		SELECT check_type, path, port, command, interval_seconds, timeout_seconds, failure_threshold
		FROM workload_health_checks WHERE enterprise_tenant_id = $1 AND workload_component_id = $2 ORDER BY created_at
	`, tenantID, componentID)
	if err != nil {
		return nil, fmt.Errorf("list health checks: %w", err)
	}
	defer rows.Close()
	var out []healthCheckFacts
	for rows.Next() {
		var f healthCheckFacts
		var commandRaw []byte
		if err := rows.Scan(&f.CheckType, &f.Path, &f.Port, &commandRaw, &f.IntervalSeconds, &f.TimeoutSeconds, &f.FailureThreshold); err != nil {
			return nil, fmt.Errorf("scan health check: %w", err)
		}
		if err := json.Unmarshal(commandRaw, &f.Command); err != nil {
			return nil, fmt.Errorf("decode health check command: %w", err)
		}
		out = append(out, f)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Cluster agent identity (machine-authenticated paths only -- mirrors
// internal/modules/agents' unexported helpers of similar names; duplicated
// rather than shared, per this package's doc comment on
// activeClusterAgentForCluster above.)
// ---------------------------------------------------------------------

// clusterAgentIdentity resolves the owning operator and current valid
// certificate PEM for a cluster agent, for verifying a machine-authenticated
// request's signature before trusting anything else about it.
func clusterAgentIdentity(ctx context.Context, c conn, agentID uuid.UUID) (operatorID uuid.UUID, certPEM string, ok bool, err error) {
	err = c.QueryRow(ctx, `SELECT operator_id FROM cluster_agents WHERE id = $1 AND status = 'active'`, agentID).Scan(&operatorID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, "", false, nil
		}
		return uuid.Nil, "", false, fmt.Errorf("resolve cluster agent operator: %w", err)
	}
	err = c.QueryRow(ctx, `
		SELECT certificate_pem FROM cluster_agent_certificates
		WHERE cluster_agent_id = $1 AND revoked_at IS NULL AND expires_at > now()
		ORDER BY issued_at DESC LIMIT 1
	`, agentID).Scan(&certPEM)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, "", false, nil
		}
		return uuid.Nil, "", false, fmt.Errorf("load current cluster agent certificate: %w", err)
	}
	return operatorID, certPEM, true, nil
}

// ---------------------------------------------------------------------
// Control messages (write-only from this package's perspective -- polling
// for pending to_agent messages and verifying/recording deployment-plan-
// validation responses remain internal/modules/agents' job; this package
// only sends deployment_command messages and records
// deployment_command_result responses, both new generic message types
// migration 0027 added).
// ---------------------------------------------------------------------

func createControlMessage(ctx context.Context, c conn, operatorID, agentID uuid.UUID, direction, messageType string, inResponseTo *uuid.UUID, nonce string, payload []byte, signature string, signedAt time.Time, status string) (uuid.UUID, error) {
	var id uuid.UUID
	err := c.QueryRow(ctx, `
		INSERT INTO control_messages (operator_id, cluster_agent_id, direction, message_type, in_response_to, nonce, payload, signature, signed_at, status)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		RETURNING id
	`, operatorID, agentID, direction, messageType, inResponseTo, nonce, string(payload), signature, signedAt, status).Scan(&id)
	if err != nil {
		return uuid.Nil, fmt.Errorf("insert control message: %w", err)
	}
	return id, nil
}

func controlMessageNonceExists(ctx context.Context, c conn, agentID uuid.UUID, nonce string) (bool, error) {
	var exists bool
	err := c.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM control_messages WHERE cluster_agent_id = $1 AND nonce = $2)`, agentID, nonce).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("check control message nonce: %w", err)
	}
	return exists, nil
}

func getPendingCommandMessage(ctx context.Context, c conn, agentID, messageID uuid.UUID) (deploymentCommandPayload, bool, error) {
	var payloadRaw string
	err := c.QueryRow(ctx, `
		SELECT payload FROM control_messages
		WHERE id = $1 AND cluster_agent_id = $2 AND direction = 'to_agent' AND message_type = 'deployment_command' AND status = 'pending'
	`, messageID, agentID).Scan(&payloadRaw)
	if err != nil {
		if err == pgx.ErrNoRows {
			return deploymentCommandPayload{}, false, nil
		}
		return deploymentCommandPayload{}, false, fmt.Errorf("look up pending deployment command message: %w", err)
	}
	var payload deploymentCommandPayload
	if err := json.Unmarshal([]byte(payloadRaw), &payload); err != nil {
		return deploymentCommandPayload{}, false, fmt.Errorf("decode deployment command payload: %w", err)
	}
	return payload, true, nil
}

func markControlMessageResponded(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `UPDATE control_messages SET status = 'responded' WHERE id = $1 AND status = 'pending'`, id)
	if err != nil {
		return false, fmt.Errorf("mark control message responded: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}
