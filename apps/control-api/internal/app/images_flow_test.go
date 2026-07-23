package app_test

import (
	"net/http"
	"testing"
	"time"

	"gridkeep/control-api/internal/testutil"
)

// TestImageRegistrationRequiresApprovedRegistry proves the fail-closed
// registry allowlist: an image at a registry host that has never been
// platform-approved is rejected before it can even become a "pending"
// row, and succeeds once (and only once) that host is approved.
func TestImageRegistrationRequiresApprovedRegistry(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	owner := registerVerifyAndLogin(t, base, smtp, "image-owner@example.com")
	tenantID := createTenant(t, owner, "Image Test Tenant", "AE")

	digest := fakeDigest("image-registration-test")
	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/images", map[string]any{
		"registry_host": "unapproved.example.com",
		"repository":    "acme/inference-api",
		"digest":        digest,
		"tag":           "v1",
	})
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("register image at unapproved registry: expected 400, got %d: %v", resp.StatusCode, body)
	}

	seedApprovedRegistry(t, store, "registry.example.com")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/images", map[string]any{
		"registry_host": "registry.example.com",
		"repository":    "acme/inference-api",
		"digest":        digest,
		"tag":           "v1",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("register image at approved registry: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "pending" {
		t.Fatalf("expected status pending, got %v", got)
	}
}

// TestImageApprovalBlockedByVulnerabilityPolicyAndException covers the
// vulnerability-policy gate end to end: a critical finding blocks approval
// (fail closed), and the image only becomes approvable once a genuinely
// different user grants a dual-control exception covering that finding.
func TestImageApprovalBlockedByVulnerabilityPolicyAndException(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	owner := registerVerifyAndLogin(t, base, smtp, "vuln-owner@example.com")
	tenantID := createTenant(t, owner, "Vulnerability Test Tenant", "AE")
	seedApprovedRegistry(t, store, "registry.example.com")

	approverEmail := "vuln-approver@example.com"
	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/invitations", map[string]string{
		"email": approverEmail, "role_key": "enterprise_admin",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("invite approver: expected 201, got %d: %v", resp.StatusCode, body)
	}
	msg, ok := smtp.LastMessageContaining(approverEmail)
	if !ok {
		t.Fatalf("no invitation email captured for %s", approverEmail)
	}
	token, err := testutil.ExtractToken(msg)
	if err != nil {
		t.Fatalf("extract invitation token: %v", err)
	}
	approver := registerVerifyAndLogin(t, base, smtp, approverEmail)
	resp, body = approver.post("/api/v1/invitations/accept", map[string]string{"token": token})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("accept invitation: expected 200, got %d: %v", resp.StatusCode, body)
	}

	// Relax the policy to isolate the severity check from SBOM/signature
	// requirements, which are covered by their own tests.
	resp, body = owner.put("/api/v1/enterprises/"+tenantID+"/vulnerability-policy", map[string]any{
		"max_allowed_severity": "medium", "block_unsigned_images": false, "require_sbom": false,
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("update vulnerability policy: expected 200, got %d: %v", resp.StatusCode, body)
	}

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/images", map[string]any{
		"registry_host": "registry.example.com",
		"repository":    "acme/rag-app",
		"digest":        fakeDigest("vuln-policy-test"),
		"tag":           "v1",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("register image: expected 201, got %d: %v", resp.StatusCode, body)
	}
	imageID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/images/"+imageID+"/vulnerability-scans", map[string]any{
		"scanner":    "fake-scanner",
		"scanned_at": time.Now().Format(time.RFC3339),
		"findings": []map[string]any{
			{"cve_id": "CVE-2026-0001", "severity": "critical", "package_name": "libfake", "package_version": "1.0.0"},
		},
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("ingest vulnerability scan: expected 201, got %d: %v", resp.StatusCode, body)
	}
	findingsRaw, ok := body["findings"].([]any)
	if !ok || len(findingsRaw) != 1 {
		t.Fatalf("expected exactly 1 finding, got %v", body["findings"])
	}
	findingID := str(t, findingsRaw[0].(map[string]any), "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/images/"+imageID+"/approve", nil)
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("approve image with unaddressed critical finding: expected 409, got %d: %v", resp.StatusCode, body)
	}

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/images/"+imageID+"/vulnerability-exceptions", map[string]any{
		"finding_id": findingID,
		"reason":     "Vendor-confirmed false positive, tracked in INC-1234",
		"expires_at": time.Now().Add(24 * time.Hour).Format(time.RFC3339),
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("request exception: expected 201, got %d: %v", resp.StatusCode, body)
	}
	exceptionID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/vulnerability-exceptions/"+exceptionID+"/approve", nil)
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("self-approve exception: expected 403, got %d: %v", resp.StatusCode, body)
	}

	resp, body = approver.post("/api/v1/enterprises/"+tenantID+"/vulnerability-exceptions/"+exceptionID+"/approve", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("approve exception by different user: expected 200, got %d: %v", resp.StatusCode, body)
	}

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/images/"+imageID+"/approve", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("approve image after exception granted: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "approved" {
		t.Fatalf("expected status approved, got %v", got)
	}
}
