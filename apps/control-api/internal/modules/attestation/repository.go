package attestation

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
// Attestation policies
// ---------------------------------------------------------------------

const attestationPolicyColumns = `id, operator_id, cluster_id, provider_type, expected_measurements,
	status, created_by, revoked_by, revoked_at, revoked_reason, created_at, updated_at`

func scanAttestationPolicy(row pgx.Row) (AttestationPolicy, error) {
	var p AttestationPolicy
	var measurementsRaw []byte
	err := row.Scan(&p.ID, &p.OperatorID, &p.ClusterID, &p.ProviderType, &measurementsRaw,
		&p.Status, &p.CreatedBy, &p.RevokedBy, &p.RevokedAt, &p.RevokedReason, &p.CreatedAt, &p.UpdatedAt)
	if err != nil {
		return AttestationPolicy{}, err
	}
	if err := json.Unmarshal(measurementsRaw, &p.ExpectedMeasurements); err != nil {
		return AttestationPolicy{}, fmt.Errorf("decode expected measurements: %w", err)
	}
	return p, nil
}

func currentActivePolicyForCluster(ctx context.Context, c conn, clusterID uuid.UUID) (AttestationPolicy, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+attestationPolicyColumns+` FROM attestation_policies WHERE cluster_id = $1 AND status = 'active'`, clusterID)
	p, err := scanAttestationPolicy(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return AttestationPolicy{}, false, nil
		}
		return AttestationPolicy{}, false, fmt.Errorf("look up active attestation policy: %w", err)
	}
	return p, true, nil
}

func supersedeActivePolicyForCluster(ctx context.Context, c conn, clusterID uuid.UUID, revokedBy uuid.UUID) error {
	_, err := c.Exec(ctx, `
		UPDATE attestation_policies
		SET status = 'revoked', revoked_by = $2, revoked_at = now(), revoked_reason = 'superseded by a new policy version', updated_at = now()
		WHERE cluster_id = $1 AND status = 'active'
	`, clusterID, revokedBy)
	if err != nil {
		return fmt.Errorf("supersede active attestation policy: %w", err)
	}
	return nil
}

func createAttestationPolicy(ctx context.Context, c conn, operatorID, clusterID uuid.UUID, providerType string, expectedMeasurements map[string]any, createdBy uuid.UUID) (AttestationPolicy, error) {
	measurementsJSON, err := json.Marshal(expectedMeasurements)
	if err != nil {
		return AttestationPolicy{}, fmt.Errorf("encode expected measurements: %w", err)
	}
	row := c.QueryRow(ctx, `
		INSERT INTO attestation_policies (operator_id, cluster_id, provider_type, expected_measurements, created_by)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING `+attestationPolicyColumns, operatorID, clusterID, providerType, measurementsJSON, createdBy)
	p, err := scanAttestationPolicy(row)
	if err != nil {
		return AttestationPolicy{}, fmt.Errorf("insert attestation policy: %w", err)
	}
	return p, nil
}

func getAttestationPolicyByID(ctx context.Context, c conn, operatorID, id uuid.UUID) (AttestationPolicy, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+attestationPolicyColumns+` FROM attestation_policies WHERE id = $1 AND operator_id = $2`, id, operatorID)
	p, err := scanAttestationPolicy(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return AttestationPolicy{}, false, nil
		}
		return AttestationPolicy{}, false, fmt.Errorf("get attestation policy: %w", err)
	}
	return p, true, nil
}

