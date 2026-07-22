// Package tenancy implements enterprise tenants, memberships, and
// invitations. Tenant identity for any request is always resolved by the
// rbac middleware from the caller's session + membership -- handlers here
// never trust a tenant ID except as the already-authorized value the
// middleware placed in the request scope.
package tenancy

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
	"gridkeep/control-api/internal/platform/mailer"
	"gridkeep/control-api/internal/platform/security"
)

var (
	ErrInvalidInvitation = errors.New("invitation is invalid or has expired")
)

type Config struct {
	InvitationTTL time.Duration
	PublicBaseURL string
}

type Service struct {
	store  *dbpkg.Store
	mailer *mailer.Mailer
	cfg    Config
}

func NewService(store *dbpkg.Store, m *mailer.Mailer, cfg Config) *Service {
	return &Service{store: store, mailer: m, cfg: cfg}
}

func (s *Service) CreateTenant(ctx context.Context, creatorUserID uuid.UUID, legalName, displayName, country string) (EnterpriseTenant, error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return EnterpriseTenant{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	tenant, err := createTenant(ctx, tx, legalName, displayName, country)
	if err != nil {
		return EnterpriseTenant{}, err
	}

	ownerRoleID, err := rbac.RoleIDByKey(ctx, tx, "enterprise", "enterprise_owner")
	if err != nil {
		return EnterpriseTenant{}, err
	}
	if _, err := createMembership(ctx, tx, creatorUserID, tenant.ID, ownerRoleID); err != nil {
		return EnterpriseTenant{}, err
	}

	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &creatorUserID,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     &tenant.ID,
		Action:      "tenancy.tenant_created",
		TargetType:  "enterprise_tenant",
		TargetID:    &tenant.ID,
		Evidence:    map[string]any{"legal_name": legalName, "country": country},
	}); err != nil {
		return EnterpriseTenant{}, err
	}

	if err := tx.Commit(ctx); err != nil {
		return EnterpriseTenant{}, fmt.Errorf("commit tenant creation: %w", err)
	}
	return tenant, nil
}

func (s *Service) GetTenant(ctx context.Context) (EnterpriseTenant, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	tenant, ok, err := getTenantByID(ctx, scopedTx.Tx, *scope.TenantID)
	if err != nil {
		return EnterpriseTenant{}, err
	}
	if !ok {
		return EnterpriseTenant{}, fmt.Errorf("tenant not found")
	}
	return tenant, nil
}

func (s *Service) UpdateTenantSettings(ctx context.Context, displayName string) error {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	authUser := actorFromScope(ctx)

	if err := updateTenantSettings(ctx, scopedTx.Tx, *scope.TenantID, displayName); err != nil {
		return err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: authUser,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "tenancy.settings_updated",
		TargetType:  "enterprise_tenant",
		TargetID:    scope.TenantID,
		Evidence:    map[string]any{"display_name": displayName},
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

func (s *Service) ListMembers(ctx context.Context) ([]Membership, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listMembers(ctx, scopedTx.Tx, *scope.TenantID)
}

// ListMyMemberships returns every active enterprise membership for the
// caller, across all tenants -- used to drive the tenant switcher in the UI.
// It runs its own platform_bypass-scoped read since it is not bound to a
// single tenant's rbac middleware.
func (s *Service) ListMyMemberships(ctx context.Context, userID uuid.UUID) ([]Membership, error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return nil, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()
	return listMyMemberships(ctx, tx, userID)
}

func (s *Service) CreateInvitation(ctx context.Context, email, roleKey string) error {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	authUser := actorFromScope(ctx)

	roleID, err := rbac.RoleIDByKey(ctx, scopedTx.Tx, "enterprise", roleKey)
	if err != nil {
		return err
	}

	rawToken, tokenHash, err := security.GenerateOpaqueToken(32)
	if err != nil {
		return err
	}

	invID, err := createInvitation(ctx, scopedTx.Tx, *scope.TenantID, roleID, *authUser, email, tokenHash, s.cfg.InvitationTTL)
	if err != nil {
		return err
	}

	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: authUser,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "tenancy.invitation_created",
		TargetType:  "invitation",
		TargetID:    &invID,
		Evidence:    map[string]any{"email": email, "role": roleKey},
	}); err != nil {
		return err
	}

	if err := scopedTx.Commit(ctx); err != nil {
		return err
	}

	link := fmt.Sprintf("%s/invitations/accept?token=%s", s.cfg.PublicBaseURL, rawToken)
	_ = s.mailer.Send(email, "You have been invited to GRIDKEEP",
		fmt.Sprintf("You have been invited to join a GRIDKEEP enterprise tenant.\n\nAccept your invitation:\n%s", link))

	return nil
}

// AcceptInvitation resolves the invitation by raw token (platform_bypass
// scoped, since the recipient has no membership yet) and creates the
// membership for the authenticated userID accepting it.
func (s *Service) AcceptInvitation(ctx context.Context, userID uuid.UUID, rawToken string) (uuid.UUID, error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return uuid.Nil, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	tokenHash := security.HashToken(rawToken)
	inv, ok, err := getInvitationByTokenHash(ctx, tx, tokenHash)
	if err != nil {
		return uuid.Nil, err
	}
	if !ok {
		return uuid.Nil, ErrInvalidInvitation
	}

	if _, err := createMembership(ctx, tx, userID, inv.TenantID, inv.RoleID); err != nil {
		return uuid.Nil, err
	}
	if err := markInvitationAccepted(ctx, tx, inv.ID); err != nil {
		return uuid.Nil, err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &userID,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     &inv.TenantID,
		Action:      "tenancy.invitation_accepted",
		TargetType:  "invitation",
		TargetID:    &inv.ID,
	}); err != nil {
		return uuid.Nil, err
	}

	if err := tx.Commit(ctx); err != nil {
		return uuid.Nil, fmt.Errorf("commit invitation acceptance: %w", err)
	}
	return inv.TenantID, nil
}

func actorFromScope(ctx context.Context) *uuid.UUID {
	if authUser, ok := httpserver.AuthUser(ctx); ok {
		return &authUser.UserID
	}
	return nil
}
