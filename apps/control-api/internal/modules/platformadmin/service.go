// Package platformadmin implements GRIDKEEP platform-administration actions:
// tenant/operator lifecycle management and just-in-time support access.
// Every handler in this package runs under rbac.RequirePlatformPermission,
// which is deliberately separate from and never inherited via enterprise or
// operator memberships.
package platformadmin

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
)

const defaultSupportAccessTTL = 4 * time.Hour

type Service struct {
	store *dbpkg.Store
}

func NewService(store *dbpkg.Store) *Service {
	return &Service{store: store}
}

func (s *Service) ListTenants(ctx context.Context) ([]tenantSummary, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listTenants(ctx, scopedTx.Tx)
}

func (s *Service) SetTenantStatus(ctx context.Context, actorUserID, tenantID uuid.UUID, status string) error {
	scopedTx, _ := rbac.TxFromContext(ctx)
	if err := setTenantStatus(ctx, scopedTx.Tx, tenantID, status); err != nil {
		return err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actorUserID,
		ScopeType:   audit.ScopePlatform,
		Action:      "platformadmin.tenant_status_changed",
		TargetType:  "enterprise_tenant",
		TargetID:    &tenantID,
		Evidence:    map[string]any{"status": status},
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

func (s *Service) ListOperators(ctx context.Context) ([]operatorSummary, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listOperators(ctx, scopedTx.Tx)
}

func (s *Service) SetOperatorStatus(ctx context.Context, actorUserID, operatorID uuid.UUID, status string) error {
	scopedTx, _ := rbac.TxFromContext(ctx)
	if err := setOperatorStatus(ctx, scopedTx.Tx, operatorID, status); err != nil {
		return err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actorUserID,
		ScopeType:   audit.ScopePlatform,
		Action:      "platformadmin.operator_status_changed",
		TargetType:  "operator",
		TargetID:    &operatorID,
		Evidence:    map[string]any{"status": status},
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

func (s *Service) SetOperatorTrustLevel(ctx context.Context, actorUserID, operatorID uuid.UUID, trustLevel string) error {
	scopedTx, _ := rbac.TxFromContext(ctx)
	if err := setOperatorTrustLevel(ctx, scopedTx.Tx, operatorID, trustLevel); err != nil {
		return err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actorUserID,
		ScopeType:   audit.ScopePlatform,
		Action:      "platformadmin.operator_trust_level_changed",
		TargetType:  "operator",
		TargetID:    &operatorID,
		Evidence:    map[string]any{"trust_level": trustLevel},
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

// RequestSupportAccessGrant creates a pending, unapproved grant. It must be
// approved by a different platform user before it grants any access -- see
// the support_access_grants_no_self_approval CHECK constraint and
// ApproveSupportAccessGrant below.
func (s *Service) RequestSupportAccessGrant(ctx context.Context, requestedBy uuid.UUID, scopeType string, scopeID uuid.UUID, reason string) (uuid.UUID, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	id, err := createSupportAccessGrant(ctx, scopedTx.Tx, requestedBy, scopeType, scopeID, reason, defaultSupportAccessTTL)
	if err != nil {
		return uuid.Nil, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &requestedBy,
		ScopeType:   audit.ScopePlatform,
		Action:      "platformadmin.support_access_requested",
		TargetType:  "support_access_grant",
		TargetID:    &id,
		Evidence:    map[string]any{"scope_type": scopeType, "scope_id": scopeID, "reason": reason},
	}); err != nil {
		return uuid.Nil, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return uuid.Nil, err
	}
	return id, nil
}

func (s *Service) ApproveSupportAccessGrant(ctx context.Context, approvedBy, grantID uuid.UUID) error {
	scopedTx, _ := rbac.TxFromContext(ctx)
	if err := approveSupportAccessGrant(ctx, scopedTx.Tx, grantID, approvedBy); err != nil {
		return fmt.Errorf("approve support access grant: %w", err)
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &approvedBy,
		ScopeType:   audit.ScopePlatform,
		Action:      "platformadmin.support_access_approved",
		TargetType:  "support_access_grant",
		TargetID:    &grantID,
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

func (s *Service) RevokeSupportAccessGrant(ctx context.Context, revokedBy, grantID uuid.UUID) error {
	scopedTx, _ := rbac.TxFromContext(ctx)
	if err := revokeSupportAccessGrant(ctx, scopedTx.Tx, grantID, revokedBy); err != nil {
		return err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &revokedBy,
		ScopeType:   audit.ScopePlatform,
		Action:      "platformadmin.support_access_revoked",
		TargetType:  "support_access_grant",
		TargetID:    &grantID,
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

func (s *Service) ListSupportAccessGrants(ctx context.Context) ([]SupportAccessGrant, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listSupportAccessGrants(ctx, scopedTx.Tx)
}
