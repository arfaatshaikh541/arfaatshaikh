package policies

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"

	"gridkeep/control-api/internal/platform/policyengine"
)

type conn interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

func scanPolicy(row pgx.Row) (SovereigntyPolicy, error) {
	var p SovereigntyPolicy
	var rawDocument []byte
	err := row.Scan(
		&p.ID, &p.TenantID, &p.PolicyKey, &p.Version, &p.Status, &p.Name, &rawDocument,
		&p.RequestedBy, &p.RequestedPublishAt, &p.ApprovedBy, &p.PublishedAt, &p.SupersededAt,
		&p.RolledBackFromVersion, &p.CreatedAt, &p.UpdatedAt,
	)
	if err != nil {
		return SovereigntyPolicy{}, err
	}
	if err := json.Unmarshal(rawDocument, &p.Document); err != nil {
		return SovereigntyPolicy{}, fmt.Errorf("unmarshal policy document: %w", err)
	}
	return p, nil
}

const policyColumns = `
	id, enterprise_tenant_id, policy_key, version, status, name, document,
	requested_by, requested_publish_at, approved_by, published_at, superseded_at,
	rolled_back_from_version, created_at, updated_at
`

func createDraft(ctx context.Context, c conn, tenantID uuid.UUID, policyKey, name string, document policyengine.PolicyDocument, requestedBy uuid.UUID, rolledBackFromVersion *int) (SovereigntyPolicy, error) {
	documentJSON, err := json.Marshal(document)
	if err != nil {
		return SovereigntyPolicy{}, fmt.Errorf("marshal policy document: %w", err)
	}
	row := c.QueryRow(ctx, `
		INSERT INTO sovereignty_policies (enterprise_tenant_id, policy_key, version, name, document, requested_by, rolled_back_from_version)
		VALUES (
			$1, $2,
			COALESCE((SELECT max(version) FROM sovereignty_policies WHERE enterprise_tenant_id = $1 AND policy_key = $2), 0) + 1,
			$3, $4, $5, $6
		)
		RETURNING `+policyColumns,
		tenantID, policyKey, name, documentJSON, requestedBy, rolledBackFromVersion,
	)
	p, err := scanPolicy(row)
	if err != nil {
		return SovereigntyPolicy{}, fmt.Errorf("insert policy draft: %w", err)
	}
	return p, nil
}

func getDraftByKey(ctx context.Context, c conn, tenantID uuid.UUID, policyKey string) (SovereigntyPolicy, bool, error) {
	row := c.QueryRow(ctx, `
		SELECT `+policyColumns+`
		FROM sovereignty_policies WHERE enterprise_tenant_id = $1 AND policy_key = $2 AND status = 'draft'
	`, tenantID, policyKey)
	p, err := scanPolicy(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return SovereigntyPolicy{}, false, nil
		}
		return SovereigntyPolicy{}, false, fmt.Errorf("get draft: %w", err)
	}
	return p, true, nil
}

func getPolicyByID(ctx context.Context, c conn, tenantID, id uuid.UUID) (SovereigntyPolicy, bool, error) {
	row := c.QueryRow(ctx, `
		SELECT `+policyColumns+`
		FROM sovereignty_policies WHERE id = $1 AND enterprise_tenant_id = $2
	`, id, tenantID)
	p, err := scanPolicy(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return SovereigntyPolicy{}, false, nil
		}
		return SovereigntyPolicy{}, false, fmt.Errorf("get policy: %w", err)
	}
	return p, true, nil
}

