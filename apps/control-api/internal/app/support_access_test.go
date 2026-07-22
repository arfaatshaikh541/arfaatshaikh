package app_test

import (
	"net/http"
	"testing"
)

// TestSupportAccessDualControl is the automated version of the manual
// verification performed during development: a platform support engineer
// cannot self-approve their own support-access request (dual control,
// enforced by the support_access_grants_no_self_approval CHECK constraint
// and re-validated at the service layer), cannot access the tenant before
// approval, and gains access -- with an audit event recorded -- only once a
// *different* platform user approves the grant.
func TestSupportAccessDualControl(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	owner := registerVerifyAndLogin(t, base, smtp, "support-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Support Access Test Tenant", "AE")

	supportEngineer := registerVerifyAndLogin(t, base, smtp, "support-engineer@example.com")
	grantPlatformRole(t, store, "support-engineer@example.com", "platform_support_engineer")

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "platform-admin-2@example.com")
	grantPlatformRole(t, store, "platform-admin-2@example.com", "platform_super_administrator")

	// No access before any grant exists.
	resp, _ := supportEngineer.get("/api/v1/enterprises/" + tenantID)
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("support engineer before grant: expected 403, got %d", resp.StatusCode)
	}

	resp, body := supportEngineer.post("/api/v1/platform/support-access-grants", map[string]any{
		"scope_type": "enterprise",
		"scope_id":   tenantID,
		"reason":     "Customer escalation INC-TEST-1",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("request support access grant: expected 201, got %d: %v", resp.StatusCode, body)
	}
	grantID := str(t, body, "id")

	// Self-approval must fail (dual control).
	resp, _ = supportEngineer.post("/api/v1/platform/support-access-grants/"+grantID+"/approve", nil)
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("self-approval: expected 409 conflict, got %d", resp.StatusCode)
	}

	// Still no access -- not yet approved.
	resp, _ = supportEngineer.get("/api/v1/enterprises/" + tenantID)
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("support engineer before approval: expected 403, got %d", resp.StatusCode)
	}

	// A different platform user approves it.
	resp, _ = platformAdmin.post("/api/v1/platform/support-access-grants/"+grantID+"/approve", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("approve by different admin: expected 200, got %d", resp.StatusCode)
	}

	// Now access succeeds.
	resp, _ = supportEngineer.get("/api/v1/enterprises/" + tenantID)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("support engineer after approval: expected 200, got %d", resp.StatusCode)
	}

	// And the tenant owner can see the support access was audited.
	events := owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/audit")
	found := false
	for _, e := range events {
		if e["action"] == "support_access.request_served" {
			found = true
			break
		}
	}
	if !found {
		t.Fatalf("expected a support_access.request_served audit event, got %v", events)
	}
}
