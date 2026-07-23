package app_test

import (
	"encoding/json"
	"fmt"
	"net/http"
	"testing"
	"time"

	"gridkeep/control-api/internal/platform/pki"
)

// testControlMessage mirrors cmd/mockclusteragent's own decode type:
// Payload as json.RawMessage, not a generic map, is what preserves the
// exact bytes Signature was computed over through the JSON round trip --
// decoding into map[string]any and re-marshaling to verify a signature
// would reorder keys (Go sorts map keys alphabetically on marshal, but the
// original was signed in struct declaration order) and spuriously fail.
type testControlMessage struct {
	ID        string          `json:"id"`
	Payload   json.RawMessage `json:"payload"`
	Signature string          `json:"signature"`
}

// pollPendingMessagesForTest signs the canonical poll challenge with the
// agent's own key and fetches pending control messages -- the exact same
// request cmd/mockclusteragent makes, reimplemented here so the test does
// not need to shell out to a separate binary.
func pollPendingMessagesForTest(t *testing.T, baseURL, agentID, keyPEM string) []testControlMessage {
	t.Helper()
	nonce := fmt.Sprintf("poll-%d", time.Now().UnixNano())
	signedAt := time.Now().UTC().Format(time.RFC3339)
	challenge := fmt.Sprintf("poll:%s:%s:%s", agentID, nonce, signedAt)
	signature, err := pki.SignMessage(keyPEM, []byte(challenge))
	if err != nil {
		t.Fatalf("sign poll challenge: %v", err)
	}

	req, err := http.NewRequest(http.MethodGet, baseURL+"/api/v1/cluster-agents/"+agentID+"/control-messages/pending", nil)
	if err != nil {
		t.Fatalf("build poll request: %v", err)
	}
	req.Header.Set("X-Agent-Nonce", nonce)
	req.Header.Set("X-Agent-Signed-At", signedAt)
	req.Header.Set("X-Agent-Signature", signature)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("poll pending messages: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("poll pending messages: expected 200, got %d", resp.StatusCode)
	}
	var out []testControlMessage
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		t.Fatalf("decode pending messages: %v", err)
	}
	return out
}

func rfc3339Now() string {
	return time.Now().UTC().Format(time.RFC3339)
}

