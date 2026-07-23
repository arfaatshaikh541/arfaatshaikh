package app_test

import (
	"encoding/json"
	"fmt"
	"net/http"
	"testing"
	"time"

	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/pki"
)

// setUpDeployableWorkload builds a published workload version with one
// component (referencing an approved, digest-pinned image) and one health
// check -- everything CreatePlan's manifest snapshot needs -- reusing the
// same licence/image/model fixtures workloads_flow_test.go and
// placement_flow_test.go already establish.
func setUpDeployableWorkload(t *testing.T, store *dbpkg.Store, owner, approver *client, tenantID, seed string) (versionID, imageID string) {
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
	componentID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/workload-components/"+componentID+"/health-checks", map[string]any{
		"check_type": "http", "path": "/healthz", "interval_seconds": 10, "timeout_seconds": 2, "failure_threshold": 3,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("add health check: expected 201, got %d: %v", resp.StatusCode, body)
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

// reserveCommittedCapacity runs a real (non-simulated) placement evaluation
// against a workload version with deployment_approval_required=false, which
// auto-commits the resulting reservation -- exactly the precondition
// CreateDeployment requires.
func reserveCommittedCapacity(t *testing.T, owner *client, tenantID, versionID string, quantity int) (reservationID string) {
	t.Helper()
	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/placement-requests", map[string]any{
		"workload_version_id": versionID, "quantity": quantity, "simulate": false,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("evaluate placement: expected 201, got %d: %v", resp.StatusCode, body)
	}
	reservation, ok := body["reservation"].(map[string]any)
	if !ok {
		t.Fatalf("expected a committed reservation, got %v", body["reservation"])
	}
	if got := reservation["status"]; got != "committed" {
		t.Fatalf("expected reservation status committed, got %v", got)
	}
	return reservation["id"].(string)
}

// deploymentCommandResultBody signs a command-result body with the agent's
// key, mirroring exactly what cmd/mockclusteragent's real execution loop
// will eventually do (Task 66) -- reimplemented here so this test does not
// depend on that CLI existing yet.
func deploymentCommandResultBody(t *testing.T, keyPEM, action string, success bool, detail, nonce string) ([]byte, string) {
	t.Helper()
	raw, err := json.Marshal(map[string]any{
		"action": action, "success": success, "detail": detail, "nonce": nonce, "signed_at": rfc3339Now(),
	})
	if err != nil {
		t.Fatalf("marshal command result: %v", err)
	}
	signature, err := pki.SignMessage(keyPEM, raw)
	if err != nil {
		t.Fatalf("sign command result: %v", err)
	}
	return raw, signature
}

// pollSingleDeploymentCommand polls for pending control messages and
// asserts exactly one deployment_command is pending, returning its id and
// decoded payload.
func pollSingleDeploymentCommand(t *testing.T, baseURL, agentID, keyPEM string) (messageID string, payload map[string]any) {
	t.Helper()
	pending := pollPendingMessagesForTest(t, baseURL, agentID, keyPEM)
	if len(pending) != 1 {
		t.Fatalf("expected exactly 1 pending control message, got %d", len(pending))
	}
	if err := json.Unmarshal(pending[0].Payload, &payload); err != nil {
		t.Fatalf("decode command payload: %v", err)
	}
	return pending[0].ID, payload
}

