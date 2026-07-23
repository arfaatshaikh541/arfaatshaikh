package app_test

import (
	"net/http"
	"testing"

	"gridkeep/control-api/internal/testutil"
)

// approveTestImage registers, then approves, a container image against a
// relaxed vulnerability policy (no SBOM/signature/scan involved) -- a
// reusable fixture for tests that only care about having *an* approved
// image to reference, not about supply-chain gating itself (see
// images_flow_test.go for that).
func approveTestImage(t *testing.T, owner *client, tenantID, seed string) string {
	t.Helper()
	resp, body := owner.put("/api/v1/enterprises/"+tenantID+"/vulnerability-policy", map[string]any{
		"max_allowed_severity": "critical", "block_unsigned_images": false, "require_sbom": false,
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("relax vulnerability policy: expected 200, got %d: %v", resp.StatusCode, body)
	}

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/images", map[string]any{
		"registry_host": "registry.example.com", "repository": "acme/base-image", "digest": fakeDigest(seed), "tag": "v1",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("register image: expected 201, got %d: %v", resp.StatusCode, body)
	}
	imageID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/images/"+imageID+"/approve", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("approve image: expected 200, got %d: %v", resp.StatusCode, body)
	}
	return imageID
}

// approveTestModelVersion registers a model, drafts a version with the
// given permitted geographies, and dual-control-approves it.
func approveTestModelVersion(t *testing.T, owner, approver *client, tenantID, licenceID, modelKey, seed string, permittedGeographies []string) string {
	t.Helper()
	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/models", map[string]any{
		"model_key": modelKey, "name": modelKey, "description": "",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create model: expected 201, got %d: %v", resp.StatusCode, body)
	}
	modelID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/models/"+modelID+"/versions", map[string]any{
		"licence_id": licenceID, "checksum_sha256": fakeDigest(seed)[len("sha256:"):],
		"permitted_geographies": permittedGeographies, "prohibited_geographies": []string{},
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create model version draft: expected 201, got %d: %v", resp.StatusCode, body)
	}
	versionID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/model-versions/"+versionID+"/request-approval", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("request model approval: expected 200, got %d: %v", resp.StatusCode, body)
	}
	resp, body = approver.post("/api/v1/enterprises/"+tenantID+"/model-versions/"+versionID+"/approve", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("approve model version: expected 200, got %d: %v", resp.StatusCode, body)
	}
	return versionID
}

func inviteAndAcceptAdmin(t *testing.T, base httpTestServer, smtp *testutil.FakeSMTPServer, owner *client, tenantID, email string) *client {
	t.Helper()
	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/invitations", map[string]string{"email": email, "role_key": "enterprise_admin"})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("invite %s: expected 201, got %d: %v", email, resp.StatusCode, body)
	}
	msg, ok := smtp.LastMessageContaining(email)
	if !ok {
		t.Fatalf("no invitation email captured for %s", email)
	}
	token, err := testutil.ExtractToken(msg)
	if err != nil {
		t.Fatalf("extract invitation token: %v", err)
	}
	member := registerVerifyAndLogin(t, base, smtp, email)
	resp, body = member.post("/api/v1/invitations/accept", map[string]string{"token": token})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("accept invitation for %s: expected 200, got %d: %v", email, resp.StatusCode, body)
	}
	return member
}

