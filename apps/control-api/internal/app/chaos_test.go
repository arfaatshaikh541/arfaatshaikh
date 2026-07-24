package app_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"gridkeep/control-api/internal/app"
	"gridkeep/control-api/internal/platform/cache"
	"gridkeep/control-api/internal/platform/config"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/pki"
	"gridkeep/control-api/internal/testutil"
)

// testServerWithCache is testServer's setup duplicated with one difference:
// a real *cache.Client (backed by a real, locally-running Redis, per
// internal/platform/cache/redis.go's Connect) instead of testServer's nil.
// Kept separate from testServer rather than adding a parameter to it, so
// this one chaos test's Redis dependency can never affect the rest of the
// suite, which correctly has no Redis dependency at all.
func testServerWithCache(t *testing.T, cacheClient *cache.Client) (*httptest.Server, *testutil.FakeSMTPServer, *dbpkg.Store) {
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
	pkiCAKey := make([]byte, 32)
	for i := range pkiCAKey {
		pkiCAKey[i] = byte(i + 1)
	}
	ca, err := pki.LoadOrCreate(context.Background(), store.Pool, pkiCAKey)
	if err != nil {
		t.Fatalf("load or create test CA: %v", err)
	}
	secretsVaultKey := make([]byte, 32)
	for i := range secretsVaultKey {
		secretsVaultKey[i] = byte(i + 2)
	}

	fakeEngine := startFakePolicyEngine(t)
	fakeStorage := startFakeObjectStore(t)

	cfg := &config.Config{
		Env:                      "test",
		SessionCookieName:        "gridkeep_session",
		SessionCookieSecure:      false,
		SessionTTL:               time.Hour,
		StepUpTTL:                15 * time.Minute,
		CORSAllowedOrigins:       []string{"http://localhost:3000"},
		Argon2Memory:             19456,
		Argon2Iterations:         2,
		Argon2Parallelism:        1,
		LoginLockoutThreshold:    5,
		LoginLockoutWindow:       15 * time.Minute,
		EmailVerificationTTL:     24 * time.Hour,
		PasswordResetTTL:         30 * time.Minute,
		MFAMaxAttempts:           5,
		AgentBootstrapTokenTTL:   24 * time.Hour,
		AgentCertificateTTL:      72 * time.Hour,
		PolicyEngineURL:          fakeEngine.URL,
		PolicyEngineTimeout:      5 * time.Second,
		ArtefactMaxContentLength: 20 * 1024 * 1024 * 1024,
		ArtefactUploadURLTTL:     15 * time.Minute,
		ArtefactDownloadURLTTL:   15 * time.Minute,
		SMTPHost:                 smtpHost,
		SMTPPort:                 smtpPort,
		SMTPFrom:                 "no-reply@gridkeep.test",
	}

	router := app.NewRouter(app.Deps{
		Store:           store,
		Cache:           cacheClient,
		Logger:          testutil.DiscardLogger(),
		Config:          cfg,
		MFAKey:          mfaKey,
		CA:              ca,
		Storage:         fakeStorage,
		SecretsVaultKey: secretsVaultKey,
	})

	srv := httptest.NewServer(router)
	t.Cleanup(srv.Close)
	return srv, smtp, store
}

// TestEntitlementsSurviveRedisOutage is an actually-executed chaos
// experiment (Milestone 16), not a description of one: it connects a real
// cache.Client to a real, locally-running Redis, warms the entitlements
// cache with one successful request, then forces every subsequent Redis
// call on that connection to fail (closing the pool -- the same failure
// shape a Redis outage produces from the caller's point of view: every
// command errors), and proves the entitlements endpoint still returns
// 200 with correct data. This is the property subscriptions.Service's own
// package doc already claims ("a cache miss or Redis outage falls back to
// Postgres, never to an 'allow by default' decision") -- proven here
// against a real Redis process, not merely asserted by reading the code.
func TestEntitlementsSurviveRedisOutage(t *testing.T) {
	ctx := context.Background()
	cacheClient, err := cache.Connect(ctx, "redis://localhost:6379/15")
	if err != nil {
		t.Skipf("no local Redis reachable for this chaos experiment: %v", err)
	}

	srv, smtp, _ := testServerWithCache(t, cacheClient)
	base := httpTestServer{URL: srv.URL}
	owner := registerVerifyAndLogin(t, base, smtp, "chaos-redis-owner@example.com")
	tenantID := createTenant(t, owner, "Chaos Redis Tenant", "AE")

	// Warm the cache: the first read populates entitlements:enterprise:<id>.
	resp, body := owner.get("/api/v1/enterprises/" + tenantID + "/subscription")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("warm-up entitlements read: expected 200, got %d: %v", resp.StatusCode, body)
	}
	warm, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal warm-up body: %v", err)
	}

	// Simulate a Redis outage: close the connection pool out from under the
	// running service, so every subsequent command this service issues
	// against it fails exactly the way a real network partition or a
	// crashed Redis process would from the caller's point of view.
	if err := cacheClient.Raw().Close(); err != nil {
		t.Fatalf("simulate redis outage (close pool): %v", err)
	}

	resp, body = owner.get("/api/v1/enterprises/" + tenantID + "/subscription")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("entitlements read during simulated Redis outage: expected 200, got %d: %v", resp.StatusCode, body)
	}
	duringOutage, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal during-outage body: %v", err)
	}
	if string(warm) != string(duringOutage) {
		t.Fatalf("entitlements changed across a Redis outage that touched no underlying data: warm=%s duringOutage=%s", warm, duringOutage)
	}
}