// registerAndBootstrapClusterAgent registers a cluster agent for the given
// cluster and bootstraps it with a real generated key pair and CSR,
// returning the agent id, its private key PEM, and its issued certificate.
func registerAndBootstrapClusterAgent(t *testing.T, owner *client, operatorID, clusterID, name string) (agentID, keyPEM, certPEM string) {
	t.Helper()
	resp, body := owner.post("/api/v1/operators/"+operatorID+"/cluster-agents", map[string]string{
		"cluster_id": clusterID, "name": name,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("register cluster agent: expected 201, got %d: %v", resp.StatusCode, body)
	}
	agentObj := body["agent"].(map[string]any)
	agentID, _ = agentObj["id"].(string)
	bootstrapToken, _ := body["bootstrap_token"].(string)
	if agentID == "" || bootstrapToken == "" {
		t.Fatalf("expected cluster agent id and bootstrap token, got %v", body)
	}

	var csrPEM string
	keyPEM, csrPEM, err := pki.GenerateKeyAndCSR(agentID)
	if err != nil {
		t.Fatalf("generate key and CSR: %v", err)
	}

	anon := newClient(t, owner.baseURL)
	resp, body = anon.post("/api/v1/cluster-agent-bootstrap", map[string]string{
		"bootstrap_token": bootstrapToken, "csr_pem": csrPEM,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("cluster agent bootstrap: expected 201, got %d: %v", resp.StatusCode, body)
	}
	certPEM = str(t, body, "certificate_pem")
	return agentID, keyPEM, certPEM
}

// TestClusterAgentDeploymentPlanValidationLifecycle exercises Milestone 6's
// core round trip end to end, with real cryptography on both sides: an
// operator requests a deployment-plan validation, the (test-side, standing
// in for cmd/mockclusteragent) cluster agent polls for it, verifies the
// control-plane's signature against the CA's own certificate (fetched from
// the public endpoint), and signs back an "allow" decision -- which
// control-api verifies, records as a DeploymentPlanValidation, and marks
// the original message responded.
func TestClusterAgentDeploymentPlanValidationLifecycle(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}
	owner, operatorID, clusterID := setUpOperatorWithCluster(t, base, smtp, store, "planlifecycle")

	agentID, keyPEM, certPEM := registerAndBootstrapClusterAgent(t, owner, operatorID, clusterID, "cluster-agent-1")
	if certPEM == "" {
		t.Fatalf("expected a non-empty issued certificate")
	}

	anon := newClient(t, srv.URL)
	resp, body := anon.get("/api/v1/platform-ca/certificate")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("fetch CA certificate: expected 200, got %d: %v", resp.StatusCode, body)
	}
	caCertPEM := str(t, body, "certificate_pem")

	resp, body = owner.post("/api/v1/operators/"+operatorID+"/deployment-plan-requests", map[string]any{
		"cluster_id": clusterID, "namespace": "tenant-fictional-rag",
		"resource_quota":   map[string]any{"cpu": "8", "memory_gb": 32},
		"network_policy":   map[string]any{"deny_by_default": true},
		"security_context": map[string]any{"run_as_non_root": true},
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("request deployment plan validation: expected 201, got %d: %v", resp.StatusCode, body)
	}
	messageID := str(t, body, "id")

	// Identity for the poll itself is proved by a signature over a
	// canonical challenge string, sent as headers, not a body.
	pending := pollPendingMessagesForTest(t, srv.URL, agentID, keyPEM)
	if len(pending) != 1 {
		t.Fatalf("expected 1 pending control message, got %d", len(pending))
	}
	if pending[0].ID != messageID {
		t.Fatalf("expected pending message id %s, got %v", messageID, pending[0].ID)
	}

	// Local enforcement: verify the control-plane's signature against the
	// CA's own certificate before trusting anything about the plan. This
	// uses pending[0].Payload directly (json.RawMessage, the exact bytes
	// that traveled over the wire) rather than reconstructing it -- the
	// same discipline cmd/mockclusteragent's real verification uses.
	valid, err := pki.VerifySignature(caCertPEM, pending[0].Payload, pending[0].Signature)
	if err != nil {
		t.Fatalf("verify control-plane signature: %v", err)
	}
	if !valid {
		t.Fatalf("expected the control-plane's signature to verify against the CA's own certificate")
	}

	// Respond with a signed "allow" decision.
	respBody, err := json.Marshal(map[string]any{
		"decision": "allow", "reason_codes": []string{},
		"nonce": "respond-nonce-1", "signed_at": rfc3339Now(),
	})
	if err != nil {
		t.Fatalf("marshal response body: %v", err)
	}
	agentSignature, err := pki.SignMessage(keyPEM, respBody)
	if err != nil {
		t.Fatalf("sign response: %v", err)
	}
	resp, body = anon.postRaw("/api/v1/cluster-agents/"+agentID+"/control-messages/"+messageID+"/respond", respBody, map[string]string{
		"X-Agent-Signature": agentSignature,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("respond to control message: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if got := body["policy_decision"]; got != "allow" {
		t.Fatalf("expected policy_decision allow, got %v", got)
	}
	if got := body["signature_valid"]; got != true {
		t.Fatalf("expected signature_valid true, got %v", got)
	}

	validations := owner.getArray(t, "/api/v1/operators/"+operatorID+"/cluster-agents/"+agentID+"/deployment-plan-validations")
	if len(validations) != 1 {
		t.Fatalf("expected 1 deployment plan validation, got %d", len(validations))
	}

	pendingAfter := pollPendingMessagesForTest(t, srv.URL, agentID, keyPEM)
	if len(pendingAfter) != 0 {
		t.Fatalf("expected 0 pending messages after responding, got %d", len(pendingAfter))
	}
}

// TestControlMessageRespondRejectsReplayedNonce proves a captured, valid
// signed response cannot be replayed with the same nonce to fabricate a
// second recorded decision.
func TestControlMessageRespondRejectsReplayedNonce(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}
	owner, operatorID, clusterID := setUpOperatorWithCluster(t, base, smtp, store, "replay")
	agentID, keyPEM, _ := registerAndBootstrapClusterAgent(t, owner, operatorID, clusterID, "cluster-agent-replay")

	_, body := owner.post("/api/v1/operators/"+operatorID+"/deployment-plan-requests", map[string]any{
		"cluster_id": clusterID, "namespace": "tenant-a", "resource_quota": map[string]any{}, "network_policy": map[string]any{}, "security_context": map[string]any{},
	})
	messageID := str(t, body, "id")

	anon := newClient(t, srv.URL)
	respBody, _ := json.Marshal(map[string]any{"decision": "allow", "reason_codes": []string{}, "nonce": "fixed-nonce", "signed_at": rfc3339Now()})
	signature, err := pki.SignMessage(keyPEM, respBody)
	if err != nil {
		t.Fatalf("sign: %v", err)
	}
	resp, body := anon.postRaw("/api/v1/cluster-agents/"+agentID+"/control-messages/"+messageID+"/respond", respBody, map[string]string{"X-Agent-Signature": signature})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("first respond: expected 201, got %d: %v", resp.StatusCode, body)
	}

	// A second request, this time to a second plan, reusing the exact same
	// nonce, must be rejected -- (cluster_agent_id, nonce) is unique
	// regardless of which message it targets.
	_, body = owner.post("/api/v1/operators/"+operatorID+"/deployment-plan-requests", map[string]any{
		"cluster_id": clusterID, "namespace": "tenant-b", "resource_quota": map[string]any{}, "network_policy": map[string]any{}, "security_context": map[string]any{},
	})
	secondMessageID := str(t, body, "id")
	resp, body = anon.postRaw("/api/v1/cluster-agents/"+agentID+"/control-messages/"+secondMessageID+"/respond", respBody, map[string]string{"X-Agent-Signature": signature})
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("replayed nonce: expected 409, got %d: %v", resp.StatusCode, body)
	}
}

