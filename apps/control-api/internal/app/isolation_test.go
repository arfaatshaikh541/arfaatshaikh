package app_test

import (
	"net/http"
	"testing"
)

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
	if _, err := store.Pool.Exec(ctx, `UPDATE enterprise_tenants SET status = 'suspended' WHERE id = $1`, tenantID); err != nil {
		t.Fatalf("suspend tenant directly: %v", err)
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
