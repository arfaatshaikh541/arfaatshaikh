package app_test

import (
	"net/http"
	"testing"

	"gridkeep/control-api/internal/testutil"
)

// TestModelVersionDualControlApproval covers the model-registry lifecycle:
// registering a model, drafting an immutable-once-approved version,
// requesting approval, rejecting self-approval, and a genuinely different
// user approving it.
func TestModelVersionDualControlApproval(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	owner := registerVerifyAndLogin(t, base, smtp, "model-owner@example.com")
	tenantID := createTenant(t, owner, "Model Test Tenant", "AE")
	licenceID := seedModelLicence(t, store, "apache2-test", true)

	approverEmail := "model-approver@example.com"
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

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/models", map[string]any{
		"model_key": "text-embed-fictional", "name": "Fictional Text Embedding Model", "description": "",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create model: expected 201, got %d: %v", resp.StatusCode, body)
	}
	modelID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/models/"+modelID+"/versions", map[string]any{
		"licence_id":               licenceID,
		"checksum_sha256":          fakeDigest("model-version-test")[len("sha256:"):],
		"permitted_geographies":    []string{"AE", "SA"},
		"prohibited_geographies":   []string{},
		"supported_workload_types": []string{"embedding_service"},
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create draft version: expected 201, got %d: %v", resp.StatusCode, body)
	}
	versionID := str(t, body, "id")
	if got := body["status"]; got != "draft" {
		t.Fatalf("expected status draft, got %v", got)
	}

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/model-versions/"+versionID+"/request-approval", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("request approval: expected 200, got %d: %v", resp.StatusCode, body)
	}

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/model-versions/"+versionID+"/approve", nil)
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("self-approve: expected 403, got %d: %v", resp.StatusCode, body)
	}

	resp, body = approver.post("/api/v1/enterprises/"+tenantID+"/model-versions/"+versionID+"/approve", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("approve by different user: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "approved" {
		t.Fatalf("expected status approved, got %v", got)
	}

	// Retire, then confirm it cannot be retired twice.
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/model-versions/"+versionID+"/retire", map[string]string{"reason": "superseded"})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("retire version: expected 200, got %d: %v", resp.StatusCode, body)
	}
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/model-versions/"+versionID+"/retire", map[string]string{"reason": "superseded"})
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("retire already-retired version: expected 409, got %d: %v", resp.StatusCode, body)
	}
}
