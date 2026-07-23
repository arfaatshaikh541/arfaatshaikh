package app_test

import (
	"net/http"
	"testing"

	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/testutil"
)

// setUpPlacementWorkload builds a published, immutable workload version
// referencing an approved image and model version -- the same fixture
// workloads_flow_test.go uses -- with deployment_approval_required set
// explicitly, since EvaluatePlacement snapshots that field to decide
// whether a reservation needs dual-control approval before it commits.
func setUpPlacementWorkload(t *testing.T, store *dbpkg.Store, owner, approver *client, tenantID, seed string, approvalRequired bool) string {
	t.Helper()
	licenceID := seedModelLicence(t, store, seed+"-licence", true)
	seedApprovedRegistry(t, store, "registry.example.com")
	imageID := approveTestImage(t, owner, tenantID, seed+"-image")
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
		"resource_requirements":        map[string]any{},
		"deployment_approval_required": approvalRequired,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create workload version draft: expected 201, got %d: %v", resp.StatusCode, body)
	}
	versionID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/workload-versions/"+versionID+"/request-publish", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("request publish: expected 200, got %d: %v", resp.StatusCode, body)
	}
	resp, body = approver.post("/api/v1/enterprises/"+tenantID+"/workload-versions/"+versionID+"/approve-publish", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("approve publish: expected 200, got %d: %v", resp.StatusCode, body)
	}
	return versionID
}

// setUpOperatorWithOffer registers, activates, and builds out one
// operator's location/cluster chain in the given region, then publishes a
// single capacity offer against it via the real HTTP capacity-offers API.
func setUpOperatorWithOffer(t *testing.T, base httpTestServer, smtp *testutil.FakeSMTPServer, platformAdmin *client, seed, regionID string, totalCapacity int, pricePerUnitHour float64) (operatorOwner *client, operatorID, offerID string) {
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
		"confidential_computing_available": false, "estimated_kwh_per_unit_hour": 0.5,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create capacity offer: expected 201, got %d: %v", resp.StatusCode, body)
	}
	return owner, operatorID, str(t, body, "id")
}

func publishResidencyPolicy(t *testing.T, owner, approver *client, tenantID, policyKey string, allowedCountries ...string) {
	t.Helper()
	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/policies", map[string]any{
		"policy_key": policyKey, "name": policyKey, "document": residencyDocument(allowedCountries...),
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create policy draft: expected 201, got %d: %v", resp.StatusCode, body)
	}
	policyID := str(t, body, "id")
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/policies/"+policyID+"/request-publish", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("request policy publish: expected 200, got %d: %v", resp.StatusCode, body)
	}
	resp, body = approver.post("/api/v1/enterprises/"+tenantID+"/policies/"+policyID+"/approve-publish", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("approve policy publish: expected 200, got %d: %v", resp.StatusCode, body)
	}
}

func assertOfferAvailableCapacity(t *testing.T, offers []map[string]any, offerID string, want int) {
	t.Helper()
	for _, o := range offers {
		if o["id"] == offerID {
			if int(o["available_capacity"].(float64)) != want {
				t.Fatalf("expected available_capacity %d for offer %s, got %v", want, offerID, o["available_capacity"])
			}
			return
		}
	}
	t.Fatalf("offer %s not found", offerID)
}

