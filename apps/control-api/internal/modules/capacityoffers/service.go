package capacityoffers

import (
	"context"
	"errors"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
)

var (
	ErrClusterNotFound        = errors.New("cluster not found or does not belong to this operator")
	ErrOfferNotFound          = errors.New("capacity offer not found")
	ErrAgreementNotFound      = errors.New("bilateral agreement not found")
	ErrAgreementNotActive     = errors.New("bilateral agreement is not active")
	ErrGrantNotFound          = errors.New("capacity offer grant not found or already revoked")
	ErrGrantAgreementMismatch = errors.New("bilateral agreement does not belong to the same enterprise tenant as the grant")
)

type Service struct {
	store *dbpkg.Store
}

func NewService(store *dbpkg.Store) *Service {
	return &Service{store: store}
}

func actorFromContext(ctx context.Context) uuid.UUID {
	if authUser, ok := httpserver.AuthUser(ctx); ok {
		return authUser.UserID
	}
	return uuid.Nil
}

func (s *Service) CreateOffer(ctx context.Context, in CreateOfferInput) (CapacityOffer, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	regionID, exists, err := clusterRegion(ctx, scopedTx.Tx, in.ClusterID, *scope.OperatorID)
	if err != nil {
		return CapacityOffer{}, err
	}
	if !exists {
		return CapacityOffer{}, ErrClusterNotFound
	}

	o, err := createOffer(ctx, scopedTx.Tx, *scope.OperatorID, regionID, actor, in)
	if err != nil {
		return CapacityOffer{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "capacity_offers.created", TargetType: "capacity_offer", TargetID: &o.ID,
		Evidence: map[string]any{"cluster_id": in.ClusterID, "accelerator_type": in.AcceleratorType, "total_capacity": in.TotalCapacity},
	}); err != nil {
		return CapacityOffer{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return CapacityOffer{}, err
	}
	return o, nil
}

func (s *Service) ListOffers(ctx context.Context) ([]CapacityOffer, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listOffers(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) GetOffer(ctx context.Context, id uuid.UUID) (CapacityOffer, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	o, exists, err := getOfferByID(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return CapacityOffer{}, err
	}
	if !exists {
		return CapacityOffer{}, ErrOfferNotFound
	}
	return o, nil
}

func (s *Service) UpdateOffer(ctx context.Context, id uuid.UUID, in UpdateOfferInput) (CapacityOffer, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := updateOffer(ctx, scopedTx.Tx, *scope.OperatorID, id, in)
	if err != nil {
		return CapacityOffer{}, err
	}
	if !ok {
		return CapacityOffer{}, ErrOfferNotFound
	}
	o, exists, err := getOfferByID(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return CapacityOffer{}, err
	}
	if !exists {
		return CapacityOffer{}, ErrOfferNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "capacity_offers.updated", TargetType: "capacity_offer", TargetID: &id,
		Evidence: map[string]any{
			"status": o.Status, "available_capacity": o.AvailableCapacity,
			"visibility": o.Visibility, "degraded": o.Degraded, "degraded_reason": o.DegradedReason,
		},
	}); err != nil {
		return CapacityOffer{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return CapacityOffer{}, err
	}
	return o, nil
}

func (s *Service) ListReservations(ctx context.Context) ([]Reservation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listReservationsForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

// ---------------------------------------------------------------------
// Bilateral agreements (Milestone 12: Federated Capacity Exchange)
// ---------------------------------------------------------------------

func (s *Service) CreateAgreement(ctx context.Context, in CreateAgreementInput) (BilateralAgreement, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	a, err := createAgreement(ctx, scopedTx.Tx, *scope.OperatorID, actor, in)
	if err != nil {
		return BilateralAgreement{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "bilateral_agreements.created", TargetType: "bilateral_agreement", TargetID: &a.ID,
		Evidence: map[string]any{"enterprise_tenant_id": in.EnterpriseTenantID, "platform_fee_rate": in.PlatformFeeRate, "currency": in.Currency},
	}); err != nil {
		return BilateralAgreement{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return BilateralAgreement{}, err
	}
	return a, nil
}

func (s *Service) ListAgreements(ctx context.Context) ([]BilateralAgreement, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listAgreementsForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) TerminateAgreement(ctx context.Context, id uuid.UUID) (BilateralAgreement, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getAgreementByID(ctx, scopedTx.Tx, *scope.OperatorID, id); err != nil {
		return BilateralAgreement{}, err
	} else if !exists {
		return BilateralAgreement{}, ErrAgreementNotFound
	}
	ok, err := terminateAgreement(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return BilateralAgreement{}, err
	}
	if !ok {
		return BilateralAgreement{}, ErrAgreementNotActive
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "bilateral_agreements.terminated", TargetType: "bilateral_agreement", TargetID: &id,
	}); err != nil {
		return BilateralAgreement{}, err
	}
	a, exists, err := getAgreementByID(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return BilateralAgreement{}, err
	}
	if !exists {
		return BilateralAgreement{}, ErrAgreementNotFound
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return BilateralAgreement{}, err
	}
	return a, nil
}

// ---------------------------------------------------------------------
// Capacity offer grants (the per-tenant "invitation" a private offer needs)
// ---------------------------------------------------------------------

// CreateGrant issues (or re-activates) a per-tenant grant against one of
// this operator's own offers -- the mechanism that makes a private offer
// visible/reservable for that one tenant at all (see
// capacity_offers_enterprise_read's RLS policy). If bilateralAgreementID is
// given, it must belong to the same operator and the same enterprise tenant
// as the grant -- a grant is never allowed to silently attach to a
// different tenant's commercial terms.
func (s *Service) CreateGrant(ctx context.Context, offerID uuid.UUID, in CreateGrantInput) (CapacityOfferGrant, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	operatorID := *scope.OperatorID

	if _, exists, err := getOfferByID(ctx, scopedTx.Tx, operatorID, offerID); err != nil {
		return CapacityOfferGrant{}, err
	} else if !exists {
		return CapacityOfferGrant{}, ErrOfferNotFound
	}
	if in.BilateralAgreementID != nil {
		agreement, exists, err := getAgreementByID(ctx, scopedTx.Tx, operatorID, *in.BilateralAgreementID)
		if err != nil {
			return CapacityOfferGrant{}, err
		}
		if !exists {
			return CapacityOfferGrant{}, ErrAgreementNotFound
		}
		if agreement.EnterpriseTenantID != in.EnterpriseTenantID {
			return CapacityOfferGrant{}, ErrGrantAgreementMismatch
		}
	}

	g, err := createGrant(ctx, scopedTx.Tx, offerID, operatorID, actor, in)
	if err != nil {
		return CapacityOfferGrant{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "capacity_offer_grants.created", TargetType: "capacity_offer_grant", TargetID: &g.ID,
		Evidence: map[string]any{"capacity_offer_id": offerID, "enterprise_tenant_id": in.EnterpriseTenantID},
	}); err != nil {
		return CapacityOfferGrant{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return CapacityOfferGrant{}, err
	}
	return g, nil
}

func (s *Service) ListGrantsForOffer(ctx context.Context, offerID uuid.UUID) ([]CapacityOfferGrant, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listGrantsForOffer(ctx, scopedTx.Tx, *scope.OperatorID, offerID)
}

func (s *Service) RevokeGrant(ctx context.Context, id uuid.UUID) error {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := revokeGrant(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return err
	}
	if !ok {
		return ErrGrantNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "capacity_offer_grants.revoked", TargetType: "capacity_offer_grant", TargetID: &id,
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}
