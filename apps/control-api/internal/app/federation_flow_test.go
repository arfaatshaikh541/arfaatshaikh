package app_test

import (
	"encoding/json"
	"net/http"
	"testing"

	"gridkeep/control-api/internal/platform/pki"
)

// TestFederatedCapacityExchangePrivateOffersDegradedModeAndSettlementContracts
// exercises Milestone 12's core round trip end to end: a private capacity
// offer is invisible to a tenant with no grant, becomes visible (and
// reservable, at its own tenant-specific override price) once granted, a
// degraded offer is excluded from placement eligibility with an explained
// reason code rather than silently hidden, and a bilateral agreement's own
// contracted platform fee rate -- never a request-supplied one -- prices a
// settlement scoped to exactly that one tenant's real, signed usage.
func TestFederatedCapacityExchangePrivateOffersDegradedModeAndSettlementContracts(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "federation-platform-admin@example.com")
	grantPlatformRole(t, store, "federation-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE"})
	aeJurisdiction := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-federation", "name": "Middle East Central", "jurisdiction_id": aeJurisdiction})
	aeRegionID := str(t, body, "id")

	operatorOwner, operatorID, _, agentID, keyPEM := setUpOperatorWithNetworkOffer(t, base, smtp, platformAdmin, "federation-operator", aeRegionID, 100, 2.00)

	clusters := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/clusters")
	if len(clusters) != 1 {
		t.Fatalf("expected exactly 1 cluster, got %d", len(clusters))
	}
	clusterID := clusters[0]["id"].(string)

	resp, body := operatorOwner.post("/api/v1/operators/"+operatorID+"/capacity-offers", map[string]any{
		"cluster_id": clusterID, "accelerator_type": "nvidia-h100", "total_capacity": 10,
		"price_per_unit_hour": 5.00, "currency": "USD", "visibility": "private",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create private capacity offer: expected 201, got %d: %v", resp.StatusCode, body)
	}
	privateOfferID := str(t, body, "id")
	if got := body["visibility"]; got != "private" {
		t.Fatalf("expected visibility private, got %v", got)
	}

	ownerA := registerVerifyAndLogin(t, base, smtp, "federation-tenant-a-owner@example.com")
	tenantA := createTenant(t, ownerA, "Federation Tenant A", "AE")

	// --- Private offer is invisible with no grant --------------------------
	offersBeforeGrant := ownerA.getArray(t, "/api/v1/enterprises/"+tenantA+"/capacity-offers")
	for _, o := range offersBeforeGrant {
		if o["id"] == privateOfferID {
			t.Fatalf("expected the private offer to be invisible to tenant A before any grant, got %v", offersBeforeGrant)
		}
	}

	// --- Bilateral agreement + grant with a tenant-specific price override --
	resp, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/bilateral-agreements", map[string]any{
		"enterprise_tenant_id": tenantA, "currency": "USD", "platform_fee_rate": 0.15,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create bilateral agreement: expected 201, got %d: %v", resp.StatusCode, body)
	}
	agreementID := str(t, body, "id")

	resp, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/capacity-offers/"+privateOfferID+"/grants", map[string]any{
		"enterprise_tenant_id": tenantA, "bilateral_agreement_id": agreementID, "price_per_unit_hour_override": 3.00,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create capacity offer grant: expected 201, got %d: %v", resp.StatusCode, body)
	}

	agreementsForTenantA := ownerA.getArray(t, "/api/v1/enterprises/"+tenantA+"/bilateral-agreements")
	if len(agreementsForTenantA) != 1 || agreementsForTenantA[0]["id"] != agreementID {
		t.Fatalf("expected tenant A to see its own bilateral agreement, got %v", agreementsForTenantA)
	}

	// --- Now visible, and priced at the tenant-specific override -----------
	offersAfterGrant := ownerA.getArray(t, "/api/v1/enterprises/"+tenantA+"/capacity-offers")
	found := false
	for _, o := range offersAfterGrant {
		if o["id"] == privateOfferID {
			found = true
		}
	}
	if !found {
		t.Fatalf("expected the private offer to be visible to tenant A after a grant, got %v", offersAfterGrant)
	}

	approver := inviteAndAcceptAdmin(t, base, smtp, ownerA, tenantA, "federation-tenant-a-approver@example.com")
	versionID := setUpPlacementWorkload(t, store, ownerA, approver, tenantA, "federation-workload", false)

	resp, body = ownerA.post("/api/v1/enterprises/"+tenantA+"/placement-requests", map[string]any{
		"workload_version_id": versionID, "quantity": 2, "simulate": false,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("evaluate placement: expected 201, got %d: %v", resp.StatusCode, body)
	}
	reservation, ok := body["reservation"].(map[string]any)
	if !ok {
		t.Fatalf("expected a reservation against the granted private offer, got %v", body["reservation"])
	}
	if got := reservation["price_per_unit_hour"]; got != 3.00 {
		t.Fatalf("expected the reservation priced at the tenant-specific override 3.00, not the offer's own base price 5.00, got %v", got)
	}
	if got := reservation["estimated_cost"]; got != 6.00 {
		t.Fatalf("expected estimated cost 6.00 (2 * 3.00 override), got %v", got)
	}
	requestBody := body["request"].(map[string]any)
	requestID := requestBody["id"].(string)

	evaluations := ownerA.getArray(t, "/api/v1/enterprises/"+tenantA+"/placement-requests/"+requestID+"/evaluations")
	var privateOfferEval map[string]any
	for _, e := range evaluations {
		if e["capacity_offer_id"] == privateOfferID {
			privateOfferEval = e
		}
	}
	if privateOfferEval == nil {
		t.Fatalf("expected an evaluation for the granted private offer, got %v", evaluations)
	}
	explanation := privateOfferEval["explanation"].(map[string]any)
	commercialEligibility := explanation["commercial_eligibility"].(map[string]any)
	if got := commercialEligibility["price_override_applied"]; got != true {
		t.Fatalf("expected commercial_eligibility.price_override_applied=true, got %v", commercialEligibility)
	}

	// --- Degraded-mode exclusion --------------------------------------------
	resp, body = operatorOwner.patch("/api/v1/operators/"+operatorID+"/capacity-offers/"+privateOfferID, map[string]any{
		"degraded": true, "degraded_reason": "scheduled maintenance",
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("mark offer degraded: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["degraded"]; got != true {
		t.Fatalf("expected degraded=true, got %v", got)
	}

	resp, body = ownerA.post("/api/v1/enterprises/"+tenantA+"/placement-requests", map[string]any{
		"workload_version_id": versionID, "quantity": 1, "simulate": true,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("simulate placement against degraded offer: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if body["reservation"] != nil {
		t.Fatalf("expected no reservation against a degraded offer, got %v", body["reservation"])
	}
	degradedEvaluations := body["evaluations"].([]any)
	rejectedForDegraded := false
	for _, raw := range degradedEvaluations {
		e := raw.(map[string]any)
		if e["capacity_offer_id"] != privateOfferID {
			continue
		}
		if e["decision"] != "rejected" {
			t.Fatalf("expected the degraded offer's evaluation to be rejected, got %v", e)
		}
		for _, rc := range e["reason_codes"].([]any) {
			if rc == "OPERATOR_DEGRADED" {
				rejectedForDegraded = true
			}
		}
	}
	if !rejectedForDegraded {
		t.Fatalf("expected an OPERATOR_DEGRADED reason code, got %v", degradedEvaluations)
	}

	// --- Settlement contract: priced at the agreement's own fee rate -------
	resp, body = ownerA.post("/api/v1/enterprises/"+tenantA+"/network-service-requests", map[string]any{
		"required_bandwidth_gbps": 10.0, "simulate": false,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("evaluate network service: expected 201, got %d: %v", resp.StatusCode, body)
	}
	networkReservation := body["reservation"].(map[string]any)
	networkReservationID := networkReservation["id"].(string)

	resp, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/price-books", map[string]any{
		"currency": "USD",
		"rules":    []map[string]any{{"usage_metric_key": "network_slice_gbps_hours", "unit_price": 4.0}},
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create price book: expected 201, got %d: %v", resp.StatusCode, body)
	}
	priceBookID := str(t, body, "id")
	resp, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/price-books/"+priceBookID+"/activate", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("activate price book: expected 200, got %d: %v", resp.StatusCode, body)
	}

	usageRaw, err := json.Marshal(map[string]any{
		"network_reservation_id": networkReservationID, "usage_metric_key": "network_slice_gbps_hours",
		"quantity": 20.0, "occurred_at": rfc3339Now(), "nonce": "federation-usage-1", "signed_at": rfc3339Now(),
	})
	if err != nil {
		t.Fatalf("marshal usage report: %v", err)
	}
	signature, err := pki.SignMessage(keyPEM, usageRaw)
	if err != nil {
		t.Fatalf("sign usage report: %v", err)
	}
	anon := newClient(t, srv.URL)
	resp, body = anon.postRaw("/api/v1/cluster-agents/"+agentID+"/usage-events", usageRaw, map[string]string{"X-Agent-Signature": signature})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("report usage: expected 201, got %d: %v", resp.StatusCode, body)
	}

	resp, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/invoices", map[string]any{
		"enterprise_tenant_id": tenantA, "period_start": "2020-01-01T00:00:00Z", "period_end": "2030-01-01T00:00:00Z", "tax_amount": 0.0,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("generate invoice: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if got := body["total"]; got != 80.0 {
		t.Fatalf("expected invoice total 80 (20 * 4.00), got %v", got)
	}

	resp, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/settlements/for-agreement", map[string]any{
		"bilateral_agreement_id": agreementID, "period_start": "2020-01-01T00:00:00Z", "period_end": "2030-01-01T00:00:00Z",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create settlement for agreement: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if got := body["gross_amount"]; got != 80.0 {
		t.Fatalf("expected settlement gross_amount 80, got %v", got)
	}
	if got := body["net_amount"]; got != 68.0 {
		t.Fatalf("expected settlement net_amount 68 (80 * 0.85, the agreement's own 0.15 fee rate), got %v", got)
	}
	if got := body["enterprise_tenant_id"]; got != tenantA {
		t.Fatalf("expected settlement scoped to tenant A, got %v", got)
	}
	if got := body["bilateral_agreement_id"]; got != agreementID {
		t.Fatalf("expected settlement to reference the bilateral agreement, got %v", got)
	}
}
