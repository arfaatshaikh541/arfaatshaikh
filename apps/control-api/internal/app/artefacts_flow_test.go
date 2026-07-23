package app_test

import (
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"testing"
)

// TestArtefactUploadDownloadDeleteLifecycle exercises the full
// server-authorised object-storage workflow against the fake in-process
// object store (internal/app/objectstore_fake_test.go): authorise upload,
// really PUT bytes to the returned presigned URL, complete the upload
// (server independently verifies size and re-hashes the object rather than
// trusting the client), download, then delete.
func TestArtefactUploadDownloadDeleteLifecycle(t *testing.T) {
	srv, smtp, _ := testServer(t)
	base := httpTestServer{URL: srv.URL}

	owner := registerVerifyAndLogin(t, base, smtp, "artefact-owner@example.com")
	tenantID := createTenant(t, owner, "Artefact Test Tenant", "AE")

	content := []byte("fictional model weights, definitely not real")
	sum := sha256.Sum256(content)
	checksum := hex.EncodeToString(sum[:])

	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/artefacts", map[string]any{
		"purpose":        "model_artefact",
		"content_type":   "application/octet-stream",
		"content_length": len(content),
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("authorise upload: expected 201, got %d: %v", resp.StatusCode, body)
	}
	uploadResp, ok := body["upload"].(map[string]any)
	if !ok {
		t.Fatalf("expected an 'upload' object in response, got %v", body)
	}
	artefactID := str(t, uploadResp, "id")
	uploadURL, ok := body["upload_url"].(string)
	if !ok || uploadURL == "" {
		t.Fatalf("expected a non-empty upload_url, got %v", body["upload_url"])
	}

	putObject(t, uploadURL, content)

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/artefacts/"+artefactID+"/complete", map[string]string{
		"checksum_sha256": checksum,
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("complete upload: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "uploaded" {
		t.Fatalf("expected status uploaded, got %v", got)
	}
	if got, want := body["checksum_sha256"], checksum; got != want {
		t.Fatalf("expected server-verified checksum %q, got %v", want, got)
	}

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/artefacts/"+artefactID+"/download", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("request download: expected 200, got %d: %v", resp.StatusCode, body)
	}
	downloadURL, ok := body["download_url"].(string)
	if !ok || downloadURL == "" {
		t.Fatalf("expected a non-empty download_url, got %v", body["download_url"])
	}
	downloadResp, err := http.Get(downloadURL)
	if err != nil {
		t.Fatalf("download object: %v", err)
	}
	defer func() { _ = downloadResp.Body.Close() }()
	if downloadResp.StatusCode != http.StatusOK {
		t.Fatalf("download object: expected 200, got %d", downloadResp.StatusCode)
	}

	resp, body = owner.delete("/api/v1/enterprises/" + tenantID + "/artefacts/" + artefactID)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("delete artefact: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "deleted" {
		t.Fatalf("expected status deleted, got %v", got)
	}
}

// TestArtefactCompletionRejectsChecksumMismatch proves the server does not
// trust a client-declared checksum -- it hashes the actual uploaded bytes
// itself and fails closed (marking the upload 'failed') on any mismatch.
func TestArtefactCompletionRejectsChecksumMismatch(t *testing.T) {
	srv, smtp, _ := testServer(t)
	base := httpTestServer{URL: srv.URL}

	owner := registerVerifyAndLogin(t, base, smtp, "artefact-checksum@example.com")
	tenantID := createTenant(t, owner, "Artefact Checksum Test Tenant", "AE")

	content := []byte("some workload config bytes")
	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/artefacts", map[string]any{
		"purpose": "workload_artefact", "content_type": "application/json", "content_length": len(content),
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("authorise upload: expected 201, got %d: %v", resp.StatusCode, body)
	}
	uploadResp := body["upload"].(map[string]any)
	artefactID := str(t, uploadResp, "id")
	uploadURL := body["upload_url"].(string)

	putObject(t, uploadURL, content)

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/artefacts/"+artefactID+"/complete", map[string]string{
		"checksum_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
	})
	if resp.StatusCode != http.StatusUnprocessableEntity {
		t.Fatalf("complete upload with wrong checksum: expected 422, got %d: %v", resp.StatusCode, body)
	}
}
