// Package db owns the PostgreSQL connection pool and the request-scoped,
// row-level-security-aware transaction helper used throughout control-api.
//
// GRIDKEEP enforces tenant/operator isolation in two independent layers:
// application-level scope checks in each module's service layer, AND
// PostgreSQL Row-Level Security policies driven by session GUCs set here.
// Neither layer alone is trusted; both must agree for a scoped row to be
// visible.
package db

import (
	"context"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Store struct {
	Pool *pgxpool.Pool
}

func Connect(ctx context.Context, databaseURL string) (*Store, error) {
	cfg, err := pgxpool.ParseConfig(databaseURL)
	if err != nil {
		return nil, fmt.Errorf("parse database url: %w", err)
	}

	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, fmt.Errorf("create connection pool: %w", err)
	}

	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("ping database: %w", err)
	}

	return &Store{Pool: pool}, nil
}

func (s *Store) Close() {
	s.Pool.Close()
}

// Scope describes the request-scoped identity a caller has been authorized
// to act as. It is derived server-side from the authenticated session and
// its memberships — it is never accepted from client-supplied input.
type Scope struct {
	TenantID       *uuid.UUID
	OperatorID     *uuid.UUID
	PlatformBypass bool
}

// BeginScoped opens a transaction and sets PostgreSQL session GUCs for the
// duration of that transaction so Row-Level Security policies can enforce
// tenant/operator isolation independently of the application layer. Callers
// MUST commit or rollback the returned transaction.
func (s *Store) BeginScoped(ctx context.Context, scope Scope) (pgx.Tx, error) {
	tx, err := s.Pool.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return nil, fmt.Errorf("begin transaction: %w", err)
	}

	tenantVal := ""
	if scope.TenantID != nil {
		tenantVal = scope.TenantID.String()
	}
	operatorVal := ""
	if scope.OperatorID != nil {
		operatorVal = scope.OperatorID.String()
	}
	bypassVal := "false"
	if scope.PlatformBypass {
		bypassVal = "true"
	}

	if _, err := tx.Exec(ctx, "SELECT set_config('app.tenant_id', $1, true)", tenantVal); err != nil {
		_ = tx.Rollback(ctx)
		return nil, fmt.Errorf("set tenant scope: %w", err)
	}
	if _, err := tx.Exec(ctx, "SELECT set_config('app.operator_id', $1, true)", operatorVal); err != nil {
		_ = tx.Rollback(ctx)
		return nil, fmt.Errorf("set operator scope: %w", err)
	}
	if _, err := tx.Exec(ctx, "SELECT set_config('app.platform_bypass', $1, true)", bypassVal); err != nil {
		_ = tx.Rollback(ctx)
		return nil, fmt.Errorf("set platform bypass scope: %w", err)
	}

	return tx, nil
}
