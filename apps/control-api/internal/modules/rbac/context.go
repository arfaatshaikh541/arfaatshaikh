package rbac

import (
	"context"

	"github.com/jackc/pgx/v5"
)

type ctxKey int

const (
	ctxKeyScope ctxKey = iota
	ctxKeyTx
)

// ScopedTx wraps a request-scoped, RLS-configured transaction. The
// permission-check middleware begins it; the handler that ultimately
// receives the request owns committing it. If the handler returns without
// calling Commit, the middleware's deferred cleanup rolls it back — so a
// forgotten commit fails safe (no partial write survives), it never leaks an
// uncommitted change.
type ScopedTx struct {
	Tx        pgx.Tx
	committed bool
}

func (s *ScopedTx) Commit(ctx context.Context) error {
	if err := s.Tx.Commit(ctx); err != nil {
		return err
	}
	s.committed = true
	return nil
}

func withScope(ctx context.Context, scope Scope) context.Context {
	return context.WithValue(ctx, ctxKeyScope, scope)
}

func FromContext(ctx context.Context) (Scope, bool) {
	s, ok := ctx.Value(ctxKeyScope).(Scope)
	return s, ok
}

func withTx(ctx context.Context, tx *ScopedTx) context.Context {
	return context.WithValue(ctx, ctxKeyTx, tx)
}

// TxFromContext returns the request-scoped, RLS-configured transaction
// opened by the permission-check middleware for this request.
func TxFromContext(ctx context.Context) (*ScopedTx, bool) {
	tx, ok := ctx.Value(ctxKeyTx).(*ScopedTx)
	return tx, ok
}
