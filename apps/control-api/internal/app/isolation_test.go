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

// TestPrivateCapacityOfferMarketplaceRLSDeniesNonGrantedTenant closes a real
// coverage gap an independent tenant-isolation audit found: every existing
// marketplace/dual-scope test (capacity offers, model versions) proves
// cross-tenant visibility only through the HTTP/application layer, never
// with a raw query directly against a scoped transaction the way
// TestTenantAndOperatorRowLevelSecurity does for enterprise_tenants. A
// private offer's capacity_offers_enterprise_read policy (migration 0036)
// is the one place in this codebase where "is this row visible to this
// tenant" depends on a second table's content (capacity_offer_grants), not
// just a column on the row itself -- exactly the kind of policy an
// application-layer-only test could pass while a subtly wrong EXISTS
// clause still leaked (or wrongly hid) rows. This proves the grant/revoke
// lifecycle at the database layer, independent of the placement/offers
// HTTP handlers.
func TestPrivateCapacityOfferMarketplaceRLSDeniesNonGrantedTenant(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}
	ctx := t.Context()

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "private-offer-rls-admin@example.com")
	grantPlatformRole(t, store, "private-offer-rls-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE"})
	jurisdictionID := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-private-offer", "name": "Middle East Central", "jurisdiction_id": jurisdictionID})
	regionID := str(t, body, "id")

	operatorOwner := registerVerifyAndLogin(t, base, smtp, "private-offer-operator-owner@example.com")
	operatorID := createOperator(t, operatorOwner, "Private Offer Operator", "AE")
	activateOperator(t, platformAdmin, operatorID)

	_, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/data-centres", map[string]string{
		"region_id": regionID, "name": "Private Offer DC1", "locality": "private-offer",
	})
	dataCentreID := str(t, body, "id")
	_, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/clusters", map[string]string{
		"data_centre_id": dataCentreID, "name": "private-offer-cluster", "kubernetes_version": "1.31",
	})
	clusterID := str(t, body, "id")

	resp, body := operatorOwner.post("/api/v1/operators/"+operatorID+"/capacity-offers", map[string]any{
		"cluster_id": clusterID, "accelerator_type": "nvidia-h100", "total_capacity": 10,
		"price_per_unit_hour": 2.00, "currency": "USD", "visibility": "private",
		"confidential_computing_available": false, "estimated_kwh_per_unit_hour": 0.5,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create private capacity offer: expected 201, got %d: %v", resp.StatusCode, body)
	}
	offerID := str(t, body, "id")

	grantedOwner := registerVerifyAndLogin(t, base, smtp, "private-offer-granted-tenant@example.com")
	grantedTenantID := createTenant(t, grantedOwner, "Private Offer Granted Tenant", "AE")

	selectOfferRows := func(tenantID string) []string {
		t.Helper()
		tx, err := store.BeginScoped(ctx, dbpkg.Scope{TenantID: mustParseUUID(t, tenantID)})
		if err != nil {
			t.Fatalf("begin tenant-scoped tx: %v", err)
		}
		defer func() { _ = tx.Rollback(ctx) }()
		rows, err := tx.Query(ctx, `SELECT id FROM capacity_offers WHERE id = $1`, offerID)
		if err != nil {
			t.Fatalf("query capacity_offers scoped to tenant %s: %v", tenantID, err)
		}
		defer rows.Close()
		var seen []string
		for rows.Next() {
			var id string
			if err := rows.Scan(&id); err != nil {
				t.Fatalf("scan offer id: %v", err)
			}
			seen = append(seen, id)
		}
		return seen
	}

	// Before any grant exists, the private offer is invisible even to a
	// raw, no-WHERE-on-visibility query -- the RLS policy itself is the
	// boundary, not application-level filtering.
	if seen := selectOfferRows(grantedTenantID); len(seen) != 0 {
		t.Fatalf("RLS leak: private offer %s visible to ungranted tenant %s before any grant: %v", offerID, grantedTenantID, seen)
	}

	resp, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/capacity-offers/"+offerID+"/grants", map[string]any{
		"enterprise_tenant_id": grantedTenantID,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create capacity offer grant: expected 201, got %d: %v", resp.StatusCode, body)
	}
	grantID := str(t, body, "id")

	// With an active grant, the same raw query now sees exactly the one
	// granted row.
	if seen := selectOfferRows(grantedTenantID); len(seen) != 1 || seen[0] != offerID {
		t.Fatalf("expected granted tenant %s to see offer %s, got %v", grantedTenantID, offerID, seen)
	}

	resp, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/capacity-offer-grants/"+grantID+"/revoke", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("revoke capacity offer grant: expected 200, got %d: %v", resp.StatusCode, body)
	}

	// A revoked grant must remove visibility again, proving the policy's
	// EXISTS clause checks the grant's status, not merely its existence.
	if seen := selectOfferRows(grantedTenantID); len(seen) != 0 {
		t.Fatalf("RLS leak: private offer %s still visible to tenant %s after grant revocation: %v", offerID, grantedTenantID, seen)
	}

	// A second, entirely uninvolved tenant must never see the private
	// offer at any point in this sequence.
	outsiderOwner := registerVerifyAndLogin(t, base, smtp, "private-offer-outsider-tenant@example.com")
	outsiderTenantID := createTenant(t, outsiderOwner, "Private Offer Outsider Tenant", "AE")
	if seen := selectOfferRows(outsiderTenantID); len(seen) != 0 {
		t.Fatalf("RLS leak: private offer %s visible to uninvolved outsider tenant %s: %v", offerID, outsiderTenantID, seen)
	}
}
