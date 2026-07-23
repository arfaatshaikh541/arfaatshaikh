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
	ErrClusterNotFound = errors.New("cluster not found or does not belong to this operator")
	ErrOfferNotFound   = errors.New("capacity offer not found")
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
		Evidence: map[string]any{"status": o.Status, "available_capacity": o.AvailableCapacity},
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
