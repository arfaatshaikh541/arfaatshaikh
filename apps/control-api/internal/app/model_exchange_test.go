package app_test

import (
	"net/http"
	"testing"
)

func containsVersionID(rows []map[string]any, id string) bool {
	for _, row := range rows {
		if row["id"] == id {
			return true
		}
	}
	return false
}

// TestAIModelExchangeMarketplaceGrantsEligibilityAndLicensing covers
// Milestone 13's core guarantees: publishing an approved model version makes
// it visible to every tenant; leaving it private keeps it hidden until an
// access grant exists, at which point the grantee sees the owner's
// per-tenant overridden price rather than the public base price; a granted
// cross-tenant model version can be selected by the grantee's workloads
// (subject to the same geography/language checks an own-tenant selection
// already enforced pre-Milestone-13); revoking the grant removes both
// marketplace visibility and workload-selection eligibility; and a licence
// that forbids commercial use blocks both publishing and granting, even
// though the version itself is fully approved.
func TestAIModelExchangeMarketplaceGrantsEligibilityAndLicensing(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	ownerA := registerVerifyAndLogin(t, base, smtp, "exchange-owner-a@example.com")
	tenantA := createTenant(t, ownerA, "Exchange Tenant A", "AE")
	approverA := inviteAndAcceptAdmin(t, base, smtp, ownerA, tenantA, "exchange-approver-a@example.com")

	ownerB := registerVerifyAndLogin(t, base, smtp, "exchange-owner-b@example.com")
	tenantB := createTenant(t, ownerB, "Exchange Tenant B", "AE")

	openLicenceID := seedModelLicence(t, store, "exchange-open-licence", true)
	closedLicenceID := seedModelLicence(t, store, "exchange-closed-licence", false)

	createApprovedVersion := func(modelKey, seed, licenceID string, permittedGeographies, supportedLanguages []string) string {
		resp, body := ownerA.post("/api/v1/enterprises/"+tenantA+"/models", map[string]any{
			"model_key": modelKey, "name": modelKey, "description": "",
		})
		if resp.StatusCode != http.StatusCreated {
			t.Fatalf("create model %s: expected 201, got %d: %v", modelKey, resp.StatusCode, body)
		}
		modelID := str(t, body, "id")

		resp, body = ownerA.post("/api/v1/enterprises/"+tenantA+"/models/"+modelID+"/versions", map[string]any{
			"licence_id": licenceID, "checksum_sha256": fakeDigest(seed)[len("sha256:"):],
			"permitted_geographies": permittedGeographies, "prohibited_geographies": []string{},
			"supported_languages": supportedLanguages,
		})
		if resp.StatusCode != http.StatusCreated {
			t.Fatalf("create version for %s: expected 201, got %d: %v", modelKey, resp.StatusCode, body)
		}
		versionID := str(t, body, "id")

		resp, body = ownerA.post("/api/v1/enterprises/"+tenantA+"/model-versions/"+versionID+"/request-approval", nil)
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("request approval for %s: expected 200, got %d: %v", modelKey, resp.StatusCode, body)
		}
		resp, body = approverA.post("/api/v1/enterprises/"+tenantA+"/model-versions/"+versionID+"/approve", nil)
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("approve %s: expected 200, got %d: %v", modelKey, resp.StatusCode, body)
		}
		return versionID
	}

	// --- Public listing: visible to any tenant, no grant needed. ---
	publicVersionID := createApprovedVersion("exchange-public-model", "exchange-public-model-v1", openLicenceID, []string{"AE"}, []string{"en"})

	resp, body := ownerA.post("/api/v1/enterprises/"+tenantA+"/model-versions/"+publicVersionID+"/publish", map[string]any{
		"price_per_unit": 2.5, "pricing_unit": "per_1k_tokens", "currency": "USD",
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("publish public version: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["visibility"]; got != "public" {
		t.Fatalf("expected visibility public, got %v", got)
	}

	marketplace := ownerB.getArray(t, "/api/v1/enterprises/"+tenantB+"/model-marketplace/versions")
	if !containsVersionID(marketplace, publicVersionID) {
		t.Fatalf("expected public version %s visible in tenant B's marketplace", publicVersionID)
	}

	// --- Private listing: hidden until a per-tenant access grant exists. ---
	privateVersionID := createApprovedVersion("exchange-private-model", "exchange-private-model-v1", openLicenceID, []string{"AE"}, []string{"en"})

	marketplaceBeforeGrant := ownerB.getArray(t, "/api/v1/enterprises/"+tenantB+"/model-marketplace/versions")
	if containsVersionID(marketplaceBeforeGrant, privateVersionID) {
		t.Fatalf("private version %s must not be visible before a grant exists", privateVersionID)
	}

	resp, body = ownerA.post("/api/v1/enterprises/"+tenantA+"/model-versions/"+privateVersionID+"/access-grants", map[string]any{
		"grantee_tenant_id": tenantB, "price_per_unit_override": 1.25,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create access grant: expected 201, got %d: %v", resp.StatusCode, body)
	}
	grantID := str(t, body, "id")

	marketplaceAfterGrant := ownerB.getArray(t, "/api/v1/enterprises/"+tenantB+"/model-marketplace/versions")
	if !containsVersionID(marketplaceAfterGrant, privateVersionID) {
		t.Fatalf("expected granted private version %s visible in tenant B's marketplace", privateVersionID)
	}

	resp, body = ownerB.get("/api/v1/enterprises/" + tenantB + "/model-marketplace/versions/" + privateVersionID)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("get marketplace version: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got, ok := body["price_per_unit"].(float64); !ok || got != 1.25 {
		t.Fatalf("expected tenant B's overridden price 1.25, got %v", body["price_per_unit"])
	}

	// --- Cross-tenant workload selection succeeds once granted. ---
	resp, body = ownerB.post("/api/v1/enterprises/"+tenantB+"/workloads", map[string]any{
		"workload_key": "exchange-consumer-app", "workload_type": "retrieval_augmented_generation_application",
		"name": "Exchange Consumer App", "description": "",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create workload: expected 201, got %d: %v", resp.StatusCode, body)
	}
	workloadID := str(t, body, "id")

	resp, body = ownerB.post("/api/v1/enterprises/"+tenantB+"/workloads/"+workloadID+"/versions", map[string]any{
		"model_version_id":       privateVersionID,
		"residency_requirements": map[string]any{"allowed_countries": []string{"AE"}, "required_languages": []string{"en"}},
		"resource_requirements":  map[string]any{"cpu": "2", "memory_gb": 4},
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create workload version selecting granted cross-tenant model: expected 201, got %d: %v", resp.StatusCode, body)
	}

	// Negative: a required language the model doesn't declare support for is rejected.
	resp, body = ownerB.post("/api/v1/enterprises/"+tenantB+"/workloads/"+workloadID+"/versions", map[string]any{
		"model_version_id":       privateVersionID,
		"residency_requirements": map[string]any{"required_languages": []string{"fr"}},
		"resource_requirements":  map[string]any{"cpu": "2", "memory_gb": 4},
	})
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected language mismatch to be rejected with 400, got %d: %v", resp.StatusCode, body)
	}

	// --- Revoking the grant removes both marketplace visibility and workload eligibility. ---
	resp, _ = ownerA.post("/api/v1/enterprises/"+tenantA+"/model-access-grants/"+grantID+"/revoke", nil)
	if resp.StatusCode != http.StatusNoContent {
		t.Fatalf("revoke grant: expected 204, got %d", resp.StatusCode)
	}

	marketplaceAfterRevoke := ownerB.getArray(t, "/api/v1/enterprises/"+tenantB+"/model-marketplace/versions")
	if containsVersionID(marketplaceAfterRevoke, privateVersionID) {
		t.Fatalf("revoked private version %s must no longer be visible", privateVersionID)
	}

	resp, body = ownerB.post("/api/v1/enterprises/"+tenantB+"/workloads/"+workloadID+"/versions", map[string]any{
		"model_version_id":       privateVersionID,
		"residency_requirements": map[string]any{},
		"resource_requirements":  map[string]any{"cpu": "2", "memory_gb": 4},
	})
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected revoked cross-tenant selection to be rejected with 400, got %d: %v", resp.StatusCode, body)
	}

	// --- Licence enforcement: forbids-commercial-use blocks both publish and grant. ---
	closedVersionID := createApprovedVersion("exchange-closed-model", "exchange-closed-model-v1", closedLicenceID, []string{"AE"}, []string{"en"})

	resp, body = ownerA.post("/api/v1/enterprises/"+tenantA+"/model-versions/"+closedVersionID+"/publish", map[string]any{
		"price_per_unit": 1.0, "pricing_unit": "per_1k_tokens", "currency": "USD",
	})
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("expected licence-forbids-commercial-use to block publish with 403, got %d: %v", resp.StatusCode, body)
	}
	resp, body = ownerA.post("/api/v1/enterprises/"+tenantA+"/model-versions/"+closedVersionID+"/access-grants", map[string]any{
		"grantee_tenant_id": tenantB,
	})
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("expected licence-forbids-commercial-use to block grant with 403, got %d: %v", resp.StatusCode, body)
	}

	// --- Provider onboarding under platform.model_catalogue.manage. ---
	platformAdminEmail := "exchange-platform-admin@example.com"
	platformAdmin := registerVerifyAndLogin(t, base, smtp, platformAdminEmail)
	grantPlatformRole(t, store, platformAdminEmail, "platform_super_administrator")

	resp, body = platformAdmin.post("/api/v1/model-providers", map[string]any{
		"key": "exchange-test-provider", "name": "Exchange Test Provider", "website": "https://example.com",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("onboard provider: expected 201, got %d: %v", resp.StatusCode, body)
	}
	providerID := str(t, body, "id")
	if got := body["status"]; got != "active" {
		t.Fatalf("expected new provider status active, got %v", got)
	}

	resp, _ = platformAdmin.post("/api/v1/model-providers/"+providerID+"/suspend", nil)
	if resp.StatusCode != http.StatusNoContent {
		t.Fatalf("suspend provider: expected 204, got %d", resp.StatusCode)
	}
	resp, body = platformAdmin.post("/api/v1/model-providers/"+providerID+"/suspend", nil)
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("suspend already-suspended provider: expected 409, got %d: %v", resp.StatusCode, body)
	}

	resp, body = ownerA.post("/api/v1/model-providers", map[string]any{
		"key": "exchange-forbidden-provider", "name": "Forbidden Provider",
	})
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("expected non-platform-admin provider onboarding to be forbidden, got %d: %v", resp.StatusCode, body)
	}
}
