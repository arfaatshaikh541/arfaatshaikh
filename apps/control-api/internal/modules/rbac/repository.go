package rbac

import (
	"context"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

// enterpriseMembershipPermission looks up whether userID has an active
// membership in tenantID whose role grants permissionKey, and returns the
// tenant's current status and the role key for auditing. It must be called
// inside a transaction already scoped (SET LOCAL app.tenant_id) to tenantID,
// so RLS on enterprise_memberships permits the row to be seen at all.
func enterpriseMembershipPermission(ctx context.Context, tx pgx.Tx, userID, tenantID uuid.UUID, permissionKey string) (roleKey string, tenantStatus string, granted bool, err error) {
	err = tx.QueryRow(ctx, `
		SELECT t.status, r.key,
			EXISTS (
				SELECT 1 FROM role_permissions rp
				JOIN permissions p ON p.id = rp.permission_id
				WHERE rp.role_id = r.id AND p.key = $3
			)
		FROM enterprise_memberships m
		JOIN enterprise_tenants t ON t.id = m.enterprise_tenant_id
		JOIN roles r ON r.id = m.role_id
		WHERE m.user_id = $1 AND m.enterprise_tenant_id = $2 AND m.status = 'active'
		LIMIT 1
	`, userID, tenantID, permissionKey).Scan(&tenantStatus, &roleKey, &granted)
	if err != nil {
		if err == pgx.ErrNoRows {
			return "", "", false, nil
		}
		return "", "", false, fmt.Errorf("lookup enterprise membership permission: %w", err)
	}
	return roleKey, tenantStatus, granted, nil
}

// enterpriseMembership looks up whether userID has any active membership in
// tenantID, without checking a specific permission -- used for read views
// available to every member of a tenant (e.g. viewing the tenant profile or
// member roster).
func enterpriseMembership(ctx context.Context, tx pgx.Tx, userID, tenantID uuid.UUID) (roleKey string, tenantStatus string, isMember bool, err error) {
	err = tx.QueryRow(ctx, `
		SELECT t.status, r.key
		FROM enterprise_memberships m
		JOIN enterprise_tenants t ON t.id = m.enterprise_tenant_id
		JOIN roles r ON r.id = m.role_id
		WHERE m.user_id = $1 AND m.enterprise_tenant_id = $2 AND m.status = 'active'
		LIMIT 1
	`, userID, tenantID).Scan(&tenantStatus, &roleKey)
	if err != nil {
		if err == pgx.ErrNoRows {
			return "", "", false, nil
		}
		return "", "", false, fmt.Errorf("lookup enterprise membership: %w", err)
	}
	return roleKey, tenantStatus, true, nil
}

func operatorMembershipPermission(ctx context.Context, tx pgx.Tx, userID, operatorID uuid.UUID, permissionKey string) (roleKey string, operatorStatus string, granted bool, err error) {
	err = tx.QueryRow(ctx, `
		SELECT o.status, r.key,
			EXISTS (
				SELECT 1 FROM role_permissions rp
				JOIN permissions p ON p.id = rp.permission_id
				WHERE rp.role_id = r.id AND p.key = $3
			)
		FROM operator_memberships m
		JOIN operators o ON o.id = m.operator_id
		JOIN roles r ON r.id = m.role_id
		WHERE m.user_id = $1 AND m.operator_id = $2 AND m.status = 'active'
		LIMIT 1
	`, userID, operatorID, permissionKey).Scan(&operatorStatus, &roleKey, &granted)
	if err != nil {
		if err == pgx.ErrNoRows {
			return "", "", false, nil
		}
		return "", "", false, fmt.Errorf("lookup operator membership permission: %w", err)
	}
	return roleKey, operatorStatus, granted, nil
}

// operatorMembership is the operator-scope equivalent of enterpriseMembership.
func operatorMembership(ctx context.Context, tx pgx.Tx, userID, operatorID uuid.UUID) (roleKey string, operatorStatus string, isMember bool, err error) {
	err = tx.QueryRow(ctx, `
		SELECT o.status, r.key
		FROM operator_memberships m
		JOIN operators o ON o.id = m.operator_id
		JOIN roles r ON r.id = m.role_id
		WHERE m.user_id = $1 AND m.operator_id = $2 AND m.status = 'active'
		LIMIT 1
	`, userID, operatorID).Scan(&operatorStatus, &roleKey)
	if err != nil {
		if err == pgx.ErrNoRows {
			return "", "", false, nil
		}
		return "", "", false, fmt.Errorf("lookup operator membership: %w", err)
	}
	return roleKey, operatorStatus, true, nil
}

// platformPermission does not require RLS scoping: platform_role_assignments
// carries no tenant/operator ownership column.
func platformPermission(ctx context.Context, conn queryable, userID uuid.UUID, permissionKey string) (roleKey string, granted bool, err error) {
	err = conn.QueryRow(ctx, `
		SELECT r.key,
			EXISTS (
				SELECT 1 FROM role_permissions rp
				JOIN permissions p ON p.id = rp.permission_id
				WHERE rp.role_id = r.id AND p.key = $2
			)
		FROM platform_role_assignments a
		JOIN roles r ON r.id = a.role_id
		WHERE a.user_id = $1 AND a.status = 'active'
		LIMIT 1
	`, userID, permissionKey).Scan(&roleKey, &granted)
	if err != nil {
		if err == pgx.ErrNoRows {
			return "", false, nil
		}
		return "", false, fmt.Errorf("lookup platform permission: %w", err)
	}
	return roleKey, granted, nil
}

// activeSupportAccessGrant checks whether userID currently holds a
// non-expired, non-revoked, approved support-access grant for the given
// scope. This is the ONLY path by which a platform user may act inside an
// enterprise/operator scope without a membership of their own.
func activeSupportAccessGrant(ctx context.Context, conn queryable, userID uuid.UUID, scopeType string, scopeID uuid.UUID) (bool, error) {
	var exists bool
	err := conn.QueryRow(ctx, `
		SELECT EXISTS (
			SELECT 1 FROM support_access_grants
			WHERE user_id = $1 AND scope_type = $2 AND scope_id = $3
				AND approved_at IS NOT NULL
				AND revoked_at IS NULL
				AND expires_at > now()
		)
	`, userID, scopeType, scopeID).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("lookup support access grant: %w", err)
	}
	return exists, nil
}

type queryable interface {
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

// RoleIDByKey resolves a system role's ID from its (scope_type, key) pair,
// e.g. ("enterprise", "enterprise_owner"). Used when a module needs to
// assign a role at creation time (e.g. the creator of a new tenant becomes
// its owner).
func RoleIDByKey(ctx context.Context, c queryable, scopeType, key string) (uuid.UUID, error) {
	var id uuid.UUID
	err := c.QueryRow(ctx, `SELECT id FROM roles WHERE scope_type = $1 AND key = $2`, scopeType, key).Scan(&id)
	if err != nil {
		return uuid.Nil, fmt.Errorf("resolve role %s/%s: %w", scopeType, key, err)
	}
	return id, nil
}
