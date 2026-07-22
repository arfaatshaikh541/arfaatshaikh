// Package operators implements telecom operator onboarding, memberships,
// and invitations. An operator starts in `pending_application` status and
// only a GRIDKEEP platform administrator can move it to `approved`/`active`
// (see internal/modules/platformadmin) -- an operator can never
// self-approve its own eligibility to receive real deployment plans.
package operators

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

var ErrInvalidInvitation = errors.New("invitation is invalid or has expired")

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

func (s *Service) CreateOperator(ctx context.Context, creatorUserID uuid.UUID, legalName, displayName, country string) (Operator, error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return Operator{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	op, err := createOperator(ctx, tx, legalName, displayName, country)
	if err != nil {
		return Operator{}, err
	}

	ownerRoleID, err := rbac.RoleIDByKey(ctx, tx, "operator", "operator_platform_owner")
	if err != nil {
		return Operator{}, err
	}
	if _, err := createMembership(ctx, tx, creatorUserID, op.ID, ownerRoleID); err != nil {
		return Operator{}, err
	}

	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &creatorUserID,
		ScopeType:   audit.ScopeOperator,
		ScopeID:     &op.ID,
		Action:      "operators.operator_application_submitted",
		TargetType:  "operator",
		TargetID:    &op.ID,
		Evidence:    map[string]any{"legal_name": legalName, "country": country},
	}); err != nil {
		return Operator{}, err
	}

	if err := tx.Commit(ctx); err != nil {
		return Operator{}, fmt.Errorf("commit operator creation: %w", err)
	}
	return op, nil
}

func (s *Service) GetOperator(ctx context.Context) (Operator, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	op, ok, err := getOperatorByID(ctx, scopedTx.Tx, *scope.OperatorID)
	if err != nil {
		return Operator{}, err
	}
	if !ok {
		return Operator{}, fmt.Errorf("operator not found")
	}
	return op, nil
}

func (s *Service) UpdateOperatorProfile(ctx context.Context, displayName string) error {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if err := updateOperatorProfile(ctx, scopedTx.Tx, *scope.OperatorID, displayName); err != nil {
		return err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actor,
		ScopeType:   audit.ScopeOperator,
		ScopeID:     scope.OperatorID,
		Action:      "operators.profile_updated",
		TargetType:  "operator",
		TargetID:    scope.OperatorID,
		Evidence:    map[string]any{"display_name": displayName},
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

func (s *Service) ListMembers(ctx context.Context) ([]Membership, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listMembers(ctx, scopedTx.Tx, *scope.OperatorID)
}

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
	actor := actorFromContext(ctx)

	roleID, err := rbac.RoleIDByKey(ctx, scopedTx.Tx, "operator", roleKey)
	if err != nil {
		return err
	}

	rawToken, tokenHash, err := security.GenerateOpaqueToken(32)
	if err != nil {
		return err
	}

	invID, err := createInvitation(ctx, scopedTx.Tx, *scope.OperatorID, roleID, *actor, email, tokenHash, s.cfg.InvitationTTL)
	if err != nil {
		return err
	}

	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actor,
		ScopeType:   audit.ScopeOperator,
		ScopeID:     scope.OperatorID,
		Action:      "operators.invitation_created",
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
		fmt.Sprintf("You have been invited to join a GRIDKEEP operator account.\n\nAccept your invitation:\n%s", link))

	return nil
}

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

	if _, err := createMembership(ctx, tx, userID, inv.OperatorID, inv.RoleID); err != nil {
		return uuid.Nil, err
	}
	if err := markInvitationAccepted(ctx, tx, inv.ID); err != nil {
		return uuid.Nil, err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &userID,
		ScopeType:   audit.ScopeOperator,
		ScopeID:     &inv.OperatorID,
		Action:      "operators.invitation_accepted",
		TargetType:  "invitation",
		TargetID:    &inv.ID,
	}); err != nil {
		return uuid.Nil, err
	}

	if err := tx.Commit(ctx); err != nil {
		return uuid.Nil, fmt.Errorf("commit invitation acceptance: %w", err)
	}
	return inv.OperatorID, nil
}

func actorFromContext(ctx context.Context) *uuid.UUID {
	if authUser, ok := httpserver.AuthUser(ctx); ok {
		return &authUser.UserID
	}
	return nil
}