// TestDeploymentFullLifecycle exercises Milestone 7 end to end: create a
// deployment from a committed reservation, draft/approve/submit a signed
// plan, receive it as a deployment_command over the Milestone 6 control
// channel, report a signed success result, scale, pause, resume, and
// terminate -- each an independent signed command/result round trip -- and
// confirms the append-only event stream recorded every step.
func TestDeploymentFullLifecycle(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "deploy-platform-admin@example.com")
	grantPlatformRole(t, store, "deploy-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE Deploy"})
	regionJurisdiction := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-deploy", "name": "Middle East Central Deploy", "jurisdiction_id": regionJurisdiction})
	regionID := str(t, body, "id")

	operatorOwner, operatorID, _ := setUpOperatorWithOffer(t, base, smtp, platformAdmin, "deploy-operator", regionID, 10, 2.00)

	// Resolve the cluster this operator's offer runs on so a cluster agent
	// can be registered against it.
	clusters := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/clusters")
	if len(clusters) != 1 {
		t.Fatalf("expected 1 cluster, got %d", len(clusters))
	}
	clusterID := clusters[0]["id"].(string)
	agentID, keyPEM, _ := registerAndBootstrapClusterAgent(t, operatorOwner, operatorID, clusterID, "deploy-cluster-agent")

	owner := registerVerifyAndLogin(t, base, smtp, "deploy-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Deploy Test Tenant", "AE")
	approver := inviteAndAcceptAdmin(t, base, smtp, owner, tenantID, "deploy-tenant-approver@example.com")

	versionID, _ := setUpDeployableWorkload(t, store, owner, approver, tenantID, "deploy-workload")
	reservationID := reserveCommittedCapacity(t, owner, tenantID, versionID, 2)

	// --- Create deployment ---
	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/deployments", map[string]any{
		"capacity_reservation_id": reservationID, "namespace": "tenant-fictional-ns", "replica_count": 2,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create deployment: expected 201, got %d: %v", resp.StatusCode, body)
	}
	deploymentID := str(t, body, "id")
	if got := body["status"]; got != "pending_plan_approval" {
		t.Fatalf("expected initial status pending_plan_approval, got %v", got)
	}

	// A second deployment against the same reservation must be rejected.
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/deployments", map[string]any{
		"capacity_reservation_id": reservationID, "namespace": "tenant-fictional-ns", "replica_count": 2,
	})
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("duplicate deployment for the same reservation: expected 409, got %d: %v", resp.StatusCode, body)
	}

	// --- Draft, approve, submit plan ---
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans", nil)
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create plan: expected 201, got %d: %v", resp.StatusCode, body)
	}
	planID := str(t, body, "id")
	manifest, ok := body["manifest"].(map[string]any)
	if !ok {
		t.Fatalf("expected a manifest, got %v", body["manifest"])
	}
	components, ok := manifest["components"].([]any)
	if !ok || len(components) != 1 {
		t.Fatalf("expected 1 component in the manifest, got %v", manifest["components"])
	}
	if body["manifest_hash"] == "" {
		t.Fatalf("expected a non-empty manifest_hash")
	}
	if body["signature"] != nil {
		t.Fatalf("expected no signature before approval, got %v", body["signature"])
	}

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans/"+planID+"/request-approval", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("request plan approval: expected 200, got %d: %v", resp.StatusCode, body)
	}

	// Self-approval must be rejected (dual control).
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans/"+planID+"/approve", nil)
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("self-approve plan: expected 403, got %d: %v", resp.StatusCode, body)
	}

	resp, body = approver.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans/"+planID+"/approve", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("approve plan: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if body["signature"] == nil || body["signature"] == "" {
		t.Fatalf("expected a non-empty signature after approval, got %v", body["signature"])
	}

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans/"+planID+"/submit", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("submit plan: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "submitted" {
		t.Fatalf("expected deployment status submitted, got %v", got)
	}

	// --- Agent polls, verifies, executes (fictionally), reports success ---
	_, body = platformAdmin.get("/api/v1/platform-ca/certificate")
	caCertPEM := str(t, body, "certificate_pem")

	messageID, payload := pollSingleDeploymentCommand(t, srv.URL, agentID, keyPEM)
	if got := payload["action"]; got != "deploy" {
		t.Fatalf("expected action deploy, got %v", got)
	}
	pending := pollPendingMessagesForTest(t, srv.URL, agentID, keyPEM)
	valid, err := pki.VerifySignature(caCertPEM, pending[0].Payload, pending[0].Signature)
	if err != nil || !valid {
		t.Fatalf("expected the deploy command's signature to verify against the CA's certificate, valid=%v err=%v", valid, err)
	}

	// The agent also fetches decrypted secret values for this deployment --
	// there are none configured in this test, so an empty map is correct;
	// what matters is that the signed, certificate-authenticated fetch
	// itself succeeds.
	secretsNonce := fmt.Sprintf("secrets-%d", time.Now().UnixNano())
	secretsSignedAt := time.Now().UTC().Format(time.RFC3339)
	secretsChallenge := fmt.Sprintf("agent-secrets:%s:%s:%s:%s", agentID, deploymentID, secretsNonce, secretsSignedAt)
	secretsSignature, err := pki.SignMessage(keyPEM, []byte(secretsChallenge))
	if err != nil {
		t.Fatalf("sign secrets challenge: %v", err)
	}
	req, err := http.NewRequest(http.MethodGet, srv.URL+"/api/v1/cluster-agents/"+agentID+"/deployments/"+deploymentID+"/secrets", nil)
	if err != nil {
		t.Fatalf("build secrets request: %v", err)
	}
	req.Header.Set("X-Agent-Nonce", secretsNonce)
	req.Header.Set("X-Agent-Signed-At", secretsSignedAt)
	req.Header.Set("X-Agent-Signature", secretsSignature)
	secretsResp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("fetch agent secrets: %v", err)
	}
	defer func() { _ = secretsResp.Body.Close() }()
	if secretsResp.StatusCode != http.StatusOK {
		t.Fatalf("fetch agent secrets: expected 200, got %d", secretsResp.StatusCode)
	}

	resultBody, resultSig := deploymentCommandResultBody(t, keyPEM, "deploy", true, "deployed 2 replicas", "deploy-result-1")
	anon := newClient(t, srv.URL)
	resp, body = anon.postRaw("/api/v1/cluster-agents/"+agentID+"/control-messages/"+messageID+"/command-result", resultBody, map[string]string{"X-Agent-Signature": resultSig})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("report deploy result: expected 201, got %d: %v", resp.StatusCode, body)
	}

	resp, body = owner.get("/api/v1/enterprises/" + tenantID + "/deployments/" + deploymentID)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("get deployment: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "running" {
		t.Fatalf("expected deployment status running after successful deploy, got %v", got)
	}

	plans := owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans")
	var activeFound bool
	for _, p := range plans {
		if p["id"] == planID && p["status"] == "active" {
			activeFound = true
		}
	}
	if !activeFound {
		t.Fatalf("expected the submitted plan to become active, got %v", plans)
	}

	// --- Scale ---
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/scale", map[string]any{"replica_count": 4})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("scale: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "scaling" {
		t.Fatalf("expected status scaling, got %v", got)
	}
	scaleMsgID, scalePayload := pollSingleDeploymentCommand(t, srv.URL, agentID, keyPEM)
	if got := scalePayload["replica_count"]; got != float64(4) {
		t.Fatalf("expected scale command replica_count 4, got %v", got)
	}
	scaleResultBody, scaleResultSig := deploymentCommandResultBody(t, keyPEM, "scale", true, "scaled to 4", "scale-result-1")
	resp, body = anon.postRaw("/api/v1/cluster-agents/"+agentID+"/control-messages/"+scaleMsgID+"/command-result", scaleResultBody, map[string]string{"X-Agent-Signature": scaleResultSig})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("report scale result: expected 201, got %d: %v", resp.StatusCode, body)
	}
	resp, body = owner.get("/api/v1/enterprises/" + tenantID + "/deployments/" + deploymentID)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("get deployment after scale: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "running" {
		t.Fatalf("expected status running after scale success, got %v", got)
	}
	if got := body["replica_count"]; got != float64(4) {
		t.Fatalf("expected replica_count 4 after scale success, got %v", got)
	}

	// --- Pause / Resume ---
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/pause", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("pause: expected 200, got %d: %v", resp.StatusCode, body)
	}
	pauseMsgID, _ := pollSingleDeploymentCommand(t, srv.URL, agentID, keyPEM)
	pauseResultBody, pauseResultSig := deploymentCommandResultBody(t, keyPEM, "pause", true, "paused", "pause-result-1")
	resp, body = anon.postRaw("/api/v1/cluster-agents/"+agentID+"/control-messages/"+pauseMsgID+"/command-result", pauseResultBody, map[string]string{"X-Agent-Signature": pauseResultSig})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("report pause result: expected 201, got %d: %v", resp.StatusCode, body)
	}
	resp, body = owner.get("/api/v1/enterprises/" + tenantID + "/deployments/" + deploymentID)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("get deployment after pause: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "paused" {
		t.Fatalf("expected status paused, got %v", got)
	}

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/resume", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("resume: expected 200, got %d: %v", resp.StatusCode, body)
	}
	resumeMsgID, _ := pollSingleDeploymentCommand(t, srv.URL, agentID, keyPEM)
	resumeResultBody, resumeResultSig := deploymentCommandResultBody(t, keyPEM, "resume", true, "resumed", "resume-result-1")
	resp, body = anon.postRaw("/api/v1/cluster-agents/"+agentID+"/control-messages/"+resumeMsgID+"/command-result", resumeResultBody, map[string]string{"X-Agent-Signature": resumeResultSig})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("report resume result: expected 201, got %d: %v", resp.StatusCode, body)
	}
	resp, body = owner.get("/api/v1/enterprises/" + tenantID + "/deployments/" + deploymentID)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("get deployment after resume: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "running" {
		t.Fatalf("expected status running after resume success, got %v", got)
	}

	// --- Terminate ---
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/terminate", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("terminate: expected 200, got %d: %v", resp.StatusCode, body)
	}
	terminateMsgID, _ := pollSingleDeploymentCommand(t, srv.URL, agentID, keyPEM)
	terminateResultBody, terminateResultSig := deploymentCommandResultBody(t, keyPEM, "terminate", true, "terminated", "terminate-result-1")
	resp, body = anon.postRaw("/api/v1/cluster-agents/"+agentID+"/control-messages/"+terminateMsgID+"/command-result", terminateResultBody, map[string]string{"X-Agent-Signature": terminateResultSig})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("report terminate result: expected 201, got %d: %v", resp.StatusCode, body)
	}
	resp, body = owner.get("/api/v1/enterprises/" + tenantID + "/deployments/" + deploymentID)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("get deployment after terminate: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "terminated" {
		t.Fatalf("expected status terminated, got %v", got)
	}

	// --- Event stream recorded every step, and the operator can see it too ---
	events := owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/events")
	wantEventTypes := map[string]bool{
		"deployment_created": false, "plan_drafted": false, "plan_approval_requested": false,
		"plan_approved": false, "plan_submitted": false, "scale_requested": false,
		"pause_requested": false, "resume_requested": false, "terminate_requested": false,
	}
	for _, e := range events {
		if _, ok := wantEventTypes[e["event_type"].(string)]; ok {
			wantEventTypes[e["event_type"].(string)] = true
		}
	}
	for eventType, found := range wantEventTypes {
		if !found {
			t.Fatalf("expected event type %q in the event stream, got %v", eventType, events)
		}
	}
	var commandResultCount int
	for _, e := range events {
		et := e["event_type"].(string)
		if len(et) >= len("command_result:") && et[:len("command_result:")] == "command_result:" {
			commandResultCount++
			if e["actor_user_id"] != nil {
				t.Fatalf("expected agent-reported events to have no actor_user_id, got %v", e)
			}
		}
	}
	if commandResultCount != 5 {
		t.Fatalf("expected 5 agent-reported command_result events (deploy/scale/pause/resume/terminate), got %d", commandResultCount)
	}

	operatorEvents := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/deployments/"+deploymentID+"/events")
	if len(operatorEvents) != len(events) {
		t.Fatalf("expected the operator to see the same event stream, got %d vs %d", len(operatorEvents), len(events))
	}
}

