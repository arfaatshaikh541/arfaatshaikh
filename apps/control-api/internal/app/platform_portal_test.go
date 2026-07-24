package app_test

import (
	"net/http"
	"testing"
)

// TestPlatformRolesExposedOnMeAndTopLevelProviderList covers two small
// Milestone 15 additions the platform portal frontend needs: /auth/me
// reports the caller's own active platform role keys (read-only UI
// convenience -- every platform.* route still independently re-checks the
// permission on every request), and the model-providers catalogue has a
// top-level GET any authenticated user can read, not just a platform admin,
// mirroring registry.MountTopLevel's jurisdictions/regions read pattern.
func TestPlatformRolesExposedOnMeAndTopLevelProviderList(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	ordinaryUser := registerVerifyAndLogin(t, base, smtp, "platform-portal-ordinary@example.com")
	resp, body := ordinaryUser.get("/api/v1/auth/me")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("/auth/me: expected 200, got %d", resp.StatusCode)
	}
	roles, ok := body["platform_roles"].([]any)
	if !ok {
		t.Fatalf("expected platform_roles array in /auth/me response, got %v", body)
	}
	if len(roles) != 0 {
		t.Fatalf("expected no platform roles for an ordinary user, got %v", roles)
	}

	// An ordinary, non-platform-admin user can still read the model provider
	// catalogue (it is reference data, not a write) via the new top-level GET.
	resp, _ = ordinaryUser.get("/api/v1/model-providers")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("GET /api/v1/model-providers as ordinary user: expected 200, got %d", resp.StatusCode)
	}

	platformAdminEmail := "platform-portal-admin@example.com"
	platformAdmin := registerVerifyAndLogin(t, base, smtp, platformAdminEmail)
	grantPlatformRole(t, store, platformAdminEmail, "platform_super_administrator")

	resp, body = platformAdmin.get("/api/v1/auth/me")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("/auth/me for platform admin: expected 200, got %d", resp.StatusCode)
	}
	roles, ok = body["platform_roles"].([]any)
	if !ok || len(roles) != 1 || roles[0] != "platform_super_administrator" {
		t.Fatalf("expected platform_roles == [\"platform_super_administrator\"], got %v", body["platform_roles"])
	}

	// The write endpoints under the same path remain platform-permission
	// gated -- an ordinary user is still forbidden from onboarding a provider.
	resp, body = ordinaryUser.post("/api/v1/model-providers", map[string]any{
		"key": "portal-test-forbidden-provider", "name": "Forbidden",
	})
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("expected non-admin provider onboarding to be forbidden, got %d: %v", resp.StatusCode, body)
	}
}
