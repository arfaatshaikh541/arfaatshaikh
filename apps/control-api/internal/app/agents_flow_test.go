package app_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"testing"
	"time"

	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/pki"
	"gridkeep/control-api/internal/testutil"
)

// postRaw sends a POST request with an exact, pre-serialized body (used
// where the signature must cover precisely those bytes) plus any extra
// headers, echoing the CSRF token like every other write in this client.
func (c *client) postRaw(path string, rawBody []byte, extraHeaders map[string]string) (*http.Response, map[string]any) {
	c.t.Helper()
	req, err := http.NewRequest(http.MethodPost, c.baseURL+path, bytes.NewReader(rawBody))
	if err != nil {
		c.t.Fatalf("build request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-CSRF-Token", c.csrfToken())
	for k, v := range extraHeaders {
		req.Header.Set(k, v)
	}
	resp, err := c.http.Do(req)
	if err != nil {
		c.t.Fatalf("POST %s: %v", path, err)
	}
	defer func() { _ = resp.Body.Close() }()
	var body map[string]any
	_ = json.NewDecoder(resp.Body).Decode(&body)
	return resp, body
}

// setUpOperatorWithCluster is a shared fixture for the agent tests: an
// active operator with one data centre and one cluster, ready to receive
// agent-submitted capacity snapshots.
func setUpOperatorWithCluster(t *testing.T, base httpTestServer, smtp *testutil.FakeSMTPServer, store *dbpkg.Store, suffix string) (owner *client, operatorID, clusterID string) {
	t.Helper()
	platformAdmin := registerVerifyAndLogin(t, base, smtp, "agents-platform-admin-"+suffix+"@example.com")
	grantPlatformRole(t, store, "agents-platform-admin-"+suffix+"@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "DE", "name": "Germany " + suffix})
	jurisdictionID := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "eu-" + suffix, "name": "EU " + suffix, "jurisdiction_id": jurisdictionID})
	regionID := str(t, body, "id")

	owner = registerVerifyAndLogin(t, base, smtp, "agents-operator-owner-"+suffix+"@example.com")
	operatorID = createOperator(t, owner, "Agents Test Operator "+suffix, "DE")
	activateOperator(t, platformAdmin, operatorID)

	_, body = owner.post("/api/v1/operators/"+operatorID+"/data-centres", map[string]string{
		"region_id": regionID, "name": "DC " + suffix, "locality": "Berlin",
	})
	dataCentreID := str(t, body, "id")

	_, body = owner.post("/api/v1/operators/"+operatorID+"/clusters", map[string]string{
		"data_centre_id": dataCentreID, "name": "cluster-" + suffix,
	})
	clusterID = str(t, body, "id")
	return owner, operatorID, clusterID
}

// TestAgentBootstrapAndCapacitySnapshotLifecycle exercises the entire
// Milestone 2 machine-identity chain for real: register an agent, bootstrap
// it with a real generated key pair and CSR (the same code the mock
// connector CLI uses), receive a real CA-issued certificate, sign a
// capacity snapshot with the resulting private key, and submit it.
func TestAgentBootstrapAndCapacitySnapshotLifecycle(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}
	owner, operatorID, clusterID := setUpOperatorWithCluster(t, base, smtp, store, "lifecycle")

	resp, body := owner.post("/api/v1/operators/"+operatorID+"/agents", map[string]string{"name": "edge-agent-1"})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("register agent: expected 201, got %d: %v", resp.StatusCode, body)
	}
	agentObj, ok := body["agent"].(map[string]any)
	if !ok {
		t.Fatalf("expected agent object in response, got %v", body)
	}
	agentID, _ := agentObj["id"].(string)
	bootstrapToken, _ := body["bootstrap_token"].(string)
	if agentID == "" || bootstrapToken == "" {
		t.Fatalf("expected agent id and bootstrap token, got %v", body)
	}

	keyPEM, csrPEM, err := pki.GenerateKeyAndCSR(agentID)
	if err != nil {
		t.Fatalf("generate key and CSR: %v", err)
	}

	anon := newClient(t, srv.URL)
	resp, body = anon.post("/api/v1/agent-bootstrap", map[string]string{
		"bootstrap_token": bootstrapToken, "csr_pem": csrPEM,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("bootstrap: expected 201, got %d: %v", resp.StatusCode, body)
	}
	certPEM := str(t, body, "certificate_pem")

	payload := map[string]any{"node_count": 4, "gpu_type": "H100"}
	snapshotReq := map[string]any{
		"cluster_id":   clusterID,
		"collected_at": time.Now().UTC().Format(time.RFC3339),
		"payload":      payload,
	}
	rawBody, err := json.Marshal(snapshotReq)
	if err != nil {
		t.Fatalf("marshal snapshot request: %v", err)
	}
	signature, err := pki.SignMessage(keyPEM, rawBody)
	if err != nil {
		t.Fatalf("sign capacity snapshot: %v", err)
	}

	resp, body = anon.postRaw("/api/v1/agents/"+agentID+"/capacity-snapshots", rawBody, map[string]string{
		"X-Agent-Signature": signature,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("submit capacity snapshot: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if certPEM == "" {
		t.Fatalf("expected a non-empty issued certificate")
	}

	snapshots := owner.getArray(t, "/api/v1/operators/"+operatorID+"/capacity-snapshots")
	if len(snapshots) != 1 {
		t.Fatalf("expected 1 capacity snapshot visible to the operator, got %d", len(snapshots))
	}
	if trustStatus, _ := snapshots[0]["trust_status"].(string); trustStatus != "verified" {
		t.Fatalf("expected trust_status=verified, got %v", snapshots[0]["trust_status"])
	}
}

// TestAgentCapacitySnapshotRejectsInvalidSignature proves a snapshot signed
// with the wrong (attacker-controlled) key is rejected, not silently
// trusted.
func TestAgentCapacitySnapshotRejectsInvalidSignature(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}
	owner, operatorID, clusterID := setUpOperatorWithCluster(t, base, smtp, store, "badsig")

	_, body := owner.post("/api/v1/operators/"+operatorID+"/agents", map[string]string{"name": "edge-agent-2"})
	agentObj := body["agent"].(map[string]any)
	agentID, _ := agentObj["id"].(string)
	bootstrapToken, _ := body["bootstrap_token"].(string)

	_, csrPEM, err := pki.GenerateKeyAndCSR(agentID)
	if err != nil {
		t.Fatalf("generate key and CSR: %v", err)
	}
	anon := newClient(t, srv.URL)
	resp, body := anon.post("/api/v1/agent-bootstrap", map[string]string{"bootstrap_token": bootstrapToken, "csr_pem": csrPEM})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("bootstrap: expected 201, got %d: %v", resp.StatusCode, body)
	}

	attackerKeyPEM, _, err := pki.GenerateKeyAndCSR("attacker")
	if err != nil {
		t.Fatalf("generate attacker key: %v", err)
	}

	snapshotReq := map[string]any{
		"cluster_id":   clusterID,
		"collected_at": time.Now().UTC().Format(time.RFC3339),
		"payload":      map[string]any{"node_count": 999},
	}
	rawBody, err := json.Marshal(snapshotReq)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	badSignature, err := pki.SignMessage(attackerKeyPEM, rawBody)
	if err != nil {
		t.Fatalf("sign with attacker key: %v", err)
	}

	resp, body = anon.postRaw("/api/v1/agents/"+agentID+"/capacity-snapshots", rawBody, map[string]string{
		"X-Agent-Signature": badSignature,
	})
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("submit snapshot with wrong key's signature: expected 401, got %d: %v", resp.StatusCode, body)
	}
}

