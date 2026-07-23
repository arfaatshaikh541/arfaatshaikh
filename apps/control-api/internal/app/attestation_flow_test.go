package app_test

import (
	"encoding/json"
	"fmt"
	"net/http"
	"testing"
	"time"

	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/pki"
	"gridkeep/control-api/internal/testutil"
)

// setUpOperatorWithConfidentialComputingOffer mirrors setUpOperatorWithOffer
// but publishes its capacity offer with confidential_computing_available=true
// -- required for placement to even consider it eligible for a workload
// version whose security_requirements.confidential_computing_required is
// set, per Milestone 5's step-3 eligibility filter.
func setUpOperatorWithConfidentialComputingOffer(t *testing.T, base httpTestServer, smtp *testutil.FakeSMTPServer, platformAdmin *client, seed, regionID string) (operatorOwner *client, operatorID, offerID string) {
	t.Helper()
	owner := registerVerifyAndLogin(t, base, smtp, seed+"-owner@example.com")
	operatorID = createOperator(t, owner, seed+" Operator", "AE")
	activateOperator(t, platformAdmin, operatorID)

	resp, body := owner.post("/api/v1/operators/"+operatorID+"/data-centres", map[string]string{
		"region_id": regionID, "name": seed + " DC1", "locality": seed,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create data centre: expected 201, got %d: %v", resp.StatusCode, body)
	}
	dataCentreID := str(t, body, "id")

	resp, body = owner.post("/api/v1/operators/"+operatorID+"/clusters", map[string]string{
		"data_centre_id": dataCentreID, "name": seed + "-cluster", "kubernetes_version": "1.31",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create cluster: expected 201, got %d: %v", resp.StatusCode, body)
	}
	clusterID := str(t, body, "id")

	resp, body = owner.post("/api/v1/operators/"+operatorID+"/capacity-offers", map[string]any{
		"cluster_id": clusterID, "accelerator_type": "nvidia-h100", "total_capacity": 10,
		"price_per_unit_hour": 2.00, "currency": "USD",
		"confidential_computing_available": true, "estimated_kwh_per_unit_hour": 0.5,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create capacity offer: expected 201, got %d: %v", resp.StatusCode, body)
	}
	return owner, operatorID, str(t, body, "id")
}

// setUpConfidentialComputingWorkload mirrors setUpDeployableWorkload but
// marks the workload version's security_requirements.confidential_computing_required
// so its deployments exercise Milestone 8's key-release gate.
func setUpConfidentialComputingWorkload(t *testing.T, store *dbpkg.Store, owner, approver *client, tenantID, seed string) (versionID, imageID string) {
	t.Helper()
	licenceID := seedModelLicence(t, store, seed+"-licence", true)
	seedApprovedRegistry(t, store, "registry.example.com")
	imageID = approveTestImage(t, owner, tenantID, seed+"-image")
	modelVersionID := approveTestModelVersion(t, owner, approver, tenantID, licenceID, seed+"-model", seed+"-model-v1", []string{"AE"})

	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/workloads", map[string]any{
		"workload_key": seed, "workload_type": "batch_inference", "name": seed, "description": "",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create workload: expected 201, got %d: %v", resp.StatusCode, body)
	}
	workloadID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/workloads/"+workloadID+"/versions", map[string]any{
		"container_image_id":           imageID,
		"model_version_id":             modelVersionID,
		"residency_requirements":       map[string]any{"allowed_countries": []string{"AE"}},
		"resource_requirements":        map[string]any{"gpu_count": 1},
		"security_requirements":        map[string]any{"confidential_computing_required": true},
		"deployment_approval_required": false,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create workload version draft: expected 201, got %d: %v", resp.StatusCode, body)
	}
	versionID = str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/workload-versions/"+versionID+"/components", map[string]any{
		"component_key": "primary", "name": "Primary Container", "container_image_id": imageID,
		"command": []string{"/entrypoint"}, "args": []string{"--serve"}, "env": map[string]any{"LOG_LEVEL": "info"},
		"is_primary": true,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("add component: expected 201, got %d: %v", resp.StatusCode, body)
	}

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/workload-versions/"+versionID+"/request-publish", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("request publish: expected 200, got %d: %v", resp.StatusCode, body)
	}
	resp, body = approver.post("/api/v1/enterprises/"+tenantID+"/workload-versions/"+versionID+"/approve-publish", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("approve publish: expected 200, got %d: %v", resp.StatusCode, body)
	}
	return versionID, imageID
}

