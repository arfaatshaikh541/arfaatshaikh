package audit_test

import (
	"context"
	"testing"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/testutil"
)

func TestRecord_BuildsAValidHashChain(t *testing.T) {
	store := testutil.NewStore(t)
	ctx := context.Background()

	actor := insertTestUser(t, store, "hash-chain-actor@example.com")

	tx, err := store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		t.Fatalf("begin scoped tx: %v", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopePlatform,
		Action:      "test.event_one",
	}); err != nil {
		t.Fatalf("record first event: %v", err)
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopePlatform,
		Action:      "test.event_two",
	}); err != nil {
		t.Fatalf("record second event: %v", err)
	}
	if err := tx.Commit(ctx); err != nil {
		t.Fatalf("commit: %v", err)
	}

	readTx, err := store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		t.Fatalf("begin read tx: %v", err)
	}
	defer func() { _ = readTx.Rollback(ctx) }()

	var prevHash1, hash1, prevHash2, hash2 string
	err = readTx.QueryRow(ctx, `SELECT prev_hash, hash FROM audit_events WHERE action = 'test.event_one'`).Scan(&prevHash1, &hash1)
	if err != nil {
		t.Fatalf("query first event: %v", err)
	}
	err = readTx.QueryRow(ctx, `SELECT prev_hash, hash FROM audit_events WHERE action = 'test.event_two'`).Scan(&prevHash2, &hash2)
	if err != nil {
		t.Fatalf("query second event: %v", err)
	}

	if prevHash1 != "genesis" {
		t.Errorf("expected the first event in a fresh table to chain from 'genesis', got %q", prevHash1)
	}
	if prevHash2 != hash1 {
		t.Errorf("expected second event's prev_hash (%q) to equal first event's hash (%q)", prevHash2, hash1)
	}
	if hash1 == hash2 {
		t.Errorf("expected distinct hashes for distinct events")
	}
}

func TestAuditEvents_AreAppendOnly(t *testing.T) {
	store := testutil.NewStore(t)
	ctx := context.Background()

	tx, err := store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		t.Fatalf("begin scoped tx: %v", err)
	}
	if err := audit.Record(ctx, tx, audit.Event{ScopeType: audit.ScopePlatform, Action: "test.immutable"}); err != nil {
		t.Fatalf("record event: %v", err)
	}
	if err := tx.Commit(ctx); err != nil {
		t.Fatalf("commit: %v", err)
	}

	updateTx, err := store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		t.Fatalf("begin update tx: %v", err)
	}
	defer func() { _ = updateTx.Rollback(ctx) }()

	_, err = updateTx.Exec(ctx, `UPDATE audit_events SET action = 'tampered' WHERE action = 'test.immutable'`)
	if err == nil {
		t.Fatal("expected UPDATE on audit_events to fail (append-only trigger), but it succeeded")
	}

	deleteTx, err := store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		t.Fatalf("begin delete tx: %v", err)
	}
	defer func() { _ = deleteTx.Rollback(ctx) }()

	_, err = deleteTx.Exec(ctx, `DELETE FROM audit_events WHERE action = 'test.immutable'`)
	if err == nil {
		t.Fatal("expected DELETE on audit_events to fail (append-only trigger), but it succeeded")
	}
}

func TestAuditEvents_HiddenWithoutTenantOrPlatformScope(t *testing.T) {
	store := testutil.NewStore(t)
	ctx := context.Background()

	tenantID := uuid.New()
	tx, err := store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		t.Fatalf("begin scoped tx: %v", err)
	}
	if err := audit.Record(ctx, tx, audit.Event{ScopeType: audit.ScopeEnterprise, ScopeID: &tenantID, Action: "test.tenant_scoped"}); err != nil {
		t.Fatalf("record event: %v", err)
	}
	if err := tx.Commit(ctx); err != nil {
		t.Fatalf("commit: %v", err)
	}

	// A plain connection with no scope GUCs set must not see the row, even
	// though it was just inserted -- proving RLS, not just the application
	// layer, is what's actually gating visibility.
	var count int
	if err := store.Pool.QueryRow(ctx, `SELECT count(*) FROM audit_events WHERE action = 'test.tenant_scoped'`).Scan(&count); err != nil {
		t.Fatalf("count without scope: %v", err)
	}
	if count != 0 {
		t.Fatalf("expected 0 rows visible without any scope GUC set (RLS should hide them), got %d", count)
	}
}

// insertTestUser creates a minimal real user row so tests can reference a
// valid actor_user_id (audit_events has a foreign key to users).
func insertTestUser(t *testing.T, store *dbpkg.Store, email string) uuid.UUID {
	t.Helper()
	var id uuid.UUID
	err := store.Pool.QueryRow(context.Background(), `
		INSERT INTO users (email, password_hash, email_verified_at)
		VALUES ($1, 'unused', now())
		RETURNING id
	`, email).Scan(&id)
	if err != nil {
		t.Fatalf("insert test user: %v", err)
	}
	return id
}