// TestAgentBootstrapTokenIsSingleUse proves a bootstrap token cannot be
// replayed to mint a second certificate.
func TestAgentBootstrapTokenIsSingleUse(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}
	owner, operatorID, _ := setUpOperatorWithCluster(t, base, smtp, store, "singleuse")

	_, body := owner.post("/api/v1/operators/"+operatorID+"/agents", map[string]string{"name": "edge-agent-3"})
	agentObj := body["agent"].(map[string]any)
	agentID, _ := agentObj["id"].(string)
	bootstrapToken, _ := body["bootstrap_token"].(string)

	_, csrPEM1, err := pki.GenerateKeyAndCSR(agentID)
	if err != nil {
		t.Fatalf("generate CSR 1: %v", err)
	}
	anon := newClient(t, srv.URL)
	resp, body := anon.post("/api/v1/agent-bootstrap", map[string]string{"bootstrap_token": bootstrapToken, "csr_pem": csrPEM1})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("first bootstrap: expected 201, got %d: %v", resp.StatusCode, body)
	}

	_, csrPEM2, err := pki.GenerateKeyAndCSR(agentID)
	if err != nil {
		t.Fatalf("generate CSR 2: %v", err)
	}
	resp, body = anon.post("/api/v1/agent-bootstrap", map[string]string{"bootstrap_token": bootstrapToken, "csr_pem": csrPEM2})
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("replayed bootstrap token: expected 401, got %d: %v", resp.StatusCode, body)
	}
}

// TestAgentRevocationBlocksFurtherCapacitySnapshots proves a revoked
// agent's certificate is no longer accepted for new submissions, even
// though it is still cryptographically valid (unexpired).
func TestAgentRevocationBlocksFurtherCapacitySnapshots(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}
	owner, operatorID, clusterID := setUpOperatorWithCluster(t, base, smtp, store, "revoke")

	_, body := owner.post("/api/v1/operators/"+operatorID+"/agents", map[string]string{"name": "edge-agent-4"})
	agentObj := body["agent"].(map[string]any)
	agentID, _ := agentObj["id"].(string)
	bootstrapToken, _ := body["bootstrap_token"].(string)

	keyPEM, csrPEM, err := pki.GenerateKeyAndCSR(agentID)
	if err != nil {
		t.Fatalf("generate CSR: %v", err)
	}
	anon := newClient(t, srv.URL)
	resp, body := anon.post("/api/v1/agent-bootstrap", map[string]string{"bootstrap_token": bootstrapToken, "csr_pem": csrPEM})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("bootstrap: expected 201, got %d: %v", resp.StatusCode, body)
	}

	resp, body = owner.post("/api/v1/operators/"+operatorID+"/agents/"+agentID+"/revoke", map[string]string{"reason": "device decommissioned"})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("revoke agent: expected 200, got %d: %v", resp.StatusCode, body)
	}

	snapshotReq := map[string]any{
		"cluster_id":   clusterID,
		"collected_at": time.Now().UTC().Format(time.RFC3339),
		"payload":      map[string]any{"node_count": 1},
	}
	rawBody, err := json.Marshal(snapshotReq)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	signature, err := pki.SignMessage(keyPEM, rawBody)
	if err != nil {
		t.Fatalf("sign: %v", err)
	}

	resp, body = anon.postRaw("/api/v1/agents/"+agentID+"/capacity-snapshots", rawBody, map[string]string{
		"X-Agent-Signature": signature,
	})
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("submit snapshot after revocation: expected 401, got %d: %v", resp.StatusCode, body)
	}
}
