package app_test

import (
	"encoding/json"
	"net/http"
	"testing"

	"gridkeep/control-api/internal/platform/pki"
	"gridkeep/control-api/internal/testutil"
)

// setUpOperatorWithNetworkOffer builds an active operator with one data
// centre, one cluster (with a bootstrapped, active cluster agent), one
// network capability at that data centre, and a published network service
// offer against that capability -- everything EvaluateAndReserve's
// location-based cluster-agent resolution chain
// (network_capabilities -> clusters -> cluster_agents, joined on a shared
// data_centre_id) needs to find an agent to provision against.
func setUpOperatorWithNetworkOffer(t *testing.T, base httpTestServer, smtp *testutil.FakeSMTPServer, platformAdmin *client, seed, regionID string, totalBandwidthGbps, pricePerUnitHour float64) (owner *client, operatorID, offerID, agentID, keyPEM string) {
	t.Helper()
	owner = registerVerifyAndLogin(t, base, smtp, seed+"-owner@example.com")
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

	agentID, keyPEM, certPEM := registerAndBootstrapClusterAgent(t, owner, operatorID, clusterID, seed+"-cluster-agent-1")
	if certPEM == "" {
		t.Fatalf("expected a non-empty issued certificate")
	}

	resp, body = owner.post("/api/v1/operators/"+operatorID+"/network-capabilities", map[string]any{
		"data_centre_id": dataCentreID, "capability_type": "private_5g",
		"bandwidth_gbps": totalBandwidthGbps, "estimated_latency_ms": 8.0,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create network capability: expected 201, got %d: %v", resp.StatusCode, body)
	}
	capabilityID := str(t, body, "id")

	resp, body = owner.post("/api/v1/operators/"+operatorID+"/network-service-offers", map[string]any{
		"network_capability_id": capabilityID, "service_class": "private-5g-standard",
		"total_bandwidth_gbps": totalBandwidthGbps, "max_latency_ms": 10.0,
		"price_per_unit_hour": pricePerUnitHour, "currency": "USD",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create network service offer: expected 201, got %d: %v", resp.StatusCode, body)
	}
	return owner, operatorID, str(t, body, "id"), agentID, keyPEM
}

// networkProvisionResultBody signs a network-provision-result body with the
// agent's key, mirroring exactly what cmd/mockclusteragent's real execution
// loop does.
func networkProvisionResultBody(t *testing.T, keyPEM, action, reservationID string, success bool, detail, nonce string) ([]byte, string) {
	t.Helper()
	raw, err := json.Marshal(map[string]any{
		"action": action, "reservation_id": reservationID, "success": success, "detail": detail,
		"nonce": nonce, "signed_at": rfc3339Now(),
	})
	if err != nil {
		t.Fatalf("marshal network provision result: %v", err)
	}
	signature, err := pki.SignMessage(keyPEM, raw)
	if err != nil {
		t.Fatalf("sign network provision result: %v", err)
	}
	return raw, signature
}

// pollSingleNetworkProvisionCommand polls for pending control messages and
// asserts exactly one network_service_provision is pending, returning its
// id and decoded payload.
func pollSingleNetworkProvisionCommand(t *testing.T, baseURL, agentID, keyPEM string) (messageID string, payload map[string]any) {
	t.Helper()
	pending := pollPendingMessagesForTest(t, baseURL, agentID, keyPEM)
	if len(pending) != 1 {
		t.Fatalf("expected exactly 1 pending control message, got %d", len(pending))
	}
	if err := json.Unmarshal(pending[0].Payload, &payload); err != nil {
		t.Fatalf("decode network provision payload: %v", err)
	}
	return pending[0].ID, payload
}

func assertNetworkOfferAvailableBandwidth(t *testing.T, offers []map[string]any, offerID string, want float64) {
	t.Helper()
	for _, o := range offers {
		if o["id"] == offerID {
			if o["available_bandwidth_gbps"].(float64) != want {
				t.Fatalf("expected available_bandwidth_gbps %v for offer %s, got %v", want, offerID, o["available_bandwidth_gbps"])
			}
			return
		}
	}
	t.Fatalf("offer %s not found", offerID)
}

// TestNetworkServiceEvaluateReserveProvisionAndCancel exercises Milestone
// 9's full round trip end to end, with real cryptography on the agent side:
// a tenant evaluates and reserves a network service, control-api resolves
// the cluster agent from the winning offer's network capability's location
// and sends it a signed network_service_provision command, the (test-side,
// standing in for cmd/mockclusteragent) agent applies it to the mock
// network adapter and signs back a success result, and cancelling the
// reservation releases the bandwidth and sends a signed release command.
func TestNetworkServiceEvaluateReserveProvisionAndCancel(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "netsvc-platform-admin@example.com")
	grantPlatformRole(t, store, "netsvc-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE"})
	aeJurisdiction := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-netsvc", "name": "Middle East Central", "jurisdiction_id": aeJurisdiction})
	aeRegionID := str(t, body, "id")

	operatorOwner, operatorID, offerID, agentID, keyPEM := setUpOperatorWithNetworkOffer(t, base, smtp, platformAdmin, "netsvc-operator", aeRegionID, 100, 2.00)

	anon := newClient(t, srv.URL)
	resp, body := anon.get("/api/v1/platform-ca/certificate")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("fetch CA certificate: expected 200, got %d: %v", resp.StatusCode, body)
	}
	caCertPEM := str(t, body, "certificate_pem")

	owner := registerVerifyAndLogin(t, base, smtp, "netsvc-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Network Services Test Tenant", "AE")

	offers := owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/network-service-offers")
	if len(offers) != 1 {
		t.Fatalf("expected 1 visible network service offer, got %d", len(offers))
	}

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/network-service-requests", map[string]any{
		"required_bandwidth_gbps": 40.0, "simulate": false,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("evaluate network service: expected 201, got %d: %v", resp.StatusCode, body)
	}
	requestBody := body["request"].(map[string]any)
	if got := requestBody["status"]; got != "reserved" {
		t.Fatalf("expected request status reserved, got %v", got)
	}
	evaluations, ok := body["evaluations"].([]any)
	if !ok || len(evaluations) != 1 {
		t.Fatalf("expected 1 evaluation, got %v", body["evaluations"])
	}
	if eval := evaluations[0].(map[string]any); eval["decision"] != "eligible" {
		t.Fatalf("expected eligible evaluation, got %v", eval)
	}

	reservation, ok := body["reservation"].(map[string]any)
	if !ok {
		t.Fatalf("expected a reservation in the response, got %v", body["reservation"])
	}
	reservationID := reservation["id"].(string)
	if got := reservation["status"]; got != "committed" {
		t.Fatalf("expected reservation status committed (no dual-control on network reservations), got %v", got)
	}
	if got := reservation["estimated_cost"]; got != 80.0 {
		t.Fatalf("expected estimated cost 80 (40 * 2.00), got %v", got)
	}
	if got := reservation["provisioning_status"]; got != "pending" {
		t.Fatalf("expected provisioning_status pending immediately after commit, got %v", got)
	}

	offers = operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/network-service-offers")
	assertNetworkOfferAvailableBandwidth(t, offers, offerID, 60)

	// The cluster agent polls for its pending provisioning command, verifies
	// the platform CA's signature, applies it to the mock network adapter,
	// and reports a signed success result -- the exact round trip
	// cmd/mockclusteragent's real execution loop performs.
	messageID, payload := pollSingleNetworkProvisionCommand(t, srv.URL, agentID, keyPEM)
	if got := payload["action"]; got != "provision" {
		t.Fatalf("expected action provision, got %v", got)
	}
	if got := payload["reservation_id"]; got != reservationID {
		t.Fatalf("expected reservation_id %s, got %v", reservationID, got)
	}

	pending := pollPendingMessagesForTest(t, srv.URL, agentID, keyPEM)
	valid, err := pki.VerifySignature(caCertPEM, pending[0].Payload, pending[0].Signature)
	if err != nil || !valid {
		t.Fatalf("expected the provision command's signature to verify against the platform CA, err=%v valid=%v", err, valid)
	}

	resultBody, resultSig := networkProvisionResultBody(t, keyPEM, "provision", reservationID, true, "provisioned 40.00 Gbps", "provision-result-1")
	resp, body = anon.postRaw("/api/v1/cluster-agents/"+agentID+"/control-messages/"+messageID+"/network-provision-result", resultBody, map[string]string{"X-Agent-Signature": resultSig})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("report network provision result: expected 201, got %d: %v", resp.StatusCode, body)
	}

	reservations := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/network-reservations")
	if len(reservations) != 1 || reservations[0]["provisioning_status"] != "provisioned" {
		t.Fatalf("expected 1 reservation with provisioning_status provisioned, got %v", reservations)
	}

	healthEvents := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/network-health-events")
	foundProvisionSucceeded := false
	for _, e := range healthEvents {
		if e["event_type"] == "provision_succeeded" {
			foundProvisionSucceeded = true
		}
	}
	if !foundProvisionSucceeded {
		t.Fatalf("expected a provision_succeeded health event, got %v", healthEvents)
	}

	// Cancelling releases the bandwidth immediately and sends a signed
	// release command to the same cluster agent.
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/network-reservations/"+reservationID+"/cancel", map[string]string{"reason": "no longer needed"})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("cancel reservation: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "released" {
		t.Fatalf("expected reservation status released, got %v", got)
	}

	offers = operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/network-service-offers")
	assertNetworkOfferAvailableBandwidth(t, offers, offerID, 100)

	releaseMessageID, releasePayload := pollSingleNetworkProvisionCommand(t, srv.URL, agentID, keyPEM)
	if got := releasePayload["action"]; got != "release" {
		t.Fatalf("expected action release, got %v", got)
	}
	releaseResultBody, releaseResultSig := networkProvisionResultBody(t, keyPEM, "release", reservationID, true, "released", "provision-result-2")
	resp, body = anon.postRaw("/api/v1/cluster-agents/"+agentID+"/control-messages/"+releaseMessageID+"/network-provision-result", releaseResultBody, map[string]string{"X-Agent-Signature": releaseResultSig})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("report network release result: expected 201, got %d: %v", resp.StatusCode, body)
	}

	healthEvents = operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/network-health-events")
	foundReleaseSucceeded := false
	for _, e := range healthEvents {
		if e["event_type"] == "release_succeeded" {
			foundReleaseSucceeded = true
		}
	}
	if !foundReleaseSucceeded {
		t.Fatalf("expected a release_succeeded health event, got %v", healthEvents)
	}

	tenantHealthEvents := owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/network-health-events")
	if len(tenantHealthEvents) != 2 {
		t.Fatalf("expected the tenant to see both health events for its own reservation, got %d", len(tenantHealthEvents))
	}
}

