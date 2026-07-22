package app_test

import (
	"net/http"
	"testing"

	"gridkeep/control-api/internal/testutil"
)

func TestPasswordResetFlow_RevokesExistingSessions(t *testing.T) {
	srv, smtp, _ := testServer(t)
	base := httpTestServer{URL: srv.URL}
	email := "reset-flow@example.com"

	c := registerVerifyAndLogin(t, base, smtp, email)

	// The pre-reset session works.
	resp, _ := c.get("/api/v1/auth/me")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("session before reset: expected 200, got %d", resp.StatusCode)
	}

	resp, _ = c.post("/api/v1/auth/password-reset/request", map[string]string{"email": email})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("password-reset/request: expected 200, got %d", resp.StatusCode)
	}

	msg, ok := smtp.LastMessageContaining("reset-password")
	if !ok {
		t.Fatalf("no password reset email captured")
	}
	token, err := testutil.ExtractToken(msg)
	if err != nil {
		t.Fatalf("extract reset token: %v", err)
	}

	newPassword := "ANewCorrectHorseBattery2"
	resp, _ = c.post("/api/v1/auth/password-reset/confirm", map[string]string{"token": token, "new_password": newPassword})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("password-reset/confirm: expected 200, got %d", resp.StatusCode)
	}

	// The OLD session must now be dead -- resetting a password revokes every
	// existing session, so a stolen session cookie doesn't survive a reset.
	resp, _ = c.get("/api/v1/auth/me")
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("old session after reset: expected 401 (revoked), got %d", resp.StatusCode)
	}

	// The new password logs in fine on a fresh session.
	fresh := newClient(t, srv.URL)
	resp, body := fresh.post("/api/v1/auth/login", map[string]string{"email": email, "password": newPassword})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("login with new password: expected 200, got %d: %v", resp.StatusCode, body)
	}

	// The OLD password no longer works.
	fresh2 := newClient(t, srv.URL)
	resp, _ = fresh2.post("/api/v1/auth/login", map[string]string{"email": email, "password": testPassword})
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("login with old password after reset: expected 401, got %d", resp.StatusCode)
	}
}

func TestPasswordResetRequest_DoesNotRevealAccountExistence(t *testing.T) {
	srv, _, _ := testServer(t)
	c := newClient(t, srv.URL)

	resp, body := c.post("/api/v1/auth/password-reset/request", map[string]string{"email": "no-such-account@example.com"})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 (generic success) for a non-existent account, got %d: %v", resp.StatusCode, body)
	}
}
