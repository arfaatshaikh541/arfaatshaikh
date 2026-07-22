package operators

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

func createOperator(ctx context.Context, c conn, legalName, displayName, country string) (Operator, error) {
	var o Operator
	err := c.QueryRow(ctx, `
		INSERT INTO operators (legal_name, display_name, country)
		VALUES ($1, $2, $3)
		RETURNING id, legal_name, display_name, country, status, trust_level, is_fictional_demo_data, created_at
	`, legalName, displayName, country).Scan(&o.ID, &o.LegalName, &o.DisplayName, &o.Country, &o.Status, &o.TrustLevel, &o.IsFictionalDemoData, &o.CreatedAt)
	if err != nil {
		return Operator{}, fmt.Errorf("insert operator: %w", err)
	}
	return o, nil
}

func getOperatorByID(ctx context.Context, c conn, id uuid.UUID) (Operator, bool, error) {
	var o Operator
	err := c.QueryRow(ctx, `
		SELECT id, legal_name, display_name, country, status, trust_level, is_fictional_demo_data, created_at
		FROM operators WHERE id = $1
	`, id).Scan(&o.ID, &o.LegalName, &o.DisplayName, &o.Country, &o.Status, &o.TrustLevel, &o.IsFictionalDemoData, &o.CreatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Operator{}, false, nil
		}
		return Operator{}, false, fmt.Errorf("get operator: %w", err)
	}
	return o, true, nil
}

func updateOperatorProfile(ctx context.Context, c conn, id uuid.UUID, displayName string) error {
	_, err := c.Exec(ctx, `UPDATE operators SET display_name = $2, updated_at = now() WHERE id = $1`, id, displayName)
	if err != nil {
		return fmt.Errorf("update operator: %w", err)
	}
	return nil
}

func createMembership(ctx context.Context, c conn, userID, operatorID, roleID uuid.UUID) (uuid.UUID, error) {
	var id uuid.UUID
	err := c.QueryRow(ctx, `
		INSERT INTO operator_memberships (user_id, operator_id, role_id)
		VALUES ($1, $2, $3)
		RETURNING id
	`, userID, operatorID, roleID).Scan(&id)
	if err != nil {
		return uuid.Nil, fmt.Errorf("insert operator membership: %w", err)
	}
	return id, nil
}

func listMembers(ctx context.Context, c conn, operatorID uuid.UUID) ([]Membership, error) {
	rows, err := c.Query(ctx, `
		SELECT m.id, m.user_id, m.operator_id, r.key, r.name, m.status, m.created_at
		FROM operator_memberships m
		JOIN roles r ON r.id = m.role_id
		WHERE m.operator_id = $1
		ORDER BY m.created_at
	`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list operator members: %w", err)
	}
	defer rows.Close()

	var out []Membership
	for rows.Next() {
		var m Membership
		if err := rows.Scan(&m.ID, &m.UserID, &m.OperatorID, &m.RoleKey, &m.RoleName, &m.Status, &m.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan operator member: %w", err)
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

func listMyMemberships(ctx context.Context, c conn, userID uuid.UUID) ([]Membership, error) {
	rows, err := c.Query(ctx, `
		SELECT m.id, m.user_id, m.operator_id, r.key, r.name, m.status, m.created_at
		FROM operator_memberships m
		JOIN roles r ON r.id = m.role_id
		WHERE m.user_id = $1 AND m.status = 'active'
		ORDER BY m.created_at
	`, userID)
	if err != nil {
		return nil, fmt.Errorf("list my operator memberships: %w", err)
	}
	defer rows.Close()

	var out []Membership
	for rows.Next() {
		var m Membership
		if err := rows.Scan(&m.ID, &m.UserID, &m.OperatorID, &m.RoleKey, &m.RoleName, &m.Status, &m.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan operator membership: %w", err)
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

func createInvitation(ctx context.Context, c conn, operatorID, roleID, invitedBy uuid.UUID, email, tokenHash string, ttl time.Duration) (uuid.UUID, error) {
	var id uuid.UUID
	err := c.QueryRow(ctx, `
		INSERT INTO invitations (operator_id, email, role_id, invited_by, token_hash, expires_at)
		VALUES ($1, $2, $3, $4, $5, now() + ($6 * interval '1 second'))
		RETURNING id
	`, operatorID, email, roleID, invitedBy, tokenHash, ttl.Seconds()).Scan(&id)
	if err != nil {
		return uuid.Nil, fmt.Errorf("insert invitation: %w", err)
	}
	return id, nil
}

type pendingInvitation struct {
	ID         uuid.UUID
	OperatorID uuid.UUID
	RoleID     uuid.UUID
	Email      string
}

func getInvitationByTokenHash(ctx context.Context, c conn, tokenHash string) (pendingInvitation, bool, error) {
	var inv pendingInvitation
	err := c.QueryRow(ctx, `
		SELECT id, operator_id, role_id, email
		FROM invitations
		WHERE token_hash = $1 AND status = 'pending' AND expires_at > now() AND operator_id IS NOT NULL
	`, tokenHash).Scan(&inv.ID, &inv.OperatorID, &inv.RoleID, &inv.Email)
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