func listAttestationPolicies(ctx context.Context, c conn, operatorID uuid.UUID) ([]AttestationPolicy, error) {
	rows, err := c.Query(ctx, `SELECT `+attestationPolicyColumns+` FROM attestation_policies WHERE operator_id = $1 ORDER BY created_at DESC`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list attestation policies: %w", err)
	}
	defer rows.Close()
	out := []AttestationPolicy{}
	for rows.Next() {
		p, err := scanAttestationPolicy(rows)
		if err != nil {
			return nil, fmt.Errorf("scan attestation policy: %w", err)
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func revokeAttestationPolicy(ctx context.Context, c conn, id uuid.UUID, revokedBy uuid.UUID, reason string) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE attestation_policies SET status = 'revoked', revoked_by = $2, revoked_at = now(), revoked_reason = $3, updated_at = now()
		WHERE id = $1 AND status = 'active'
	`, id, revokedBy, reason)
	if err != nil {
		return false, fmt.Errorf("revoke attestation policy: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

// ---------------------------------------------------------------------
// Attestation sessions
// ---------------------------------------------------------------------

func createAttestationSession(ctx context.Context, c conn, operatorID, agentID uuid.UUID, nonce string, expiresAt time.Time) (AttestationSession, error) {
	var s AttestationSession
	err := c.QueryRow(ctx, `
		INSERT INTO attestation_sessions (operator_id, cluster_agent_id, nonce, expires_at)
		VALUES ($1, $2, $3, $4)
		RETURNING id, operator_id, cluster_agent_id, nonce, status, issued_at, expires_at
	`, operatorID, agentID, nonce, expiresAt).Scan(&s.ID, &s.OperatorID, &s.ClusterAgentID, &s.Nonce, &s.Status, &s.IssuedAt, &s.ExpiresAt)
	if err != nil {
		return AttestationSession{}, fmt.Errorf("insert attestation session: %w", err)
	}
	return s, nil
}

// consumeAttestationSession atomically transitions a pending, unexpired
// session belonging to agentID to 'consumed' -- the actual replay-protection
// mechanism: a session can never be consumed twice, and one already past
// its expires_at is rejected by the WHERE clause regardless of status.
func consumeAttestationSession(ctx context.Context, c conn, sessionID, agentID uuid.UUID) (AttestationSession, bool, error) {
	var s AttestationSession
	err := c.QueryRow(ctx, `
		UPDATE attestation_sessions
		SET status = 'consumed'
		WHERE id = $1 AND cluster_agent_id = $2 AND status = 'pending' AND expires_at > now()
		RETURNING id, operator_id, cluster_agent_id, nonce, status, issued_at, expires_at
	`, sessionID, agentID).Scan(&s.ID, &s.OperatorID, &s.ClusterAgentID, &s.Nonce, &s.Status, &s.IssuedAt, &s.ExpiresAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return AttestationSession{}, false, nil
		}
		return AttestationSession{}, false, fmt.Errorf("consume attestation session: %w", err)
	}
	return s, true, nil
}

// ---------------------------------------------------------------------
// Attestation results (append-only)
// ---------------------------------------------------------------------

const attestationResultColumns = `id, operator_id, enterprise_tenant_id, cluster_agent_id, attestation_session_id,
	attestation_policy_id, deployment_id, provider_type, measurements, raw_evidence, decision, reason_codes,
	evaluated_at, created_at`

func scanAttestationResult(row pgx.Row) (AttestationResult, error) {
	var r AttestationResult
	var measurementsRaw, reasonCodesRaw []byte
	err := row.Scan(&r.ID, &r.OperatorID, &r.EnterpriseTenantID, &r.ClusterAgentID, &r.AttestationSessionID,
		&r.AttestationPolicyID, &r.DeploymentID, &r.ProviderType, &measurementsRaw, &r.RawEvidence, &r.Decision,
		&reasonCodesRaw, &r.EvaluatedAt, &r.CreatedAt)
	if err != nil {
		return AttestationResult{}, err
	}
	if err := json.Unmarshal(measurementsRaw, &r.Measurements); err != nil {
		return AttestationResult{}, fmt.Errorf("decode measurements: %w", err)
	}
	if err := json.Unmarshal(reasonCodesRaw, &r.ReasonCodes); err != nil {
		return AttestationResult{}, fmt.Errorf("decode reason codes: %w", err)
	}
	return r, nil
}

func createAttestationResult(ctx context.Context, c conn, operatorID, tenantID, agentID, sessionID uuid.UUID, policyID *uuid.UUID, deploymentID uuid.UUID, providerType string, measurements map[string]any, rawEvidence, decision string, reasonCodes []string, nonce, signature string, evaluatedAt time.Time) (AttestationResult, error) {
	measurementsJSON, err := json.Marshal(measurements)
	if err != nil {
		return AttestationResult{}, fmt.Errorf("encode measurements: %w", err)
	}
	reasonCodesJSON, err := json.Marshal(reasonCodes)
	if err != nil {
		return AttestationResult{}, fmt.Errorf("encode reason codes: %w", err)
	}
	row := c.QueryRow(ctx, `
		INSERT INTO attestation_results (
			operator_id, enterprise_tenant_id, cluster_agent_id, attestation_session_id, attestation_policy_id,
			deployment_id, provider_type, measurements, raw_evidence, decision, reason_codes, nonce, signature, evaluated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
		RETURNING `+attestationResultColumns,
		operatorID, tenantID, agentID, sessionID, policyID, deploymentID, providerType, measurementsJSON,
		rawEvidence, decision, reasonCodesJSON, nonce, signature, evaluatedAt)
	r, err := scanAttestationResult(row)
	if err != nil {
		return AttestationResult{}, fmt.Errorf("insert attestation result: %w", err)
	}
	return r, nil
}

func listAttestationResultsForOperatorAgent(ctx context.Context, c conn, operatorID, agentID uuid.UUID) ([]AttestationResult, error) {
	rows, err := c.Query(ctx, `
		SELECT `+attestationResultColumns+` FROM attestation_results
		WHERE operator_id = $1 AND cluster_agent_id = $2 ORDER BY evaluated_at DESC
	`, operatorID, agentID)
	if err != nil {
		return nil, fmt.Errorf("list attestation results: %w", err)
	}
	defer rows.Close()
	out := []AttestationResult{}
	for rows.Next() {
		r, err := scanAttestationResult(rows)
		if err != nil {
			return nil, fmt.Errorf("scan attestation result: %w", err)
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// listAttestationResultsForTenant is the tenant-facing "customer
// verification view" query -- it deliberately never selects
// measurements/raw_evidence at all, so there is no code path in this
// function that could leak either back to a tenant session.
func listAttestationResultsForTenant(ctx context.Context, c conn, tenantID, deploymentID uuid.UUID) ([]RedactedAttestationResult, error) {
	rows, err := c.Query(ctx, `
		SELECT id, deployment_id, provider_type, decision, reason_codes, evaluated_at
		FROM attestation_results WHERE enterprise_tenant_id = $1 AND deployment_id = $2 ORDER BY evaluated_at DESC
	`, tenantID, deploymentID)
	if err != nil {
		return nil, fmt.Errorf("list attestation results for tenant: %w", err)
	}
	defer rows.Close()
	out := []RedactedAttestationResult{}
	for rows.Next() {
		var r RedactedAttestationResult
		var reasonCodesRaw []byte
		if err := rows.Scan(&r.ID, &r.DeploymentID, &r.ProviderType, &r.Decision, &reasonCodesRaw, &r.EvaluatedAt); err != nil {
			return nil, fmt.Errorf("scan redacted attestation result: %w", err)
		}
		if err := json.Unmarshal(reasonCodesRaw, &r.ReasonCodes); err != nil {
			return nil, fmt.Errorf("decode reason codes: %w", err)
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Cross-module reads: cluster agents, deployments. Each of these tables is
// owned by another module; this package only ever reads them directly by
// SQL, the same "each module owns its own SQL against shared tables"
// convention internal/modules/placement and internal/modules/deployments
// already established.
// ---------------------------------------------------------------------

// clusterAgentIdentity resolves a cluster agent's owning operator, cluster,
// and current valid certificate PEM -- for verifying a machine-authenticated
// request's signature before trusting anything else about it. Duplicated
// from the same-named helpers in internal/modules/agents and
// internal/modules/deployments rather than shared, per this codebase's
// established convention of small per-consumer primitives.
func clusterAgentIdentity(ctx context.Context, c conn, agentID uuid.UUID) (operatorID, clusterID uuid.UUID, certPEM string, ok bool, err error) {
	err = c.QueryRow(ctx, `SELECT operator_id, cluster_id FROM cluster_agents WHERE id = $1 AND status = 'active'`, agentID).Scan(&operatorID, &clusterID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, uuid.Nil, "", false, nil
		}
		return uuid.Nil, uuid.Nil, "", false, fmt.Errorf("resolve cluster agent: %w", err)
	}
	err = c.QueryRow(ctx, `
		SELECT certificate_pem FROM cluster_agent_certificates
		WHERE cluster_agent_id = $1 AND revoked_at IS NULL AND expires_at > now()
		ORDER BY issued_at DESC LIMIT 1
	`, agentID).Scan(&certPEM)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, uuid.Nil, "", false, nil
		}
		return uuid.Nil, uuid.Nil, "", false, fmt.Errorf("load current cluster agent certificate: %w", err)
	}
	return operatorID, clusterID, certPEM, true, nil
}

type deploymentFacts struct {
	EnterpriseTenantID uuid.UUID
	ClusterAgentID     uuid.UUID
}

func getDeploymentFacts(ctx context.Context, c conn, deploymentID uuid.UUID) (deploymentFacts, bool, error) {
	var f deploymentFacts
	err := c.QueryRow(ctx, `SELECT enterprise_tenant_id, cluster_agent_id FROM deployments WHERE id = $1`, deploymentID).Scan(&f.EnterpriseTenantID, &f.ClusterAgentID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return deploymentFacts{}, false, nil
		}
		return deploymentFacts{}, false, fmt.Errorf("look up deployment: %w", err)
	}
	return f, true, nil
}