func updateDraftDocument(ctx context.Context, c conn, id uuid.UUID, name string, document policyengine.PolicyDocument) (bool, error) {
	documentJSON, err := json.Marshal(document)
	if err != nil {
		return false, fmt.Errorf("marshal policy document: %w", err)
	}
	tag, err := c.Exec(ctx, `
		UPDATE sovereignty_policies SET name = $2, document = $3, updated_at = now()
		WHERE id = $1 AND status = 'draft'
	`, id, name, documentJSON)
	if err != nil {
		return false, fmt.Errorf("update draft: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func markRequestedPublish(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE sovereignty_policies SET status = 'pending_publish', requested_publish_at = now(), updated_at = now()
		WHERE id = $1 AND status = 'draft'
	`, id)
	if err != nil {
		return false, fmt.Errorf("request publish: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func supersedeCurrentPublished(ctx context.Context, c conn, tenantID uuid.UUID, policyKey string) error {
	_, err := c.Exec(ctx, `
		UPDATE sovereignty_policies SET status = 'superseded', superseded_at = now(), updated_at = now()
		WHERE enterprise_tenant_id = $1 AND policy_key = $2 AND status = 'published'
	`, tenantID, policyKey)
	if err != nil {
		return fmt.Errorf("supersede current published policy: %w", err)
	}
	return nil
}

func markApprovedAndPublished(ctx context.Context, c conn, id, approvedBy uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE sovereignty_policies SET status = 'published', approved_by = $2, published_at = now(), updated_at = now()
		WHERE id = $1 AND status = 'pending_publish'
	`, id, approvedBy)
	if err != nil {
		return false, fmt.Errorf("approve and publish: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func listLatestVersionPerKey(ctx context.Context, c conn, tenantID uuid.UUID) ([]SovereigntyPolicy, error) {
	rows, err := c.Query(ctx, `
		SELECT DISTINCT ON (policy_key) `+policyColumns+`
		FROM sovereignty_policies WHERE enterprise_tenant_id = $1
		ORDER BY policy_key, version DESC
	`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list policies: %w", err)
	}
	defer rows.Close()
	return scanPolicies(rows)
}

func listVersionsByKey(ctx context.Context, c conn, tenantID uuid.UUID, policyKey string) ([]SovereigntyPolicy, error) {
	rows, err := c.Query(ctx, `
		SELECT `+policyColumns+`
		FROM sovereignty_policies WHERE enterprise_tenant_id = $1 AND policy_key = $2
		ORDER BY version DESC
	`, tenantID, policyKey)
	if err != nil {
		return nil, fmt.Errorf("list policy versions: %w", err)
	}
	defer rows.Close()
	return scanPolicies(rows)
}

// listOtherPublished returns every currently-published policy for the
// tenant except the given policy_key -- exactly the set a new publish must
// be checked for conflicts against.
func listOtherPublished(ctx context.Context, c conn, tenantID uuid.UUID, excludePolicyKey string) ([]SovereigntyPolicy, error) {
	rows, err := c.Query(ctx, `
		SELECT `+policyColumns+`
		FROM sovereignty_policies WHERE enterprise_tenant_id = $1 AND status = 'published' AND policy_key <> $2
	`, tenantID, excludePolicyKey)
	if err != nil {
		return nil, fmt.Errorf("list other published policies: %w", err)
	}
	defer rows.Close()
	return scanPolicies(rows)
}

func scanPolicies(rows pgx.Rows) ([]SovereigntyPolicy, error) {
	var out []SovereigntyPolicy
	for rows.Next() {
		p, err := scanPolicy(rows)
		if err != nil {
			return nil, fmt.Errorf("scan policy: %w", err)
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func createEvaluationRecord(ctx context.Context, c conn, tenantID, policyID uuid.UUID, policyVersion int, decision string, reasonCodes []string, candidate map[string]any, inputsHash string, isSimulation bool, evaluatedBy *uuid.UUID, evaluatedAt time.Time) (EvaluationRecord, error) {
	reasonCodesJSON, err := json.Marshal(reasonCodes)
	if err != nil {
		return EvaluationRecord{}, fmt.Errorf("marshal reason codes: %w", err)
	}
	candidateJSON, err := json.Marshal(candidate)
	if err != nil {
		return EvaluationRecord{}, fmt.Errorf("marshal candidate: %w", err)
	}
	var rec EvaluationRecord
	var rawReasonCodes, rawCandidate []byte
	err = c.QueryRow(ctx, `
		INSERT INTO policy_evaluation_records
			(enterprise_tenant_id, sovereignty_policy_id, policy_version, decision, reason_codes, candidate, inputs_hash, is_simulation, evaluated_by, evaluated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		RETURNING id, enterprise_tenant_id, sovereignty_policy_id, policy_version, decision, reason_codes, candidate, inputs_hash, is_simulation, evaluated_by, evaluated_at, created_at
	`, tenantID, policyID, policyVersion, decision, reasonCodesJSON, candidateJSON, inputsHash, isSimulation, evaluatedBy, evaluatedAt).
		Scan(&rec.ID, &rec.TenantID, &rec.SovereigntyPolicyID, &rec.PolicyVersion, &rec.Decision, &rawReasonCodes, &rawCandidate, &rec.InputsHash, &rec.IsSimulation, &rec.EvaluatedBy, &rec.EvaluatedAt, &rec.CreatedAt)
	if err != nil {
		return EvaluationRecord{}, fmt.Errorf("insert evaluation record: %w", err)
	}
	if err := json.Unmarshal(rawReasonCodes, &rec.ReasonCodes); err != nil {
		return EvaluationRecord{}, fmt.Errorf("unmarshal reason codes: %w", err)
	}
	if err := json.Unmarshal(rawCandidate, &rec.Candidate); err != nil {
		return EvaluationRecord{}, fmt.Errorf("unmarshal candidate: %w", err)
	}
	return rec, nil
}

func listEvaluationRecords(ctx context.Context, c conn, tenantID uuid.UUID) ([]EvaluationRecord, error) {
	rows, err := c.Query(ctx, `
		SELECT id, enterprise_tenant_id, sovereignty_policy_id, policy_version, decision, reason_codes, candidate, inputs_hash, is_simulation, evaluated_by, evaluated_at, created_at
		FROM policy_evaluation_records WHERE enterprise_tenant_id = $1 ORDER BY evaluated_at DESC LIMIT 200
	`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list evaluation records: %w", err)
	}
	defer rows.Close()

	var out []EvaluationRecord
	for rows.Next() {
		var rec EvaluationRecord
		var rawReasonCodes, rawCandidate []byte
		if err := rows.Scan(&rec.ID, &rec.TenantID, &rec.SovereigntyPolicyID, &rec.PolicyVersion, &rec.Decision, &rawReasonCodes, &rawCandidate, &rec.InputsHash, &rec.IsSimulation, &rec.EvaluatedBy, &rec.EvaluatedAt, &rec.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan evaluation record: %w", err)
		}
		if err := json.Unmarshal(rawReasonCodes, &rec.ReasonCodes); err != nil {
			return nil, fmt.Errorf("unmarshal reason codes: %w", err)
		}
		if err := json.Unmarshal(rawCandidate, &rec.Candidate); err != nil {
			return nil, fmt.Errorf("unmarshal candidate: %w", err)
		}
		out = append(out, rec)
	}
	return out, rows.Err()
}