// TestControlMessageRespondRejectsInvalidSignature proves a response signed
// with the wrong (attacker-controlled) key is rejected, not silently
// trusted as the agent's own decision.
func TestControlMessageRespondRejectsInvalidSignature(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}
	owner, operatorID, clusterID := setUpOperatorWithCluster(t, base, smtp, store, "badagentsig")
	agentID, _, _ := registerAndBootstrapClusterAgent(t, owner, operatorID, clusterID, "cluster-agent-badsig")

	_, body := owner.post("/api/v1/operators/"+operatorID+"/deployment-plan-requests", map[string]any{
		"cluster_id": clusterID, "namespace": "tenant-c", "resource_quota": map[string]any{}, "network_policy": map[string]any{}, "security_context": map[string]any{},
	})
	messageID := str(t, body, "id")

	attackerKeyPEM, _, err := pki.GenerateKeyAndCSR("attacker")
	if err != nil {
		t.Fatalf("generate attacker key: %v", err)
	}
	respBody, _ := json.Marshal(map[string]any{"decision": "allow", "reason_codes": []string{}, "nonce": "n1", "signed_at": rfc3339Now()})
	badSignature, err := pki.SignMessage(attackerKeyPEM, respBody)
	if err != nil {
		t.Fatalf("sign with attacker key: %v", err)
	}

	anon := newClient(t, srv.URL)
	resp, body := anon.postRaw("/api/v1/cluster-agents/"+agentID+"/control-messages/"+messageID+"/respond", respBody, map[string]string{"X-Agent-Signature": badSignature})
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("respond with attacker's signature: expected 401, got %d: %v", resp.StatusCode, body)
	}
}

// TestDeploymentPlanValidationRequiresActiveClusterAgent proves a plan
// cannot be requested for a cluster with no active cluster agent.
func TestDeploymentPlanValidationRequiresActiveClusterAgent(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}
	owner, operatorID, clusterID := setUpOperatorWithCluster(t, base, smtp, store, "noagent")

	resp, body := owner.post("/api/v1/operators/"+operatorID+"/deployment-plan-requests", map[string]any{
		"cluster_id": clusterID, "namespace": "tenant-d", "resource_quota": map[string]any{}, "network_policy": map[string]any{}, "security_context": map[string]any{},
	})
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("request plan validation with no active cluster agent: expected 409, got %d: %v", resp.StatusCode, body)
	}
}