// TestDeploymentCommandResultRejectsInvalidSignature proves a command
// result signed with the wrong (attacker-controlled) key is rejected rather
// than silently trusted, exactly Milestone 6's equivalent proof for plan
// validation responses.
func TestDeploymentCommandResultRejectsInvalidSignature(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "deploy-badsig-platform-admin@example.com")
	grantPlatformRole(t, store, "deploy-badsig-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE Deploy Badsig"})
	jurisdictionID := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-deploy-badsig", "name": "ME Central Deploy Badsig", "jurisdiction_id": jurisdictionID})
	regionID := str(t, body, "id")

	operatorOwner, operatorID, _ := setUpOperatorWithOffer(t, base, smtp, platformAdmin, "deploy-badsig-operator", regionID, 10, 2.00)
	clusters := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/clusters")
	clusterID := clusters[0]["id"].(string)
	agentID, keyPEM, _ := registerAndBootstrapClusterAgent(t, operatorOwner, operatorID, clusterID, "deploy-badsig-cluster-agent")

	owner := registerVerifyAndLogin(t, base, smtp, "deploy-badsig-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Deploy Badsig Test Tenant", "AE")
	approver := inviteAndAcceptAdmin(t, base, smtp, owner, tenantID, "deploy-badsig-tenant-approver@example.com")

	versionID, _ := setUpDeployableWorkload(t, store, owner, approver, tenantID, "deploy-badsig-workload")
	reservationID := reserveCommittedCapacity(t, owner, tenantID, versionID, 1)

	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/deployments", map[string]any{
		"capacity_reservation_id": reservationID, "namespace": "tenant-badsig-ns", "replica_count": 1,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create deployment: expected 201, got %d: %v", resp.StatusCode, body)
	}
	deploymentID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans", nil)
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create plan: expected 201, got %d: %v", resp.StatusCode, body)
	}
	planID := str(t, body, "id")
	owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans/"+planID+"/request-approval", nil)
	approver.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans/"+planID+"/approve", nil)
	owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans/"+planID+"/submit", nil)

	messageID, _ := pollSingleDeploymentCommand(t, srv.URL, agentID, keyPEM)

	attackerKeyPEM, _, err := pki.GenerateKeyAndCSR("attacker")
	if err != nil {
		t.Fatalf("generate attacker key: %v", err)
	}
	resultBody, badSignature := deploymentCommandResultBody(t, attackerKeyPEM, "deploy", true, "deployed", "attacker-nonce-1")

	anon := newClient(t, srv.URL)
	resp, body = anon.postRaw("/api/v1/cluster-agents/"+agentID+"/control-messages/"+messageID+"/command-result", resultBody, map[string]string{"X-Agent-Signature": badSignature})
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("report result with attacker's signature: expected 401, got %d: %v", resp.StatusCode, body)
	}

	resp, body = owner.get("/api/v1/enterprises/" + tenantID + "/deployments/" + deploymentID)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("get deployment: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "submitted" {
		t.Fatalf("expected deployment status to remain submitted after a rejected forged result, got %v", got)
	}
}

