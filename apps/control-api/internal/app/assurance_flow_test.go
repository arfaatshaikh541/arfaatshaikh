package app_test

import (
	"net/http"
	"testing"
)

// TestAssuranceSLOIncidentAndAlertLifecycle exercises Milestone 10's core
// round trip end to end: an SLO measuring policy_compliance_rate is
// evaluated against real policy_evaluation_records Milestone 5's placement
// engine already produced (this milestone deliberately does not duplicate
// that data -- see internal/modules/assurance's package doc), an alert
// rule against the same metric fires and re-evaluating it is idempotent
// (never double-fires), an incident goes through its full
// open/acknowledge/resolve timeline, correlated health reflects the same
// metric, and audit correlation surfaces the SLO's own creation event.
func TestAssuranceSLOIncidentAndAlertLifecycle(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "assurance-platform-admin@example.com")
	grantPlatformRole(t, store, "assurance-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE"})
	aeJurisdiction := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-assurance", "name": "Middle East Central", "jurisdiction_id": aeJurisdiction})
	aeRegionID := str(t, body, "id")

	_, body = platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "DE", "name": "Germany"})
	deJurisdiction := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "eu-central-1-assurance", "name": "EU Central", "jurisdiction_id": deJurisdiction})
	deRegionID := str(t, body, "id")

	_, _, _ = setUpOperatorWithOffer(t, base, smtp, platformAdmin, "assurance-ae-operator", aeRegionID, 10, 3.00)
	_, _, _ = setUpOperatorWithOffer(t, base, smtp, platformAdmin, "assurance-de-operator", deRegionID, 10, 1.00)

	owner := registerVerifyAndLogin(t, base, smtp, "assurance-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Assurance Test Tenant", "AE")
	approver := inviteAndAcceptAdmin(t, base, smtp, owner, tenantID, "assurance-tenant-approver@example.com")

	versionID := setUpPlacementWorkload(t, store, owner, approver, tenantID, "assurance-workload", true)
	publishResidencyPolicy(t, owner, approver, tenantID, "assurance-residency", "AE")

	// Produces 1 'allow' policy_evaluation_record (the AE offer) and 1
	// 'deny' (the DE offer, rejected by the AE-only residency policy) --
	// a real 50% policy compliance rate this milestone never fabricates.
	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/placement-requests", map[string]any{
		"workload_version_id": versionID, "quantity": 2, "simulate": false,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("evaluate placement: expected 201, got %d: %v", resp.StatusCode, body)
	}

	// --- SLO -----------------------------------------------------------
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/slos", map[string]any{
		"name": "policy-compliance-slo", "metric_source": "policy_compliance_rate",
		"target_percentage": 50, "window_days": 1,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create slo: expected 201, got %d: %v", resp.StatusCode, body)
	}
	sloID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/slos/"+sloID+"/evaluate", nil)
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("evaluate slo: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if got := body["actual_percentage"]; got != 50.0 {
		t.Fatalf("expected actual_percentage 50 (1 allow / 2 total), got %v", got)
	}
	if got := body["sample_size"]; got != 2.0 {
		t.Fatalf("expected sample_size 2, got %v", got)
	}
	if got := body["status"]; got != "at_risk" {
		t.Fatalf("expected status at_risk (actual==target, no error budget left), got %v", got)
	}

	evaluations := owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/slos/"+sloID+"/evaluations")
	if len(evaluations) != 1 {
		t.Fatalf("expected 1 slo evaluation on record, got %d", len(evaluations))
	}

	// --- Alert rule: idempotent firing ----------------------------------
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/alert-rules", map[string]any{
		"name": "policy-compliance-alert", "metric_source": "policy_compliance_rate",
		"comparison": "lt", "threshold": 60, "severity": "warning",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create alert rule: expected 201, got %d: %v", resp.StatusCode, body)
	}
	ruleID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/alert-rules/"+ruleID+"/evaluate", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("evaluate alert rule: expected 200, got %d: %v", resp.StatusCode, body)
	}
	firstAlert, ok := body["alert"].(map[string]any)
	if !ok {
		t.Fatalf("expected a firing alert (50%% compliance < 60%% threshold), got %v", body["alert"])
	}
	if got := firstAlert["status"]; got != "firing" {
		t.Fatalf("expected alert status firing, got %v", got)
	}
	firstAlertID := firstAlert["id"].(string)

	// Re-evaluating the same still-breached rule must not create a second
	// firing alert.
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/alert-rules/"+ruleID+"/evaluate", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("re-evaluate alert rule: expected 200, got %d: %v", resp.StatusCode, body)
	}
	secondAlert := body["alert"].(map[string]any)
	if secondAlert["id"] != firstAlertID {
		t.Fatalf("expected re-evaluation to return the same firing alert %s, got %v", firstAlertID, secondAlert["id"])
	}
	alerts := owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/alerts")
	if len(alerts) != 1 {
		t.Fatalf("expected exactly 1 alert on record (idempotent firing), got %d", len(alerts))
	}

	// A rule that is not breached must evaluate to no alert at all.
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/alert-rules", map[string]any{
		"name": "policy-compliance-never-fires", "metric_source": "policy_compliance_rate",
		"comparison": "lt", "threshold": 10, "severity": "info",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create second alert rule: expected 201, got %d: %v", resp.StatusCode, body)
	}
	neverFiresRuleID := str(t, body, "id")
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/alert-rules/"+neverFiresRuleID+"/evaluate", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("evaluate never-fires alert rule: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if body["alert"] != nil {
		t.Fatalf("expected no alert for an unbreached rule, got %v", body["alert"])
	}

	// --- Incidents -------------------------------------------------------
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/incidents", map[string]any{
		"title": "Policy compliance degraded", "severity": "warning",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create incident: expected 201, got %d: %v", resp.StatusCode, body)
	}
	incidentID := str(t, body, "id")
	if got := body["status"]; got != "open" {
		t.Fatalf("expected incident status open, got %v", got)
	}

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/incidents/"+incidentID+"/acknowledge", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("acknowledge incident: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "acknowledged" {
		t.Fatalf("expected incident status acknowledged, got %v", got)
	}

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/incidents/"+incidentID+"/resolve", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("resolve incident: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "resolved" {
		t.Fatalf("expected incident status resolved, got %v", got)
	}

	incidentEvents := owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/incidents/"+incidentID+"/events")
	if len(incidentEvents) != 3 {
		t.Fatalf("expected 3 incident events (opened, acknowledged, resolved), got %d: %v", len(incidentEvents), incidentEvents)
	}

	// Resolving an already-resolved incident is rejected, not silently
	// re-accepted.
	resp, _ = owner.post("/api/v1/enterprises/"+tenantID+"/incidents/"+incidentID+"/resolve", nil)
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("re-resolve incident: expected 409, got %d", resp.StatusCode)
	}

	// --- Correlated health -------------------------------------------------
	resp, body = owner.get("/api/v1/enterprises/" + tenantID + "/health")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("get correlated health: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["policy_compliance_rate_percentage"]; got != 50.0 {
		t.Fatalf("expected correlated health policy_compliance_rate_percentage 50, got %v", got)
	}

	// --- Audit correlation ---------------------------------------------
	auditEvents := owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/audit-correlation/slo_definition/"+sloID)
	found := false
	for _, e := range auditEvents {
		if e["action"] == "slos.created" {
			found = true
		}
	}
	if !found {
		t.Fatalf("expected a slos.created audit event correlated to the SLO, got %v", auditEvents)
	}
}
