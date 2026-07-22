package app_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"testing"
)

// TestCSRFProtection_RejectsRequestsWithoutToken verifies the double-submit
// CSRF cookie is actually enforced: a state-changing request that omits the
// X-CSRF-Token header is rejected even though the session/cookie jar is
// otherwise fully valid.
func TestCSRFProtection_RejectsRequestsWithoutToken(t *testing.T) {
	srv, _, _ := testServer(t)
	c := newClient(t, srv.URL)

	payload, _ := json.Marshal(map[string]string{"email": "csrf-test@example.com", "password": testPassword})
	req, err := http.NewRequest(http.MethodPost, srv.URL+"/api/v1/auth/register", bytes.NewReader(payload))
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	// Deliberately do NOT set X-CSRF-Token.

	resp, err := c.http.Do(req)
	if err != nil {
		t.Fatalf("do request: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("expected 403 for a mutating request without a CSRF token, got %d", resp.StatusCode)
	}
}

func TestCSRFProtection_AllowsGETWithoutToken(t *testing.T) {
	srv, _, _ := testServer(t)
	c := newClient(t, srv.URL)

	resp, _ := c.get("/healthz")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected GET /healthz to succeed without a CSRF token, got %d", resp.StatusCode)
	}
}
