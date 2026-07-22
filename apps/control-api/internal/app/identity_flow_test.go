package app_test

import (
	"net/http"
	"testing"

	"github.com/pquerna/otp/totp"

	"gridkeep/control-api/internal/testutil"
)

const testPassword = "CorrectHorseBatteryStaple1"

func registerAndVerify(t *testing.T, srv httpTestServer, smtp *testutil.FakeSMTPServer, email string) *client {
	t.Helper()
	c := newClient(t, srv.URL)

	resp, _ := c.post("/api/v1/auth/register", map[string]string{"email": email, "password": testPassword})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("register: expected 201, got %d", resp.StatusCode)
	}

	msg, ok := smtp.LastMessageContaining(email)
	if !ok {
		t.Fatalf("no verification email captured for %s", email)
	}
	token, err := testutil.ExtractToken(msg)
	if err != nil {
		t.Fatalf("extract verification token: %v", err)
	}

	resp, _ = c.post("/api/v1/auth/verify-email", map[string]string{"token": token})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("verify-email: expected 200, got %d", resp.StatusCode)
	}
	return c
}

// registerVerifyAndLogin is registerAndVerify plus the login step, for tests
// that need an authenticated session rather than testing the login flow
// itself.
func registerVerifyAndLogin(t *testing.T, srv httpTestServer, smtp *testutil.FakeSMTPServer, email string) *client {
	t.Helper()
	c := registerAndVerify(t, srv, smtp, email)
	resp, body := c.post("/api/v1/auth/login", map[string]string{"email": email, "password": testPassword})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("login: expected 200, got %d: %v", resp.StatusCode, body)
	}
	return c
}

// httpTestServer is the minimal subset of *httptest.Server this file needs,
// so registerAndVerify can be reused across test files without importing
// net/http/httptest directly in each one.
type httpTestServer struct {
	URL string
}

func TestRegisterVerifyLoginFlow(t *testing.T) {
	srv, smtp, _ := testServer(t)
	email := "register-flow@example.com"

	c := registerAndVerify(t, httpTestServer{URL: srv.URL}, smtp, email)

	resp, body := c.post("/api/v1/auth/login", map[string]string{"email": email, "password": testPassword})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("login: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if mfaRequired, _ := body["mfa_required"].(bool); mfaRequired {
		t.Fatalf("expected mfa_required=false for an account without MFA enrolled")
	}

	resp, body = c.get("/api/v1/auth/me")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("/auth/me: expected 200, got %d", resp.StatusCode)
	}
	if _, ok := body["user_id"]; !ok {
		t.Fatalf("expected user_id in /auth/me response, got %v", body)
	}
}

func TestLoginRejectsWrongPassword(t *testing.T) {
	srv, smtp, _ := testServer(t)
	email := "wrong-password@example.com"
	registerAndVerify(t, httpTestServer{URL: srv.URL}, smtp, email)

	c := newClient(t, srv.URL)
	resp, _ := c.post("/api/v1/auth/login", map[string]string{"email": email, "password": "totally-wrong-password"})
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("expected 401 for wrong password, got %d", resp.StatusCode)
	}
}

func TestLoginLockoutAfterRepeatedFailures(t *testing.T) {
	srv, smtp, _ := testServer(t)
	email := "lockout@example.com"
	registerAndVerify(t, httpTestServer{URL: srv.URL}, smtp, email)

	c := newClient(t, srv.URL)
	// Config in testServer sets LoginLockoutThreshold to 5.
	for i := 0; i < 5; i++ {
		resp, _ := c.post("/api/v1/auth/login", map[string]string{"email": email, "password": "wrong"})
		if resp.StatusCode != http.StatusUnauthorized {
			t.Fatalf("attempt %d: expected 401, got %d", i, resp.StatusCode)
		}
	}

	// The 6th attempt, even with the CORRECT password, must be locked out --
	// proving the lockout is enforced before credentials are even checked.
	resp, _ := c.post("/api/v1/auth/login", map[string]string{"email": email, "password": testPassword})
	if resp.StatusCode != http.StatusTooManyRequests {
		t.Fatalf("expected 429 (locked out) even with correct password, got %d", resp.StatusCode)
	}
}

func TestDuplicateRegistrationRejected(t *testing.T) {
	srv, smtp, _ := testServer(t)
	email := "duplicate@example.com"
	registerAndVerify(t, httpTestServer{URL: srv.URL}, smtp, email)

	c := newClient(t, srv.URL)
	resp, _ := c.post("/api/v1/auth/register", map[string]string{"email": email, "password": testPassword})
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("expected 409 for duplicate registration, got %d", resp.StatusCode)
	}
}

func TestMFAEnrollmentAndLoginChallenge(t *testing.T) {
	srv, smtp, _ := testServer(t)
	email := "mfa-user@example.com"
	c := registerAndVerify(t, httpTestServer{URL: srv.URL}, smtp, email)

	resp, _ := c.post("/api/v1/auth/login", map[string]string{"email": email, "password": testPassword})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("initial login before MFA enrollment: expected 200, got %d", resp.StatusCode)
	}

	resp, body := c.post("/api/v1/auth/mfa/enroll", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("mfa/enroll: expected 200, got %d: %v", resp.StatusCode, body)
	}
	otpauthURI := str(t, body, "otpauth_uri")
	secret := extractTOTPSecret(t, otpauthURI)

	code, err := totp.GenerateCode(secret, timeNow())
	if err != nil {
		t.Fatalf("generate totp code: %v", err)
	}
	resp, _ = c.post("/api/v1/auth/mfa/confirm", map[string]string{"code": code})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("mfa/confirm: expected 200, got %d", resp.StatusCode)
	}

	// A fresh session (new client/cookie jar) must now be challenged for MFA.
	fresh := newClient(t, srv.URL)
	resp, body = fresh.post("/api/v1/auth/login", map[string]string{"email": email, "password": testPassword})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("login after mfa enabled: expected 200, got %d", resp.StatusCode)
	}
	if mfaRequired, _ := body["mfa_required"].(bool); !mfaRequired {
		t.Fatalf("expected mfa_required=true after enabling MFA, got %v", body)
	}
	challenge := str(t, body, "mfa_challenge")

	code2, err := totp.GenerateCode(secret, timeNow())
	if err != nil {
		t.Fatalf("generate totp code: %v", err)
	}
	resp, _ = fresh.post("/api/v1/auth/mfa/verify", map[string]string{"mfa_challenge": challenge, "code": code2})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("mfa/verify: expected 200, got %d", resp.StatusCode)
	}

	resp, _ = fresh.get("/api/v1/auth/me")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("/auth/me after mfa verification: expected 200, got %d", resp.StatusCode)
	}
}