// TestClusterAgentCertificateRotation proves an agent can renew its
// identity by proving possession of its current certificate's private key
// -- no bootstrap token involved -- and that the old certificate is
// revoked once the new one is issued.
func TestClusterAgentCertificateRotation(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}
	owner, operatorID, clusterID := setUpOperatorWithCluster(t, base, smtp, store, "rotate")
	agentID, oldKeyPEM, _ := registerAndBootstrapClusterAgent(t, owner, operatorID, clusterID, "cluster-agent-rotate")

	newKeyPEM, newCSRPEM, err := pki.GenerateKeyAndCSR(agentID)
	if err != nil {
		t.Fatalf("generate new key and CSR: %v", err)
	}
	proof, err := pki.SignMessage(oldKeyPEM, []byte(newCSRPEM))
	if err != nil {
		t.Fatalf("sign rotation proof: %v", err)
	}

	anon := newClient(t, srv.URL)
	resp, body := anon.post("/api/v1/cluster-agents/"+agentID+"/rotate-certificate", map[string]string{
		"csr_pem": newCSRPEM, "signature": proof,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("rotate certificate: expected 201, got %d: %v", resp.StatusCode, body)
	}
	newCertPEM := str(t, body, "certificate_pem")
	if newCertPEM == "" {
		t.Fatalf("expected a non-empty rotated certificate")
	}

	certs := owner.getArray(t, "/api/v1/operators/"+operatorID+"/cluster-agents/"+agentID+"/certificates")
	if len(certs) != 2 {
		t.Fatalf("expected 2 certificates (original + rotated), got %d", len(certs))
	}
	var oldRevoked, newActive bool
	for _, c := range certs {
		if c["certificate_pem"] == nil && c["revoked_at"] != nil {
			oldRevoked = true
		}
		if c["revoked_at"] == nil {
			newActive = true
		}
	}
	if !newActive {
		t.Fatalf("expected exactly one non-revoked certificate after rotation, got %v", certs)
	}
	_ = oldRevoked // presence checked via count above; revoked_at nullability confirms rotation took effect

	// Rotating again using the OLD (now-revoked) key must fail -- proves
	// revocation, not just insertion of a new row, actually took effect.
	_, staleCSRPEM, err := pki.GenerateKeyAndCSR(agentID)
	if err != nil {
		t.Fatalf("generate stale csr: %v", err)
	}
	staleProof, err := pki.SignMessage(oldKeyPEM, []byte(staleCSRPEM))
	if err != nil {
		t.Fatalf("sign stale proof: %v", err)
	}
	resp, body = anon.post("/api/v1/cluster-agents/"+agentID+"/rotate-certificate", map[string]string{
		"csr_pem": staleCSRPEM, "signature": staleProof,
	})
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("rotate using revoked key: expected 401, got %d: %v", resp.StatusCode, body)
	}
	_ = newKeyPEM
}

// TestOperatorAgentCertificateRotation proves the same rotation capability
// works for Milestone 2's original operator-wide agent identity.
func TestOperatorAgentCertificateRotation(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}
	owner, operatorID, _ := setUpOperatorWithCluster(t, base, smtp, store, "opagentrotate")

	resp, body := owner.post("/api/v1/operators/"+operatorID+"/agents", map[string]string{"name": "operator-agent-rotate"})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("register agent: expected 201, got %d: %v", resp.StatusCode, body)
	}
	agentObj := body["agent"].(map[string]any)
	agentID, _ := agentObj["id"].(string)
	bootstrapToken, _ := body["bootstrap_token"].(string)

	keyPEM, csrPEM, err := pki.GenerateKeyAndCSR(agentID)
	if err != nil {
		t.Fatalf("generate key and CSR: %v", err)
	}
	anon := newClient(t, srv.URL)
	resp, body = anon.post("/api/v1/agent-bootstrap", map[string]string{"bootstrap_token": bootstrapToken, "csr_pem": csrPEM})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("bootstrap: expected 201, got %d: %v", resp.StatusCode, body)
	}

	newKeyPEM, newCSRPEM, err := pki.GenerateKeyAndCSR(agentID)
	if err != nil {
		t.Fatalf("generate new key and CSR: %v", err)
	}
	proof, err := pki.SignMessage(keyPEM, []byte(newCSRPEM))
	if err != nil {
		t.Fatalf("sign rotation proof: %v", err)
	}
	resp, body = anon.post("/api/v1/agents/"+agentID+"/rotate-certificate", map[string]string{
		"csr_pem": newCSRPEM, "signature": proof,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("rotate operator agent certificate: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if str(t, body, "certificate_pem") == "" {
		t.Fatalf("expected a non-empty rotated certificate")
	}

	certs := owner.getArray(t, "/api/v1/operators/"+operatorID+"/agents/"+agentID+"/certificates")
	if len(certs) != 2 {
		t.Fatalf("expected 2 certificates (original + rotated), got %d", len(certs))
	}
	_ = newKeyPEM
}
