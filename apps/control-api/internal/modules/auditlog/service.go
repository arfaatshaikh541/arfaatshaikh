// Package auditlog exposes read-only views over the append-only,
// hash-chained audit_events table written by internal/platform/audit. It
// never writes to audit_events itself.
package auditlog

import (
	"context"

	"gridkeep/control-api/internal/modules/rbac"
	dbpkg "gridkeep/control-api/internal/platform/db"
)

const defaultLimit = 100

type Service struct {
	store *dbpkg.Store
}

func NewService(store *dbpkg.Store) *Service {
	return &Service{store: store}
}

func (s *Service) ListEnterpriseEvents(ctx context.Context) ([]Event, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listEvents(ctx, scopedTx.Tx, "enterprise", *scope.TenantID, defaultLimit)
}

func (s *Service) ListOperatorEvents(ctx context.Context) ([]Event, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listEvents(ctx, scopedTx.Tx, "operator", *scope.OperatorID, defaultLimit)
}

func (s *Service) ListPlatformEvents(ctx context.Context) ([]Event, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listPlatformEvents(ctx, scopedTx.Tx, defaultLimit)
}
