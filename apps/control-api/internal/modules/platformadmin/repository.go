package platformadmin

import (
	"context"
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

type tenantSummary struct {
	ID          uuid.UUID `json:"id"`
	LegalName   string    `json:"legal_name"`
	DisplayName string    `json:"display_name"`
	Country     string    `json:"country"`
	Status      string    `json:"status"`
	CreatedAt   time.Time `json:"created_at"`
}

func listTenants(ctx context.Context, c conn) ([]tenantSummary, error) {
	rows, err := c.Query(ctx, `
		SELECT id, legal_name, display_name, country, status, created_at
		FROM enterprise_tenants ORDER BY created_at
	`)
	if err != nil {
		return nil, fmt.Errorf("list tenants: %w", err)
	}
	defer rows.Close()
	var out []tenantSummary
	for rows.Next() {
		var t tenantSummary
		if err := rows.Scan(&t.ID, &t.LegalName, &t.DisplayName, &t.Country, &t.Status, &t.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan tenant: %w", err)
		}
		out = append(out, t)
	}
	return out, rows.Err()
}

func setTenantStatus(ctx context.Context, c conn, id uuid.UUID, status string) error {
	_, err := c.Exec(ctx, `UPDATE enterprise_tenants SET status = $2, updated_at = now() WHERE id = $1`, id, status)
	if err != nil {
		return fmt.Errorf("set tenant status: %w", err)
	}
	return nil
}

type operatorSummary struct {
	ID          uuid.UUID `json:"id"`
	LegalName   string    `json:"legal_name"`
	DisplayName string    `json:"display_name"`
	Country     string    `json:"country"`
	Status      string    `json:"status"`
	TrustLevel  string    `json:"trust_level"`
	CreatedAt   time.Time `json:"created_at"`
}

func listOperators(ctx context.Context, c conn) ([]operatorSummary, error) {
	rows, err := c.Query(ctx, `
		SELECT id, legal_name, display_name, country, status, trust_level, created_at
		FROM operators ORDER BY created_at
	`)
	if err != nil {
		return nil, fmt.Errorf("list operators: %w", err)
	}
	defer rows.Close()
	var out []operatorSummary
	for rows.Next() {
		var o operatorSummary
		if err := rows.Scan(&o.ID, &o.LegalName, &o.DisplayName, &o.Country, &o.Status, &o.TrustLevel, &o.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan operator: %w", err)
		}
		out = append(out, o)
	}
	return out, rows.Err()
}

func setOperatorStatus(ctx context.Context, c conn, id uuid.UUID, status string) error {
	_, err := c.Exec(ctx, `UPDATE operators SET status = $2, updated_at = now() WHERE id = $1`, id, status)
	if err != nil {
		return fmt.Errorf("set operator status: %w", err)
	}
	return nil
}

func setOperatorTrustLevel(ctx context.Context, c conn, id uuid.UUID, trustLevel string) error {
	_, err := c.Exec(ctx, `UPDATE operators SET trust_level = $2, updated_at = now() WHERE id = $1`, id, trustLevel)
	if err != nil {
		return fmt.Errorf("set operator trust level: %w", err)
	}
	return nil
}

func createSupportAccessGrant(ctx context.Context, c conn, requestedBy uuid.UUID, scopeType string, scopeID uuid.UUID, reason string, ttl time.Duration) (uuid.UUID, error) {
	var id uuid.UUID
	err := c.QueryRow(ctx, `
		INSERT INTO support_access_grants (user_id, scope_type, scope_id, reason, requested_by, expires_at)
		VALUES ($1, $2, $3, $4, $1, now() + ($5 * interval '1 second'))
		RETURNING id
	`, requestedBy, scopeType, scopeID, reason, ttl.Seconds()).Scan(&id)
	if err != nil {
		return uuid.Nil, fmt.Errorf("insert support access grant: %w", err)
	}
	return id, nil
}

func approveSupportAccessGrant(ctx context.Context, c conn, id, approvedBy uuid.UUID) error {
	tag, err := c.Exec(ctx, `
		UPDATE support_access_grants
		SET approved_by = $2, approved_at = now()
		WHERE id = $1 AND approved_at IS NULL AND revoked_at IS NULL AND requested_by <> $2
	`, id, approvedBy)
	if err != nil {
		return fmt.Errorf("approve support access grant: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return fmt.Errorf("grant not found, already decided, or approver is the requester")
	}
	return nil
}

func revokeSupportAccessGrant(ctx context.Context, c conn, id, revokedBy uuid.UUID) error {
	_, err := c.Exec(ctx, `
		UPDATE support_access_grants SET revoked_at = now(), revoked_by = $2
		WHERE id = $1 AND revoked_at IS NULL
	`, id, revokedBy)
	if err != nil {
		return fmt.Errorf("revoke support access grant: %w", err)
	}
	return nil
}

func listSupportAccessGrants(ctx context.Context, c conn) ([]SupportAccessGrant, error) {
	rows, err := c.Query(ctx, `
		SELECT id, user_id, scope_type, scope_id, reason, requested_by, approved_by, approved_at, revoked_at, expires_at, created_at
		FROM support_access_grants ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, fmt.Errorf("list support access grants: %w", err)
	}
	defer rows.Close()
	var out []SupportAccessGrant
	for rows.Next() {
		var g SupportAccessGrant
		if err := rows.Scan(&g.ID, &g.UserID, &g.ScopeType, &g.ScopeID, &g.Reason, &g.RequestedBy, &g.ApprovedBy, &g.ApprovedAt, &g.RevokedAt, &g.ExpiresAt, &g.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan support access grant: %w", err)
		}
		out = append(out, g)
	}
	return out, rows.Err()
}