// bringDeploymentToSubmitted runs a deployment through create -> draft plan
// -> request-approval -> approve -> submit, returning the deployment id and
// the pending deploy command's message id -- the same setup
// TestDeploymentFullLifecycle uses, factored out since both that test and
// this file's attestation tests need to reach exactly this state.
func bringDeploymentToSubmitted(t *testing.T, owner, approver *client, tenantID, reservationID, namespace string, agentID, keyPEM, baseURL string) (deploymentID, messageID string) {
	t.Helper()
	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/deployments", map[string]any{
		"capacity_reservation_id": reservationID, "namespace": namespace, "replica_count": 1,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create deployment: expected 201, got %d: %v", resp.StatusCode, body)
	}
	deploymentID = str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans", nil)
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create plan: expected 201, got %d: %v", resp.StatusCode, body)
	}
	planID := str(t, body, "id")
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans/"+planID+"/request-approval", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("request plan approval: expected 200, got %d: %v", resp.StatusCode, body)
	}
	resp, body = approver.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans/"+planID+"/approve", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("approve plan: expected 200, got %d: %v", resp.StatusCode, body)
	}
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans/"+planID+"/submit", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("submit plan: expected 200, got %d: %v", resp.StatusCode, body)
	}

	messageID, _ = pollSingleDeploymentCommand(t, baseURL, agentID, keyPEM)
	return deploymentID, messageID
}