// TestPlacementEvaluatesRanksAndDualControlsCommit is the end-to-end
// Milestone 5 test: two operators publish capacity in different
// jurisdictions, a tenant's published sovereignty policy allows only one of
// them, and placement must reject the sovereignty-ineligible (cheaper!)
// offer, rank and reserve against the eligible one, and require a genuinely
// different user to approve the reservation commit.
func TestPlacementEvaluatesRanksAndDualControlsCommit(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "placement-platform-admin@example.com")
	grantPlatformRole(t, store, "placement-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE"})
	aeJurisdiction := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-placement", "name": "Middle East Central", "jurisdiction_id": aeJurisdiction})
	aeRegionID := str(t, body, "id")

	_, body = platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "DE", "name": "Germany"})
	deJurisdiction := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "eu-central-1-placement", "name": "EU Central", "jurisdiction_id": deJurisdiction})
	deRegionID := str(t, body, "id")

	// The DE offer is cheaper -- if sovereignty gating did not work, it
	// would be ranked first. It must be rejected instead.
	_, _, aeOfferID := setUpOperatorWithOffer(t, base, smtp, platformAdmin, "placement-ae-operator", aeRegionID, 10, 3.00)
	deOwner, deOperatorID, _ := setUpOperatorWithOffer(t, base, smtp, platformAdmin, "placement-de-operator", deRegionID, 10, 1.00)

	owner := registerVerifyAndLogin(t, base, smtp, "placement-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Placement Test Tenant", "AE")
	approver := inviteAndAcceptAdmin(t, base, smtp, owner, tenantID, "placement-tenant-approver@example.com")

	versionID := setUpPlacementWorkload(t, store, owner, approver, tenantID, "placement-workload", true)
	publishResidencyPolicy(t, owner, approver, tenantID, "placement-residency", "AE")

	// Any tenant member can browse the cross-operator marketplace.
	offers := owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/capacity-offers")
	if len(offers) != 2 {
		t.Fatalf("expected 2 visible capacity offers, got %d", len(offers))
	}

	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/placement-requests", map[string]any{
		"workload_version_id": versionID, "quantity": 2, "simulate": false,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("evaluate placement: expected 201, got %d: %v", resp.StatusCode, body)
	}
	requestBody := body["request"].(map[string]any)
	if got := requestBody["status"]; got != "reserved" {
		t.Fatalf("expected request status reserved, got %v", got)
	}
	evaluations, ok := body["evaluations"].([]any)
	if !ok || len(evaluations) != 2 {
		t.Fatalf("expected 2 evaluations, got %v", body["evaluations"])
	}
	var eligibleCount, rejectedCount int
	for _, raw := range evaluations {
		eval := raw.(map[string]any)
		if eval["decision"] == "eligible" {
			eligibleCount++
			if eval["capacity_offer_id"] != aeOfferID {
				t.Fatalf("expected the AE offer to be the eligible one, got %v", eval)
			}
		} else {
			rejectedCount++
			reasons, _ := eval["reason_codes"].([]any)
			if len(reasons) == 0 {
				t.Fatalf("rejected evaluation must carry reason codes: %v", eval)
			}
		}
	}
	if eligibleCount != 1 || rejectedCount != 1 {
		t.Fatalf("expected exactly 1 eligible and 1 rejected evaluation, got eligible=%d rejected=%d", eligibleCount, rejectedCount)
	}

	reservation, ok := body["reservation"].(map[string]any)
	if !ok {
		t.Fatalf("expected a reservation in the response, got %v", body["reservation"])
	}
	reservationID := reservation["id"].(string)
	if got := reservation["status"]; got != "held" {
		t.Fatalf("expected reservation status held (approval required), got %v", got)
	}
	if got := reservation["estimated_cost"]; got != 6.0 {
		t.Fatalf("expected estimated cost 6 (2 * 3.00), got %v", got)
	}

	// Self-approval must be rejected (dual control).
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/capacity-reservations/"+reservationID+"/approve-commit", nil)
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("self-approve reservation: expected 409, got %d: %v", resp.StatusCode, body)
	}

	// A different, permitted user commits it.
	resp, body = approver.post("/api/v1/enterprises/"+tenantID+"/capacity-reservations/"+reservationID+"/approve-commit", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("approve-commit reservation: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "committed" {
		t.Fatalf("expected reservation status committed, got %v", got)
	}

	// The DE operator (never reserved against) sees no reservations.
	deReservations := deOwner.getArray(t, "/api/v1/operators/"+deOperatorID+"/capacity-reservations")
	if len(deReservations) != 0 {
		t.Fatalf("expected 0 reservations against the DE operator's capacity, got %d", len(deReservations))
	}
}

// TestPlacementSimulateDoesNotReserveCapacity proves simulate=true runs the
// full evaluation/ranking/explanation pipeline without ever touching
// available_capacity or creating a reservation.
func TestPlacementSimulateDoesNotReserveCapacity(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "placement-sim-platform-admin@example.com")
	grantPlatformRole(t, store, "placement-sim-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE"})
	aeJurisdiction := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-sim", "name": "Middle East Central", "jurisdiction_id": aeJurisdiction})
	aeRegionID := str(t, body, "id")

	operatorOwner, operatorID, offerID := setUpOperatorWithOffer(t, base, smtp, platformAdmin, "placement-sim-operator", aeRegionID, 5, 2.00)

	owner := registerVerifyAndLogin(t, base, smtp, "placement-sim-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Placement Sim Test Tenant", "AE")
	approver := inviteAndAcceptAdmin(t, base, smtp, owner, tenantID, "placement-sim-tenant-approver@example.com")

	versionID := setUpPlacementWorkload(t, store, owner, approver, tenantID, "placement-sim-workload", true)

	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/placement-requests", map[string]any{
		"workload_version_id": versionID, "quantity": 2, "simulate": true,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("simulate placement: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if body["reservation"] != nil {
		t.Fatalf("simulate=true must not create a reservation, got %v", body["reservation"])
	}
	requestBody := body["request"].(map[string]any)
	if got := requestBody["status"]; got != "evaluated" {
		t.Fatalf("expected request status evaluated (not reserved), got %v", got)
	}

	offers := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/capacity-offers")
	assertOfferAvailableCapacity(t, offers, offerID, 5)
}

