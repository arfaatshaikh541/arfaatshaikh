package app_test

import (
	"net/http"
	"testing"
	"time"

	"gridkeep/control-api/internal/testutil"
)

// setUpOperatorWithOfferEnergy mirrors setUpOperatorWithOffer but lets the
// caller control estimated_kwh_per_unit_hour directly (setUpOperatorWithOffer
// always seeds 0.5, and capacity_offers' own UpdateOffer endpoint has no
// patchable field for it -- only price/status/visibility/degraded state are
// mutable in place). Needed to construct two offers whose cost and energy
// figures disagree, so a ranking-mode change actually picks a different
// winner.
func setUpOperatorWithOfferEnergy(t *testing.T, base httpTestServer, smtp *testutil.FakeSMTPServer, platformAdmin *client, seed, regionID string, totalCapacity int, pricePerUnitHour, estimatedKWhPerUnitHour float64) (operatorOwner *client, operatorID, offerID string) {
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
		"cluster_id": clusterID, "accelerator_type": "nvidia-h100", "total_capacity": totalCapacity,
		"price_per_unit_hour": pricePerUnitHour, "currency": "USD",
		"confidential_computing_available": false, "estimated_kwh_per_unit_hour": estimatedKWhPerUnitHour,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create capacity offer: expected 201, got %d: %v", resp.StatusCode, body)
	}
	return owner, operatorID, str(t, body, "id")
}

