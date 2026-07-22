package app_test

import (
	"net/http"
	"testing"

	"github.com/google/uuid"

	dbpkg "gridkeep/control-api/internal/platform/db"
)

func mustParseUUID(t *testing.T, s string) *uuid.UUID {
	t.Helper()
	id, err := uuid.Parse(s)
	if err != nil {
		t.Fatalf("parse uuid %q: %v", s, err)
	}
	return &id
}

func createTenant(t *testing.T, c *client, legalName, country string) string {
	t.Helper()
	resp, body := c.post("/api/v1/enterprises", map[string]string{"legal_name": legalName, "country": country})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create tenant: expected 201, got %d: %v", resp.StatusCode, body)
	}
	return str(t, body, "id")
}

func createOperator(t *testing.T, c *client, legalName, country string) string {
	t.Helper()
	resp, body := c.post("/api/v1/operators", map[string]string{"legal_name": legalName, "country": country})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create operator: expected 201, got %d: %v", resp.StatusCode, body)
	}
	return str(t, body, "id")
}

// TestCrossTenantIsolationDenied is the automated regression test for the
// isolation property manually verified during development: a user with no
// membership in a tenant is denied on every route scoped to it, and this
// holds independently at both the RequireEnterpriseMembership (read) and
// RequireEnterprisePermission (write) layers.
func TestCrossTenantIsolationDenied(t *testing.T) {
	srv, smtp, _ := testServer(t)
	base := httpTestServer{URL: srv.URL}

	owner := registerVerifyAndLogin(t, base, smtp, "tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Isolation Test Tenant", "AE")

	outsider := registerVerifyAndLogin(t, base, smtp, "tenant-outsider@example.com")

	resp, _ := outsider.get("/api/v1/enterprises/" + tenantID)
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("outsider GET tenant profile: expected 403, got %d", resp.StatusCode)
	}

	resp, _ = outsider.get("/api/v1/enterprises/" + tenantID + "/members")
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("outsider GET tenant members: expected 403, got %d", resp.StatusCode)
	}

	resp, _ = outsider.patch("/api/v1/enterprises/"+tenantID, map[string]string{"display_name": "Hijacked"})
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("outsider PATCH tenant settings: expected 403, got %d", resp.StatusCode)
	}

	// The owner, meanwhile, must still be able to see their own tenant.
	resp, _ = owner.get("/api/v1/enterprises/" + tenantID)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("owner GET own tenant: expected 200, got %d", resp.StatusCode)
	}
}

func TestCrossOperatorIsolationDenied(t *testing.T) {
	srv, smtp, _ := testServer(t)
	base := httpTestServer{URL: srv.URL}

	owner := registerVerifyAndLogin(t, base, smtp, "operator-owner@example.com")
	operatorID := createOperator(t, owner, "Isolation Test Operator", "DE")

	outsider := registerVerifyAndLogin(t, base, smtp, "operator-outsider@example.com")

	resp, _ := outsider.get("/api/v1/operators/" + operatorID)
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("outsider GET operator profile: expected 403, got %d", resp.StatusCode)
	}

	resp, _ = outsider.get("/api/v1/operators/" + operatorID + "/members")
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("outsider GET operator members: expected 403, got %d", resp.StatusCode)
	}
}

// TestSuspendedTenantBlocksMutationButNotOwnerRead is a regression test for a
// real bug found during manual testing: enterpriseMembershipPermission had
// an unused, unreferenced SQL parameter ($3 never appeared in the query
// text), which PostgreSQL rejects with "could not determine data type of
// parameter" -- turning every permission-gated write on a tenant into a 500
// instead of enforcing the tenant's active/suspended status. Fixed in
// internal/modules/rbac/repository.go.
func TestSuspendedTenantBlocksMutationButNotOwnerRead(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	owner := registerVerifyAndLogin(t, base, smtp, "suspend-owner@example.com")
	tenantID := createTenant(t, owner, "Suspend Test Tenant", "AE")

	ctx := t.Context()
	// enterprise_tenants now enforces Row-Level Security (see migration
	// 0011), so this direct test-setup write needs a platform_bypass
	// scoped transaction -- a plain store.Pool.Exec would silently match
	// zero rows instead of erroring.
	tx, err := store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		t.Fatalf("begin scoped tx: %v", err)
	}
	if _, err := tx.Exec(ctx, `UPDATE enterprise_tenants SET status = 'suspended' WHERE id = $1`, tenantID); err != nil {
		t.Fatalf("suspend tenant directly: %v", err)
	}
	if err := tx.Commit(ctx); err != nil {
		t.Fatalf("commit tenant suspension: %v", err)
	}

	resp, _ := owner.get("/api/v1/enterprises/" + tenantID)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("owner read of suspended tenant: expected 200, got %d", resp.StatusCode)
	}

	resp, body := owner.patch("/api/v1/enterprises/"+tenantID, map[string]string{"display_name": "Should Be Blocked"})
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("owner write to suspended tenant: expected 403 (not 500), got %d: %v", resp.StatusCode, body)
	}
}

// TestTenantAndOperatorRowLevelSecurity is a regression test for an audit
// finding: enterprise_tenants and operators had no Row-Level Security at
// all, unlike every other tenant/operator-owned table -- a raw query scoped
// to one tenant could still read every other tenant's row directly from the
// database, with nothing but the application layer standing in the way.
// This proves the database itself, independent of any application code,
// now enforces the same self-scope + platform-bypass boundary migration
// 0011 added.
func TestTenantAndOperatorRowLevelSecurity(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}
	ctx := t.Context()

	ownerA := registerVerifyAndLogin(t, base, smtp, "rls-tenant-a@example.com")
	tenantA := createTenant(t, ownerA, "RLS Tenant A", "AE")
	ownerB := registerVerifyAndLogin(t, base, smtp, "rls-tenant-b@example.com")
	tenantB := createTenant(t, ownerB, "RLS Tenant B", "AE")

	tx, err := store.BeginScoped(ctx, dbpkg.Scope{TenantID: mustParseUUID(t, tenantA)})
	if err != nil {
		t.Fatalf("begin tenant-A-scoped tx: %v", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	rows, err := tx.Query(ctx, `SELECT id FROM enterprise_tenants`)
	if err != nil {
		t.Fatalf("query enterprise_tenants scoped to tenant A: %v", err)
	}
	var seen []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			t.Fatalf("scan tenant id: %v", err)
		}
		seen = append(seen, id)
	}
	rows.Close()

	if len(seen) != 1 || seen[0] != tenantA {
		t.Fatalf("RLS leak: a transaction scoped to tenant %s could see rows %v (tenant %s must not be visible)", tenantA, seen, tenantB)
	}
}