// TestPlacementCancelReservationReleasesCapacity reserves capacity, cancels
// the reservation, and proves the offer's available_capacity is restored.
// The workload version here does not require deployment approval, so the
// reservation auto-commits at hold time -- also proving that path.
func TestPlacementCancelReservationReleasesCapacity(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "placement-cancel-platform-admin@example.com")
	grantPlatformRole(t, store, "placement-cancel-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE"})
	aeJurisdiction := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-cancel", "name": "Middle East Central", "jurisdiction_id": aeJurisdiction})
	aeRegionID := str(t, body, "id")

	operatorOwner, operatorID, offerID := setUpOperatorWithOffer(t, base, smtp, platformAdmin, "placement-cancel-operator", aeRegionID, 5, 2.00)

	owner := registerVerifyAndLogin(t, base, smtp, "placement-cancel-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Placement Cancel Test Tenant", "AE")
	approver := inviteAndAcceptAdmin(t, base, smtp, owner, tenantID, "placement-cancel-tenant-approver@example.com")

	versionID := setUpPlacementWorkload(t, store, owner, approver, tenantID, "placement-cancel-workload", false)

	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/placement-requests", map[string]any{
		"workload_version_id": versionID, "quantity": 3, "simulate": false,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("evaluate placement: expected 201, got %d: %v", resp.StatusCode, body)
	}
	reservation, ok := body["reservation"].(map[string]any)
	if !ok {
		t.Fatalf("expected a reservation, got %v", body["reservation"])
	}
	// deployment_approval_required=false means the reservation is
	// auto-committed at hold time -- no separate approve-commit call needed.
	if got := reservation["status"]; got != "committed" {
		t.Fatalf("expected auto-committed reservation status committed, got %v", got)
	}
	reservationID := reservation["id"].(string)

	offers := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/capacity-offers")
	assertOfferAvailableCapacity(t, offers, offerID, 2)

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/capacity-reservations/"+reservationID+"/cancel", map[string]string{"reason": "no longer needed"})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("cancel reservation: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "released" {
		t.Fatalf("expected reservation status released, got %v", got)
	}

	offers = operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/capacity-offers")
	assertOfferAvailableCapacity(t, offers, offerID, 5)
}

// TestPlacementRejectsInsufficientCapacity proves a request for more
// quantity than any offer has available is evaluated (with a clear
// INSUFFICIENT_CAPACITY reason code) but never reserved.
func TestPlacementRejectsInsufficientCapacity(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "placement-insuff-platform-admin@example.com")
	grantPlatformRole(t, store, "placement-insuff-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE"})
	aeJurisdiction := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-insuff", "name": "Middle East Central", "jurisdiction_id": aeJurisdiction})
	aeRegionID := str(t, body, "id")

	setUpOperatorWithOffer(t, base, smtp, platformAdmin, "placement-insuff-operator", aeRegionID, 2, 2.00)

	owner := registerVerifyAndLogin(t, base, smtp, "placement-insuff-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Placement Insufficient Test Tenant", "AE")
	approver := inviteAndAcceptAdmin(t, base, smtp, owner, tenantID, "placement-insuff-tenant-approver@example.com")

	versionID := setUpPlacementWorkload(t, store, owner, approver, tenantID, "placement-insuff-workload", true)

	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/placement-requests", map[string]any{
		"workload_version_id": versionID, "quantity": 10, "simulate": false,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("evaluate placement: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if body["reservation"] != nil {
		t.Fatalf("expected no reservation when no offer has enough capacity, got %v", body["reservation"])
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
		if r == "INSUFFICIENT_CAPACITY" {
			found = true
		}
	}
	if !found {
		t.Fatalf("expected INSUFFICIENT_CAPACITY reason code, got %v", reasons)
	}
}