// attemptFetchSecrets is the agent-facing GET /deployments/{id}/secrets
// call, reimplemented directly (matching cmd/mockclusteragent's own
// fetchAgentSecrets) so this test can assert on its status code without
// shelling out to the CLI binary.
func attemptFetchSecrets(t *testing.T, baseURL, agentID, deploymentID, keyPEM string) (*http.Response, map[string]any) {
	t.Helper()
	nonce := fmt.Sprintf("secrets-%d", time.Now().UnixNano())
	signedAt := time.Now().UTC().Format(time.RFC3339)
	challenge := fmt.Sprintf("agent-secrets:%s:%s:%s:%s", agentID, deploymentID, nonce, signedAt)
	signature, err := pki.SignMessage(keyPEM, []byte(challenge))
	if err != nil {
		t.Fatalf("sign secrets challenge: %v", err)
	}
	req, err := http.NewRequest(http.MethodGet, baseURL+"/api/v1/cluster-agents/"+agentID+"/deployments/"+deploymentID+"/secrets", nil)
	if err != nil {
		t.Fatalf("build secrets request: %v", err)
	}
	req.Header.Set("X-Agent-Nonce", nonce)
	req.Header.Set("X-Agent-Signed-At", signedAt)
	req.Header.Set("X-Agent-Signature", signature)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("fetch secrets: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()
	var body map[string]any
	_ = json.NewDecoder(resp.Body).Decode(&body)
	return resp, body
}

// requestAttestationSessionForTest signs and posts the attestation-session
// request, reimplementing cmd/mockclusteragent's requestAttestationSession
// directly.
func requestAttestationSessionForTest(t *testing.T, anon *client, agentID, keyPEM string) (sessionID, attestationNonce string) {
	t.Helper()
	requestNonce := fmt.Sprintf("attsess-%d", time.Now().UnixNano())
	signedAt := time.Now().UTC().Format(time.RFC3339)
	challenge := fmt.Sprintf("attestation-session:%s:%s:%s", agentID, requestNonce, signedAt)
	signature, err := pki.SignMessage(keyPEM, []byte(challenge))
	if err != nil {
		t.Fatalf("sign session request: %v", err)
	}
	resp, body := anon.post("/api/v1/cluster-agents/"+agentID+"/attestation-sessions", map[string]string{
		"nonce": requestNonce, "signed_at": signedAt, "signature": signature,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("request attestation session: expected 201, got %d: %v", resp.StatusCode, body)
	}
	return str(t, body, "id"), str(t, body, "nonce")
}

// submitEvidenceForTest signs and posts an evidence submission,
// reimplementing cmd/mockclusteragent's submitAttestationEvidence
// directly.
func submitEvidenceForTest(t *testing.T, anon *client, agentID, sessionID, deploymentID, sessionNonce, keyPEM string, measurements map[string]any) (*http.Response, map[string]any) {
	t.Helper()
	rawBody, err := json.Marshal(map[string]any{
		"deployment_id": deploymentID, "provider_type": "mock", "measurements": measurements,
		"raw_evidence": `{"note":"test evidence"}`, "nonce": sessionNonce, "signed_at": rfc3339Now(),
	})
	if err != nil {
		t.Fatalf("marshal evidence: %v", err)
	}
	signature, err := pki.SignMessage(keyPEM, rawBody)
	if err != nil {
		t.Fatalf("sign evidence: %v", err)
	}
	return anon.postRaw("/api/v1/cluster-agents/"+agentID+"/attestation-sessions/"+sessionID+"/evidence", rawBody, map[string]string{"X-Agent-Signature": signature})
}

// TestAttestationKeyReleaseGate exercises Milestone 8 end to end: a
// confidential-computing-required deployment's secrets are withheld until
// a fresh attestation passes, a mismatched measurement is rejected (fail,
// secrets still withheld), a passing attestation unlocks the exact same
// secrets fetch, the operator sees the full result (including
// measurements/raw evidence), and the tenant's "customer verification
// view" sees only the redacted summary.
func TestAttestationKeyReleaseGate(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "attest-platform-admin@example.com")
	grantPlatformRole(t, store, "attest-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE Attest"})
	jurisdictionID := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-attest", "name": "ME Central Attest", "jurisdiction_id": jurisdictionID})
	regionID := str(t, body, "id")

	operatorOwner, operatorID, _ := setUpOperatorWithConfidentialComputingOffer(t, base, smtp, platformAdmin, "attest-operator", regionID)
	clusters := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/clusters")
	clusterID := clusters[0]["id"].(string)
	agentID, keyPEM, _ := registerAndBootstrapClusterAgent(t, operatorOwner, operatorID, clusterID, "attest-cluster-agent")

	expectedMeasurements := map[string]any{"platform": "mock-tee-v1", "firmware_hash": "abc123"}
	resp, body := operatorOwner.post("/api/v1/operators/"+operatorID+"/attestation-policies", map[string]any{
		"cluster_id": clusterID, "provider_type": "mock", "expected_measurements": expectedMeasurements,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create attestation policy: expected 201, got %d: %v", resp.StatusCode, body)
	}

	owner := registerVerifyAndLogin(t, base, smtp, "attest-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Attest Test Tenant", "AE")
	approver := inviteAndAcceptAdmin(t, base, smtp, owner, tenantID, "attest-tenant-approver@example.com")

	versionID, _ := setUpConfidentialComputingWorkload(t, store, owner, approver, tenantID, "attest-workload")
	reservationID := reserveCommittedCapacity(t, owner, tenantID, versionID, 1)

	deploymentID, _ := bringDeploymentToSubmitted(t, owner, approver, tenantID, reservationID, "tenant-attest-ns", agentID, keyPEM, srv.URL)

	// Secrets are withheld -- no attestation has ever run for this deployment.
	resp, body = attemptFetchSecrets(t, srv.URL, agentID, deploymentID, keyPEM)
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("fetch secrets before attestation: expected 409, got %d: %v", resp.StatusCode, body)
	}

	anon := newClient(t, srv.URL)

	// A mismatched measurement fails -- secrets remain withheld.
	sessionID, sessionNonce := requestAttestationSessionForTest(t, anon, agentID, keyPEM)
	resp, body = submitEvidenceForTest(t, anon, agentID, sessionID, deploymentID, sessionNonce, keyPEM, map[string]any{
		"platform": "mock-tee-v1", "firmware_hash": "tampered-value",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("submit mismatched evidence: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if got := body["decision"]; got != "fail" {
		t.Fatalf("expected decision fail for mismatched measurements, got %v", body)
	}
	resp, body = attemptFetchSecrets(t, srv.URL, agentID, deploymentID, keyPEM)
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("fetch secrets after failed attestation: expected 409, got %d: %v", resp.StatusCode, body)
	}

	// A passing attestation, using a fresh session (the failed one is
	// already consumed), unlocks the same secrets fetch.
	sessionID, sessionNonce = requestAttestationSessionForTest(t, anon, agentID, keyPEM)
	resp, body = submitEvidenceForTest(t, anon, agentID, sessionID, deploymentID, sessionNonce, keyPEM, expectedMeasurements)
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("submit matching evidence: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if got := body["decision"]; got != "pass" {
		t.Fatalf("expected decision pass for matching measurements, got %v", body)
	}
	resp, body = attemptFetchSecrets(t, srv.URL, agentID, deploymentID, keyPEM)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("fetch secrets after passing attestation: expected 200, got %d: %v", resp.StatusCode, body)
	}

	// Operator sees full detail (this is their own infrastructure's evidence).
	operatorResults := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/cluster-agents/"+agentID+"/attestation-results")
	if len(operatorResults) != 2 {
		t.Fatalf("expected 2 attestation results (1 fail, 1 pass), got %d", len(operatorResults))
	}
	for _, r := range operatorResults {
		if r["measurements"] == nil {
			t.Fatalf("expected the operator view to include measurements, got %v", r)
		}
		if r["raw_evidence"] == nil {
			t.Fatalf("expected the operator view to include raw_evidence, got %v", r)
		}
	}

	// Tenant's "customer verification view" sees only the redacted summary.
	tenantResults := owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/attestation-results")
	if len(tenantResults) != 2 {
		t.Fatalf("expected 2 redacted attestation results, got %d", len(tenantResults))
	}
	for _, r := range tenantResults {
		if _, ok := r["measurements"]; ok {
			t.Fatalf("tenant view must never include measurements, got %v", r)
		}
		if _, ok := r["raw_evidence"]; ok {
			t.Fatalf("tenant view must never include raw_evidence, got %v", r)
		}
		if r["decision"] == nil {
			t.Fatalf("expected the redacted view to still include decision, got %v", r)
		}
	}
}

