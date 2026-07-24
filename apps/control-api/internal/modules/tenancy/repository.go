package tenancy

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

const tenantColumns = `id, legal_name, display_name, country, status, is_fictional_demo_data, sustainability_ranking_mode, max_carbon_intensity_g_per_kwh, created_at`

func scanTenant(row pgx.Row) (EnterpriseTenant, error) {
	var t EnterpriseTenant
	err := row.Scan(&t.ID, &t.LegalName, &t.DisplayName, &t.Country, &t.Status, &t.IsFictionalDemoData,
		&t.SustainabilityRankingMode, &t.MaxCarbonIntensityGPerKWh, &t.CreatedAt)
	return t, err
}

func createTenant(ctx context.Context, c conn, legalName, displayName, country string) (EnterpriseTenant, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO enterprise_tenants (legal_name, display_name, country)
		VALUES ($1, $2, $3)
		RETURNING `+tenantColumns,
		legalName, displayName, country,
	)
	t, err := scanTenant(row)
	if err != nil {
		return EnterpriseTenant{}, fmt.Errorf("insert enterprise tenant: %w", err)
	}
	return t, nil
}

func getTenantByID(ctx context.Context, c conn, id uuid.UUID) (EnterpriseTenant, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+tenantColumns+` FROM enterprise_tenants WHERE id = $1`, id)
	t, err := scanTenant(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return EnterpriseTenant{}, false, nil
		}
		return EnterpriseTenant{}, false, fmt.Errorf("get enterprise tenant: %w", err)
	}
	return t, true, nil
}

func updateTenantSettings(ctx context.Context, c conn, id uuid.UUID, displayName string) error {
	_, err := c.Exec(ctx, `UPDATE enterprise_tenants SET display_name = $2, updated_at = now() WHERE id = $1`, id, displayName)
	if err != nil {
		return fmt.Errorf("update enterprise tenant: %w", err)
	}
	return nil
}

// updateSustainabilityPreferences is Milestone 14's own tenant-settings PATCH
// -- kept as a separate function (and separate service method/route) from
// updateTenantSettings because that endpoint always requires a non-empty
// display_name, whereas a carbon ceiling of nil is a meaningful choice ("no
// hard limit"), not a validation failure.
func updateSustainabilityPreferences(ctx context.Context, c conn, id uuid.UUID, rankingMode string, maxCarbonIntensityGPerKWh *float64) error {
	_, err := c.Exec(ctx, `
		UPDATE enterprise_tenants SET sustainability_ranking_mode = $2, max_carbon_intensity_g_per_kwh = $3, updated_at = now()
		WHERE id = $1
	`, id, rankingMode, maxCarbonIntensityGPerKWh)
	if err != nil {
		return fmt.Errorf("update enterprise tenant sustainability preferences: %w", err)
	}
	return nil
}

func createMembership(ctx context.Context, c conn, userID, tenantID, roleID uuid.UUID) (uuid.UUID, error) {
	var id uuid.UUID
	err := c.QueryRow(ctx, `
		INSERT INTO enterprise_memberships (user_id, enterprise_tenant_id, role_id)
		VALUES ($1, $2, $3)
		RETURNING id
	`, userID, tenantID, roleID).Scan(&id)
	if err != nil {
		return uuid.Nil, fmt.Errorf("insert enterprise membership: %w", err)
	}
	return id, nil
}

func listMembers(ctx context.Context, c conn, tenantID uuid.UUID) ([]Membership, error) {
	rows, err := c.Query(ctx, `
		SELECT m.id, m.user_id, m.enterprise_tenant_id, r.key, r.name, m.status, m.created_at
		FROM enterprise_memberships m
		JOIN roles r ON r.id = m.role_id
		WHERE m.enterprise_tenant_id = $1
		ORDER BY m.created_at
	`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list enterprise members: %w", err)
	}
	defer rows.Close()

	var out []Membership
	for rows.Next() {
		var m Membership
		if err := rows.Scan(&m.ID, &m.UserID, &m.TenantID, &m.RoleKey, &m.RoleName, &m.Status, &m.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan enterprise member: %w", err)
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

// listMyMemberships is called with a platform_bypass-scoped connection
// because it is filtered to the caller's own user_id -- a user is always
// entitled to see their own memberships across every tenant.
func listMyMemberships(ctx context.Context, c conn, userID uuid.UUID) ([]Membership, error) {
	rows, err := c.Query(ctx, `
		SELECT m.id, m.user_id, m.enterprise_tenant_id, r.key, r.name, m.status, m.created_at
		FROM enterprise_memberships m
		JOIN roles r ON r.id = m.role_id
		WHERE m.user_id = $1 AND m.status = 'active'
		ORDER BY m.created_at
	`, userID)
	if err != nil {
		return nil, fmt.Errorf("list my enterprise memberships: %w", err)
	}
	defer rows.Close()

	var out []Membership
	for rows.Next() {
		var m Membership
		if err := rows.Scan(&m.ID, &m.UserID, &m.TenantID, &m.RoleKey, &m.RoleName, &m.Status, &m.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan enterprise membership: %w", err)
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

func createInvitation(ctx context.Context, c conn, tenantID, roleID, invitedBy uuid.UUID, email, tokenHash string, ttl time.Duration) (uuid.UUID, error) {
	var id uuid.UUID
	err := c.QueryRow(ctx, `
		INSERT INTO invitations (enterprise_tenant_id, email, role_id, invited_by, token_hash, expires_at)
		VALUES ($1, $2, $3, $4, $5, now() + ($6 * interval '1 second'))
		RETURNING id
	`, tenantID, email, roleID, invitedBy, tokenHash, ttl.Seconds()).Scan(&id)
	if err != nil {
		return uuid.Nil, fmt.Errorf("insert invitation: %w", err)
	}
	return id, nil
}

type pendingInvitation struct {
	ID       uuid.UUID
	TenantID uuid.UUID
	RoleID   uuid.UUID
	Email    string
}

// getInvitationByTokenHash must be called against a platform_bypass-scoped
// connection: the recipient has no membership (and often no session) yet,
// so RLS on the invitations table would otherwise hide the row entirely.
func getInvitationByTokenHash(ctx context.Context, c conn, tokenHash string) (pendingInvitation, bool, error) {
	var inv pendingInvitation
	err := c.QueryRow(ctx, `
		SELECT id, enterprise_tenant_id, role_id, email
		FROM invitations
		WHERE token_hash = $1 AND status = 'pending' AND expires_at > now() AND enterprise_tenant_id IS NOT NULL
	`, tokenHash).Scan(&inv.ID, &inv.TenantID, &inv.RoleID, &inv.Email)
	if err != nil {
		if err == pgx.ErrNoRows {
			return pendingInvitation{}, false, nil
		}
		return pendingInvitation{}, false, fmt.Errorf("get invitation: %w", err)
	}
	return inv, true, nil
}

func markInvitationAccepted(ctx context.Context, c conn, id uuid.UUID) error {
	_, err := c.Exec(ctx, `UPDATE invitations SET status = 'accepted', accepted_at = now() WHERE id = $1`, id)
	if err != nil {
		return fmt.Errorf("mark invitation accepted: %w", err)
	}
	return nil
}

// getUserEmailByID looks up the current, authoritative email address for an
// authenticated user directly from the shared users table, so
// AcceptInvitation can verify the invitation was actually addressed to the
// person accepting it rather than trusting whichever session bearer
// happens to hold a still-valid invitation token.
func getUserEmailByID(ctx context.Context, c conn, userID uuid.UUID) (string, bool, error) {
	var email string
	err := c.QueryRow(ctx, `SELECT email FROM users WHERE id = $1`, userID).Scan(&email)
	if err != nil {
		if err == pgx.ErrNoRows {
			return "", false, nil
		}
		return "", false, fmt.Errorf("get user email: %w", err)
	}
	return email, true, nil
}