// TestNetworkServiceEvaluateRejectsInsufficientBandwidth proves a request
// for more bandwidth than any offer has available is evaluated (with a
// clear INSUFFICIENT_BANDWIDTH reason code) but never reserved.
func TestNetworkServiceEvaluateRejectsInsufficientBandwidth(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "netsvc-insuff-platform-admin@example.com")
	grantPlatformRole(t, store, "netsvc-insuff-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE"})
	aeJurisdiction := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-netsvc-insuff", "name": "Middle East Central", "jurisdiction_id": aeJurisdiction})
	aeRegionID := str(t, body, "id")

	setUpOperatorWithNetworkOffer(t, base, smtp, platformAdmin, "netsvc-insuff-operator", aeRegionID, 10, 2.00)

	owner := registerVerifyAndLogin(t, base, smtp, "netsvc-insuff-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Network Services Insufficient Test Tenant", "AE")

	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/network-service-requests", map[string]any{
		"required_bandwidth_gbps": 50.0, "simulate": false,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("evaluate network service: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if body["reservation"] != nil {
		t.Fatalf("expected no reservation when no offer has enough bandwidth, got %v", body["reservation"])
	}
	evaluations := body["evaluations"].([]any)
	if len(evaluations) != 1 {
		t.Fatalf("expected 1 evaluation, got %d", len(evaluations))
	}
	eval := evaluations[0].(map[string]any)
	if got := eval["decision"]; got != "rejected" {
		t.Fatalf("expected rejected decision, got %v", got)
	}
	reasons := eval["reason_codes"].([]any)
	found := false
	for _, r := range reasons {
		if r == "INSUFFICIENT_BANDWIDTH" {
			found = true
		}
	}
	if !found {
		t.Fatalf("expected INSUFFICIENT_BANDWIDTH reason code, got %v", reasons)
	}
}