// TestEnergyAwareSchedulingCarbonCeilingRankingAndDeferral covers
// Milestone 14's core guarantees: every placement evaluation carries
// sustainability evidence (a resolved carbon intensity, renewable
// percentage, and estimated carbon for that offer); a tenant's hard carbon
// ceiling excludes an otherwise-eligible offer with an explicit
// CARBON_INTENSITY_EXCEEDS_LIMIT reason code; a tenant's
// sustainability_ranking_mode changes which offer wins ranking (cost_first
// vs a carbon-weighted mode); and a non-urgent request whose schedule
// window has not opened yet is deferred without reserving any capacity,
// then successfully reserves once re-evaluated inside its window.
func TestEnergyAwareSchedulingCarbonCeilingRankingAndDeferral(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "energy-platform-admin@example.com")
	grantPlatformRole(t, store, "energy-platform-admin@example.com", "platform_super_administrator")

	resp, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE Energy"})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create jurisdiction: expected 201, got %d: %v", resp.StatusCode, body)
	}
	jurisdictionID := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-energy", "name": "Middle East Energy", "jurisdiction_id": jurisdictionID})
	regionID := str(t, body, "id")

	// Same region for both offers -- carbon intensity/renewable percentage
	// are resolved per-region, so both offers share an identical grid
	// snapshot. That makes estimated_carbon_kg directly proportional to
	// estimated_energy_kwh here, which is enough to prove carbon_first
	// ranking uses the carbon key (not cost) without needing to predict the
	// mock provider's actual per-region value.
	// The cheap offer is high-energy/high-carbon; the "green" offer is
	// expensive but low-energy/low-carbon.
	_, _, cheapOfferID := setUpOperatorWithOfferEnergy(t, base, smtp, platformAdmin, "energy-cheap-operator", regionID, 10, 1.00, 5.0)
	_, _, greenOfferID := setUpOperatorWithOfferEnergy(t, base, smtp, platformAdmin, "energy-green-operator", regionID, 10, 3.00, 0.1)

	owner := registerVerifyAndLogin(t, base, smtp, "energy-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Energy Test Tenant", "AE")
	approver := inviteAndAcceptAdmin(t, base, smtp, owner, tenantID, "energy-tenant-approver@example.com")
	versionID := setUpPlacementWorkload(t, store, owner, approver, tenantID, "energy-workload", false)

	// --- Sustainability evidence is present on every evaluation. ---
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/placement-requests", map[string]any{
		"workload_version_id": versionID, "quantity": 1, "simulate": true,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("simulate evaluation: expected 201, got %d: %v", resp.StatusCode, body)
	}
	evaluations, _ := body["evaluations"].([]any)
	if len(evaluations) != 2 {
		t.Fatalf("expected 2 evaluations, got %v", body["evaluations"])
	}
	for _, raw := range evaluations {
		eval := raw.(map[string]any)
		if eval["carbon_intensity_g_per_kwh"].(float64) <= 0 {
			t.Fatalf("expected a positive carbon intensity on every evaluation, got %v", eval)
		}
	}

	// --- A hard carbon ceiling excludes an otherwise-eligible offer. ---
	resp, body = owner.patch("/api/v1/enterprises/"+tenantID+"/sustainability-preferences", map[string]any{
		"sustainability_ranking_mode": "cost_first", "max_carbon_intensity_g_per_kwh": 0.01,
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("set carbon ceiling: expected 200, got %d: %v", resp.StatusCode, body)
	}
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/placement-requests", map[string]any{
		"workload_version_id": versionID, "quantity": 1, "simulate": true,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("simulate with carbon ceiling: expected 201, got %d: %v", resp.StatusCode, body)
	}
	evaluations, _ = body["evaluations"].([]any)
	for _, raw := range evaluations {
		eval := raw.(map[string]any)
		if eval["decision"] != "rejected" {
			t.Fatalf("expected every offer rejected under an unmeetable carbon ceiling, got %v", eval)
		}
		reasons, _ := eval["reason_codes"].([]any)
		found := false
		for _, r := range reasons {
			if r == "CARBON_INTENSITY_EXCEEDS_LIMIT" {
				found = true
			}
		}
		if !found {
			t.Fatalf("expected CARBON_INTENSITY_EXCEEDS_LIMIT reason code, got %v", reasons)
		}
	}

	// --- sustainability_ranking_mode changes which offer wins ranking. ---
	resp, body = owner.patch("/api/v1/enterprises/"+tenantID+"/sustainability-preferences", map[string]any{
		"sustainability_ranking_mode": "cost_first",
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("reset to cost_first: expected 200, got %d: %v", resp.StatusCode, body)
	}
	topRankedOfferID := func() string {
		resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/placement-requests", map[string]any{
			"workload_version_id": versionID, "quantity": 1, "simulate": true,
		})
		if resp.StatusCode != http.StatusCreated {
			t.Fatalf("simulate for ranking: expected 201, got %d: %v", resp.StatusCode, body)
		}
		evaluations, _ := body["evaluations"].([]any)
		for _, raw := range evaluations {
			eval := raw.(map[string]any)
			if eval["rank"] != nil && eval["rank"].(float64) == 1 {
				return eval["capacity_offer_id"].(string)
			}
		}
		t.Fatalf("no rank-1 evaluation found: %v", evaluations)
		return ""
	}

	if got := topRankedOfferID(); got != cheapOfferID {
		t.Fatalf("expected cost_first to rank the cheap offer first, got %s", got)
	}

	resp, body = owner.patch("/api/v1/enterprises/"+tenantID+"/sustainability-preferences", map[string]any{
		"sustainability_ranking_mode": "carbon_first",
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("set carbon_first: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := topRankedOfferID(); got != greenOfferID {
		t.Fatalf("expected carbon_first to rank the low-energy/low-carbon offer first, got %s", got)
	}

	// --- Non-urgent scheduling: a request outside its window defers rather
	// than reserving, then reserves once re-evaluated inside the window. ---
	resp, body = owner.patch("/api/v1/enterprises/"+tenantID+"/sustainability-preferences", map[string]any{
		"sustainability_ranking_mode": "cost_first",
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("reset ranking mode: expected 200, got %d: %v", resp.StatusCode, body)
	}

	future := time.Now().Add(2 * time.Hour)
	farFuture := time.Now().Add(3 * time.Hour)
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/placement-requests", map[string]any{
		"workload_version_id": versionID, "quantity": 1, "simulate": false,
		"non_urgent": true, "schedule_window_start": future, "schedule_window_end": farFuture,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("evaluate outside window: expected 201, got %d: %v", resp.StatusCode, body)
	}
	requestBody, _ := body["request"].(map[string]any)
	if got := requestBody["status"]; got != "deferred" {
		t.Fatalf("expected status deferred outside the schedule window, got %v", got)
	}
	if _, hasReservation := body["reservation"]; hasReservation && body["reservation"] != nil {
		t.Fatalf("expected no reservation for a deferred request, got %v", body["reservation"])
	}

	offersAfterDeferral := owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/capacity-offers")
	assertOfferAvailableCapacity(t, offersAfterDeferral, cheapOfferID, 10)
	assertOfferAvailableCapacity(t, offersAfterDeferral, greenOfferID, 10)

	past := time.Now().Add(-1 * time.Hour)
	soon := time.Now().Add(1 * time.Hour)
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/placement-requests", map[string]any{
		"workload_version_id": versionID, "quantity": 1, "simulate": false,
		"non_urgent": true, "schedule_window_start": past, "schedule_window_end": soon,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("evaluate inside window: expected 201, got %d: %v", resp.StatusCode, body)
	}
	requestBody, _ = body["request"].(map[string]any)
	if got := requestBody["status"]; got != "reserved" {
		t.Fatalf("expected status reserved inside the schedule window, got %v", got)
	}
	if _, ok := body["reservation"].(map[string]any); !ok {
		t.Fatalf("expected a reservation once inside the schedule window, got %v", body["reservation"])
	}
}