// TestAttestationSessionRejectsReplayAndForgedSignature proves a consumed
// session cannot be reused and evidence signed with the wrong key is
// rejected, mirroring Milestone 6/7's equivalent proofs for their own
// signed channels.
func TestAttestationSessionRejectsReplayAndForgedSignature(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "attest-replay-platform-admin@example.com")
	grantPlatformRole(t, store, "attest-replay-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE Attest Replay"})
	jurisdictionID := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-attest-replay", "name": "ME Central Attest Replay", "jurisdiction_id": jurisdictionID})
	regionID := str(t, body, "id")

	operatorOwner, operatorID, _ := setUpOperatorWithConfidentialComputingOffer(t, base, smtp, platformAdmin, "attest-replay-operator", regionID)
	clusters := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/clusters")
	clusterID := clusters[0]["id"].(string)
	agentID, keyPEM, _ := registerAndBootstrapClusterAgent(t, operatorOwner, operatorID, clusterID, "attest-replay-cluster-agent")

	expectedMeasurements := map[string]any{"platform": "mock-tee-v1"}
	resp, body := operatorOwner.post("/api/v1/operators/"+operatorID+"/attestation-policies", map[string]any{
		"cluster_id": clusterID, "provider_type": "mock", "expected_measurements": expectedMeasurements,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create attestation policy: expected 201, got %d: %v", resp.StatusCode, body)
	}

	owner := registerVerifyAndLogin(t, base, smtp, "attest-replay-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Attest Replay Test Tenant", "AE")
	approver := inviteAndAcceptAdmin(t, base, smtp, owner, tenantID, "attest-replay-tenant-approver@example.com")

	versionID, _ := setUpConfidentialComputingWorkload(t, store, owner, approver, tenantID, "attest-replay-workload")
	reservationID := reserveCommittedCapacity(t, owner, tenantID, versionID, 1)
	deploymentID, _ := bringDeploymentToSubmitted(t, owner, approver, tenantID, reservationID, "tenant-attest-replay-ns", agentID, keyPEM, srv.URL)

	anon := newClient(t, srv.URL)

	// Forged signature is rejected.
	sessionID, sessionNonce := requestAttestationSessionForTest(t, anon, agentID, keyPEM)
	attackerKeyPEM, _, err := pki.GenerateKeyAndCSR("attacker")
	if err != nil {
		t.Fatalf("generate attacker key: %v", err)
	}
	resp, body = submitEvidenceForTest(t, anon, agentID, sessionID, deploymentID, sessionNonce, attackerKeyPEM, expectedMeasurements)
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("submit evidence with attacker's signature: expected 401, got %d: %v", resp.StatusCode, body)
	}

	// Legitimate submission consumes the session...
	resp, body = submitEvidenceForTest(t, anon, agentID, sessionID, deploymentID, sessionNonce, keyPEM, expectedMeasurements)
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("submit legitimate evidence: expected 201, got %d: %v", resp.StatusCode, body)
	}

	// ...so replaying the exact same session/nonce a second time must fail,
	// even with a perfectly valid signature.
	resp, body = submitEvidenceForTest(t, anon, agentID, sessionID, deploymentID, sessionNonce, keyPEM, expectedMeasurements)
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("replay consumed session: expected 409, got %d: %v", resp.StatusCode, body)
	}
}