// TestDeploymentCommandResultRejectsReplayedNonce proves a captured, validly
// signed command result cannot be replayed with the same nonce against a
// second command to fabricate a second recorded outcome.
func TestDeploymentCommandResultRejectsReplayedNonce(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "deploy-replay-platform-admin@example.com")
	grantPlatformRole(t, store, "deploy-replay-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE Deploy Replay"})
	jurisdictionID := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-deploy-replay", "name": "ME Central Deploy Replay", "jurisdiction_id": jurisdictionID})
	regionID := str(t, body, "id")

	operatorOwner, operatorID, _ := setUpOperatorWithOffer(t, base, smtp, platformAdmin, "deploy-replay-operator", regionID, 10, 2.00)
	clusters := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/clusters")
	clusterID := clusters[0]["id"].(string)
	agentID, keyPEM, _ := registerAndBootstrapClusterAgent(t, operatorOwner, operatorID, clusterID, "deploy-replay-cluster-agent")

	owner := registerVerifyAndLogin(t, base, smtp, "deploy-replay-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Deploy Replay Test Tenant", "AE")
	approver := inviteAndAcceptAdmin(t, base, smtp, owner, tenantID, "deploy-replay-tenant-approver@example.com")

	versionID, _ := setUpDeployableWorkload(t, store, owner, approver, tenantID, "deploy-replay-workload")
	reservationID := reserveCommittedCapacity(t, owner, tenantID, versionID, 1)

	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/deployments", map[string]any{
		"capacity_reservation_id": reservationID, "namespace": "tenant-replay-ns", "replica_count": 1,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create deployment: expected 201, got %d: %v", resp.StatusCode, body)
	}
	deploymentID := str(t, body, "id")
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans", nil)
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create plan: expected 201, got %d: %v", resp.StatusCode, body)
	}
	planID := str(t, body, "id")
	owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans/"+planID+"/request-approval", nil)
	approver.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans/"+planID+"/approve", nil)
	owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/plans/"+planID+"/submit", nil)

	messageID, _ := pollSingleDeploymentCommand(t, srv.URL, agentID, keyPEM)
	resultBody, signature := deploymentCommandResultBody(t, keyPEM, "deploy", true, "deployed", "fixed-nonce")

	anon := newClient(t, srv.URL)
	resp, body = anon.postRaw("/api/v1/cluster-agents/"+agentID+"/control-messages/"+messageID+"/command-result", resultBody, map[string]string{"X-Agent-Signature": signature})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("first report: expected 201, got %d: %v", resp.StatusCode, body)
	}

	// Scale the now-running deployment to get a second pending command, then
	// try to replay the exact same (body, signature) pair against it.
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/deployments/"+deploymentID+"/scale", map[string]any{"replica_count": 2})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("scale: expected 200, got %d: %v", resp.StatusCode, body)
	}
	secondMessageID, _ := pollSingleDeploymentCommand(t, srv.URL, agentID, keyPEM)
	resp, body = anon.postRaw("/api/v1/cluster-agents/"+agentID+"/control-messages/"+secondMessageID+"/command-result", resultBody, map[string]string{"X-Agent-Signature": signature})
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("replayed nonce against a second command: expected 409, got %d: %v", resp.StatusCode, body)
	}
}