// TestNetworkServiceSimulateDoesNotReserveBandwidth proves simulate=true
// runs the full evaluation/ranking/explanation pipeline without ever
// touching available_bandwidth_gbps or creating a reservation.
func TestNetworkServiceSimulateDoesNotReserveBandwidth(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "netsvc-sim-platform-admin@example.com")
	grantPlatformRole(t, store, "netsvc-sim-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE"})
	aeJurisdiction := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-netsvc-sim", "name": "Middle East Central", "jurisdiction_id": aeJurisdiction})
	aeRegionID := str(t, body, "id")

	operatorOwner, operatorID, offerID, _, _ := setUpOperatorWithNetworkOffer(t, base, smtp, platformAdmin, "netsvc-sim-operator", aeRegionID, 20, 3.00)

	owner := registerVerifyAndLogin(t, base, smtp, "netsvc-sim-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Network Services Sim Test Tenant", "AE")

	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/network-service-requests", map[string]any{
		"required_bandwidth_gbps": 5.0, "simulate": true,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("simulate network service: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if body["reservation"] != nil {
		t.Fatalf("simulate=true must not create a reservation, got %v", body["reservation"])
	}
	requestBody := body["request"].(map[string]any)
	if got := requestBody["status"]; got != "evaluated" {
		t.Fatalf("expected request status evaluated (not reserved), got %v", got)
	}

	offers := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/network-service-offers")
	assertNetworkOfferAvailableBandwidth(t, offers, offerID, 20)
}