// TestAttestationPolicyRevocationFailsClosed proves that once an
// operator's attestation policy is revoked, a subsequent evidence
// submission has no active policy to verify against and is recorded as a
// failure, not silently accepted.
func TestAttestationPolicyRevocationFailsClosed(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "attest-revoke-platform-admin@example.com")
	grantPlatformRole(t, store, "attest-revoke-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE Attest Revoke"})
	jurisdictionID := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-attest-revoke", "name": "ME Central Attest Revoke", "jurisdiction_id": jurisdictionID})
	regionID := str(t, body, "id")

	operatorOwner, operatorID, _ := setUpOperatorWithConfidentialComputingOffer(t, base, smtp, platformAdmin, "attest-revoke-operator", regionID)
	clusters := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/clusters")
	clusterID := clusters[0]["id"].(string)
	agentID, keyPEM, _ := registerAndBootstrapClusterAgent(t, operatorOwner, operatorID, clusterID, "attest-revoke-cluster-agent")

	expectedMeasurements := map[string]any{"platform": "mock-tee-v1"}
	resp, body := operatorOwner.post("/api/v1/operators/"+operatorID+"/attestation-policies", map[string]any{
		"cluster_id": clusterID, "provider_type": "mock", "expected_measurements": expectedMeasurements,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create attestation policy: expected 201, got %d: %v", resp.StatusCode, body)
	}
	policyID := str(t, body, "id")

	owner := registerVerifyAndLogin(t, base, smtp, "attest-revoke-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Attest Revoke Test Tenant", "AE")
	approver := inviteAndAcceptAdmin(t, base, smtp, owner, tenantID, "attest-revoke-tenant-approver@example.com")

	versionID, _ := setUpConfidentialComputingWorkload(t, store, owner, approver, tenantID, "attest-revoke-workload")
	reservationID := reserveCommittedCapacity(t, owner, tenantID, versionID, 1)
	deploymentID, _ := bringDeploymentToSubmitted(t, owner, approver, tenantID, reservationID, "tenant-attest-revoke-ns", agentID, keyPEM, srv.URL)

	resp, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/attestation-policies/"+policyID+"/revoke", map[string]string{"reason": "cluster decommissioned"})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("revoke policy: expected 200, got %d: %v", resp.StatusCode, body)
	}

	anon := newClient(t, srv.URL)
	sessionID, sessionNonce := requestAttestationSessionForTest(t, anon, agentID, keyPEM)
	resp, body = submitEvidenceForTest(t, anon, agentID, sessionID, deploymentID, sessionNonce, keyPEM, expectedMeasurements)
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("submit evidence with no active policy: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if got := body["decision"]; got != "fail" {
		t.Fatalf("expected decision fail with no active policy, got %v", body)
	}
	reasonCodes, _ := body["reason_codes"].([]any)
	if len(reasonCodes) != 1 || reasonCodes[0] != "NO_ACTIVE_POLICY" {
		t.Fatalf("expected exactly one NO_ACTIVE_POLICY reason code, got %v", reasonCodes)
	}
}