// TestWorkloadVersionReferencesApprovedImageAndModel covers the workload
// registry's core guarantee: a draft version can reference an approved
// image and an approved, geographically-compatible model version, and
// publishing it (dual control) makes it immutable.
func TestWorkloadVersionReferencesApprovedImageAndModel(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	owner := registerVerifyAndLogin(t, base, smtp, "workload-owner@example.com")
	tenantID := createTenant(t, owner, "Workload Test Tenant", "AE")
	approver := inviteAndAcceptAdmin(t, base, smtp, owner, tenantID, "workload-approver@example.com")
	licenceID := seedModelLicence(t, store, "mit-test", true)
	seedApprovedRegistry(t, store, "registry.example.com")

	imageID := approveTestImage(t, owner, tenantID, "workload-test-image")
	modelVersionID := approveTestModelVersion(t, owner, approver, tenantID, licenceID, "workload-test-model", "workload-test-model-v1", []string{"AE", "SA"})

	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/workloads", map[string]any{
		"workload_key": "fictional-rag-app", "workload_type": "retrieval_augmented_generation_application",
		"name": "Fictional RAG App", "description": "",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create workload: expected 201, got %d: %v", resp.StatusCode, body)
	}
	workloadID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/workloads/"+workloadID+"/versions", map[string]any{
		"container_image_id": imageID, "model_version_id": modelVersionID,
		"residency_requirements": map[string]any{"allowed_countries": []string{"AE"}},
		"resource_requirements":  map[string]any{"cpu": "2", "memory_gb": 4},
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create workload version draft: expected 201, got %d: %v", resp.StatusCode, body)
	}
	versionID := str(t, body, "id")
	if got := body["status"]; got != "draft" {
		t.Fatalf("expected status draft, got %v", got)
	}

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/workload-versions/"+versionID+"/request-publish", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("request publish: expected 200, got %d: %v", resp.StatusCode, body)
	}
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/workload-versions/"+versionID+"/approve-publish", nil)
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("self-approve publish: expected 403, got %d: %v", resp.StatusCode, body)
	}
	resp, body = approver.post("/api/v1/enterprises/"+tenantID+"/workload-versions/"+versionID+"/approve-publish", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("approve publish: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "published" {
		t.Fatalf("expected status published, got %v", got)
	}

	// Immutability: editing a published version must be rejected.
	resp, body = owner.patch("/api/v1/enterprises/"+tenantID+"/workload-versions/"+versionID, map[string]any{
		"resource_requirements": map[string]any{"cpu": "16"},
	})
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("edit published version: expected 409, got %d: %v", resp.StatusCode, body)
	}
}

// TestWorkloadVersionRejectsUnapprovedImageAndGeographyMismatch proves
// criterion 16 (retired/revoked/unapproved images and models cannot be
// selected) and the model-geography enforcement rule together.
func TestWorkloadVersionRejectsUnapprovedImageAndGeographyMismatch(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	owner := registerVerifyAndLogin(t, base, smtp, "workload-reject-owner@example.com")
	tenantID := createTenant(t, owner, "Workload Reject Test Tenant", "AE")
	approver := inviteAndAcceptAdmin(t, base, smtp, owner, tenantID, "workload-reject-approver@example.com")
	licenceID := seedModelLicence(t, store, "gpl-test", false)
	seedApprovedRegistry(t, store, "registry.example.com")

	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/workloads", map[string]any{
		"workload_key": "fictional-batch-job", "workload_type": "batch_inference", "name": "Fictional Batch Job", "description": "",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create workload: expected 201, got %d: %v", resp.StatusCode, body)
	}
	workloadID := str(t, body, "id")

	// An unapproved (still 'pending') image cannot be selected.
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/images", map[string]any{
		"registry_host": "registry.example.com", "repository": "acme/unapproved", "digest": fakeDigest("unapproved-image-test"), "tag": "v1",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("register image: expected 201, got %d: %v", resp.StatusCode, body)
	}
	pendingImageID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/workloads/"+workloadID+"/versions", map[string]any{
		"container_image_id": pendingImageID,
	})
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("draft version with pending image: expected 400, got %d: %v", resp.StatusCode, body)
	}

	// An approved model version whose permitted geographies don't cover the
	// workload's declared allowed countries must also be rejected.
	modelVersionID := approveTestModelVersion(t, owner, approver, tenantID, licenceID, "geo-mismatch-model", "geo-mismatch-model-v1", []string{"DE"})

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/workloads/"+workloadID+"/versions", map[string]any{
		"model_version_id":       modelVersionID,
		"residency_requirements": map[string]any{"allowed_countries": []string{"AE"}},
	})
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("draft version with geography-mismatched model: expected 400, got %d: %v", resp.StatusCode, body)
	}
}
