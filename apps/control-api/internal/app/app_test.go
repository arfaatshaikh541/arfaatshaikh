package app_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/cookiejar"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"

	"gridkeep/control-api/internal/app"
	"gridkeep/control-api/internal/platform/config"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/testutil"
)

// testServer builds the full control-api router against a real, freshly
// truncated test database and a real (fake but protocol-speaking) SMTP
// server, then serves it via httptest.Server. Every integration test in
// this package exercises the exact router production traffic uses --
// sessions, CSRF, RLS-backed authorization -- not a reimplementation of it.
func testServer(t *testing.T) (*httptest.Server, *testutil.FakeSMTPServer, *dbpkg.Store) {
	t.Helper()
	store := testutil.NewStore(t)
	smtp := testutil.StartFakeSMTPServer(t)

	smtpHost, smtpPort, err := splitHostPort(smtp.Addr)
	if err != nil {
		t.Fatalf("split smtp addr: %v", err)
	}

	mfaKey := make([]byte, 32)
	for i := range mfaKey {
		mfaKey[i] = byte(i)
	}

	cfg := &config.Config{
		Env:                   "test",
		SessionCookieName:     "gridkeep_session",
		SessionCookieSecure:   false,
		SessionTTL:            time.Hour,
		StepUpTTL:             15 * time.Minute,
		CORSAllowedOrigins:    []string{"http://localhost:3000"},
		Argon2Memory:          19456,
		Argon2Iterations:      2,
		Argon2Parallelism:     1,
		LoginLockoutThreshold: 5,
		LoginLockoutWindow:    15 * time.Minute,
		EmailVerificationTTL:  24 * time.Hour,
		PasswordResetTTL:      30 * time.Minute,
		SMTPHost:              smtpHost,
		SMTPPort:              smtpPort,
		SMTPFrom:              "no-reply@gridkeep.test",
	}

	router := app.NewRouter(app.Deps{
		Store:  store,
		Cache:  nil,
		Logger: testutil.DiscardLogger(),
		Config: cfg,
		MFAKey: mfaKey,
	})

	srv := httptest.NewServer(router)
	t.Cleanup(srv.Close)
	return srv, smtp, store
}

func splitHostPort(addr string) (string, string, error) {
	var host, port string
	_, err := fmt.Sscanf(addr, "127.0.0.1:%s", &port)
	if err != nil {
		return "", "", err
	}
	host = "127.0.0.1"
	return host, port, nil
}

// client wraps http.Client with a cookie jar (simulating one browser
// session) and tracks the CSRF cookie so state-changing requests can echo
// it back, exactly like the real frontend does.
type client struct {
	t       *testing.T
	baseURL string
	http    *http.Client
}

func newClient(t *testing.T, baseURL string) *client {
	jar, err := cookiejar.New(nil)
	if err != nil {
		t.Fatalf("create cookie jar: %v", err)
	}
	c := &client{t: t, baseURL: baseURL, http: &http.Client{Jar: jar}}
	c.get("/healthz") // warm the CSRF cookie
	return c
}

func (c *client) csrfToken() string {
	u, err := url.Parse(c.baseURL)
	if err != nil {
		c.t.Fatalf("parse base url: %v", err)
	}
	for _, cookie := range c.http.Jar.Cookies(u) {
		if cookie.Name == "gridkeep_csrf" {
			return cookie.Value
		}
	}
	return ""
}

func (c *client) get(path string) (*http.Response, map[string]any) {
	c.t.Helper()
	resp, err := c.http.Get(c.baseURL + path)
	if err != nil {
		c.t.Fatalf("GET %s: %v", path, err)
	}
	defer func() { _ = resp.Body.Close() }()
	var body map[string]any
	_ = json.NewDecoder(resp.Body).Decode(&body)
	return resp, body
}

func (c *client) do(method, path string, payload any) (*http.Response, map[string]any) {
	c.t.Helper()
	var buf bytes.Buffer
	if payload != nil {
		if err := json.NewEncoder(&buf).Encode(payload); err != nil {
			c.t.Fatalf("encode payload: %v", err)
		}
	}
	req, err := http.NewRequest(method, c.baseURL+path, &buf)
	if err != nil {
		c.t.Fatalf("build request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if method != http.MethodGet && method != http.MethodHead {
		req.Header.Set("X-CSRF-Token", c.csrfToken())
	}
	resp, err := c.http.Do(req)
	if err != nil {
		c.t.Fatalf("%s %s: %v", method, path, err)
	}
	defer func() { _ = resp.Body.Close() }()
	var body map[string]any
	_ = json.NewDecoder(resp.Body).Decode(&body)
	return resp, body
}

func (c *client) post(path string, payload any) (*http.Response, map[string]any) {
	return c.do(http.MethodPost, path, payload)
}

func (c *client) patch(path string, payload any) (*http.Response, map[string]any) {
	return c.do(http.MethodPatch, path, payload)
}

// getArray decodes a GET response whose top-level JSON value is an array
// (e.g. the audit log and member-list endpoints), unlike get() which
// assumes an object.
func (c *client) getArray(t *testing.T, path string) []map[string]any {
	t.Helper()
	resp, err := c.http.Get(c.baseURL + path)
	if err != nil {
		t.Fatalf("GET %s: %v", path, err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("GET %s: expected 200, got %d", path, resp.StatusCode)
	}
	var out []map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		t.Fatalf("decode array response from %s: %v", path, err)
	}
	return out
}

// str reads a string field out of a decoded JSON body map, failing the test
// with a clear message if it is missing or not a string.
func str(t *testing.T, body map[string]any, key string) string {
	t.Helper()
	v, ok := body[key]
	if !ok {
		t.Fatalf("expected field %q in response body %v", key, body)
	}
	s, ok := v.(string)
	if !ok {
		t.Fatalf("expected field %q to be a string in response body %v", key, body)
	}
	return s
}

func grantPlatformRole(t *testing.T, store *dbpkg.Store, email, roleKey string) {
	t.Helper()
	ctx := t.Context()
	_, err := store.Pool.Exec(ctx, `
		INSERT INTO platform_role_assignments (user_id, role_id)
		SELECT u.id, r.id FROM users u, roles r
		WHERE u.email = $1 AND r.scope_type = 'platform' AND r.key = $2
		ON CONFLICT (user_id, role_id) DO NOTHING
	`, email, roleKey)
	if err != nil {
		t.Fatalf("grant platform role %s to %s: %v", roleKey, email, err)
	}
}
