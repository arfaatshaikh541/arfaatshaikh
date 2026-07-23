package app_test

import (
	"net/http"
	"testing"

	"gridkeep/control-api/internal/testutil"
)

// residencyDocument builds a minimal-but-evaluatable sovereignty policy
// document restricted to the given allowed countries, matching the fake
// policy-engine's (and the real Python evaluator's) residency constraint
// contract.
func residencyDocument(allowedCountries ...string) map[string]any {
	return map[string]any{
		"residency": map[string]any{
			"allowed_countries": allowedCountries,
			"denied_countries":  []string{},
		},
		"operators": map[string]any{
			"allowed": []string{},
			"denied":  []string{},
		},
		"confidential_computing": map[string]any{"required": false},
		"cross_border": map[string]any{
			"backup_allowed_countries":   []string{},
			"failover_allowed_countries": []string{},
		},
		"encryption": map[string]any{},
	}
}

// TestSovereigntyPolicyDualControlPublishAndEvaluate covers the full
// Milestone 3 lifecycle end to end: draft creation, dual-control
// publish/approve (including the self-approval regression case), a real
// evaluation against the fake policy-engine producing a genuine allow and a
// genuine deny, and the resulting evidence trail.
func TestSovereigntyPolicyDualControlPublishAndEvaluate(t *testing.T) {
	srv, smtp, _ := testServer(t)
	base := httpTestServer{URL: srv.URL}

	owner := registerVerifyAndLogin(t, base, smtp, "policy-owner@example.com")
	tenantID := createTenant(t, owner, "Policy Test Tenant", "AE")

	approverEmail := "policy-approver@example.com"
	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/invitations", map[string]string{
		"email": approverEmail, "role_key": "enterprise_admin",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("invite approver: expected 201, got %d: %v", resp.StatusCode, body)
	}
	msg, ok := smtp.LastMessageContaining(approverEmail)
	if !ok {
		t.Fatalf("no invitation email captured for %s", approverEmail)
	}
	token, err := testutil.ExtractToken(msg)
	if err != nil {
		t.Fatalf("extract invitation token: %v", err)
	}
	approver := registerVerifyAndLogin(t, base, smtp, approverEmail)
	resp, body = approver.post("/api/v1/invitations/accept", map[string]string{"token": token})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("accept invitation: expected 200, got %d: %v", resp.StatusCode, body)
	}

	// Create a draft.
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/policies", map[string]any{
		"policy_key": "data-residency",
		"name":       "Data Residency",
		"document":   residencyDocument("AE", "SA"),
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create draft: expected 201, got %d: %v", resp.StatusCode, body)
	}
	policyID := str(t, body, "id")
	if got := body["status"]; got != "draft" {
		t.Fatalf("expected status draft, got %v", got)
	}

	// A second draft for the same key is rejected.
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/policies", map[string]any{
		"policy_key": "data-residency",
		"name":       "Data Residency 2",
		"document":   residencyDocument("AE"),
	})
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("duplicate draft: expected 409, got %d: %v", resp.StatusCode, body)
	}

	// Edit the draft.
	resp, body = owner.patch("/api/v1/enterprises/"+tenantID+"/policies/"+policyID, map[string]any{
		"name":     "Data Residency (edited)",
		"document": residencyDocument("AE", "SA"),
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("edit draft: expected 200, got %d: %v", resp.StatusCode, body)
	}

	// Request publish.
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/policies/"+policyID+"/request-publish", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("request publish: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "pending_publish" {
		t.Fatalf("expected status pending_publish, got %v", got)
	}

	// Self-approval must fail (dual control).
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/policies/"+policyID+"/approve-publish", nil)
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("self-approval: expected 403, got %d: %v", resp.StatusCode, body)
	}

	// A different, permitted user approves it.
	resp, body = approver.post("/api/v1/enterprises/"+tenantID+"/policies/"+policyID+"/approve-publish", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("approve publish: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "published" {
		t.Fatalf("expected status published, got %v", got)
	}

	// Simulate an allowed candidate: no evaluation record persisted.
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/policies/"+policyID+"/simulate", map[string]any{
		"candidate": map[string]any{
			"country":                          "AE",
			"operator_id":                      "op-1",
			"confidential_computing_available": true,
			"placement_role":                   "primary",
		},
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("simulate allow: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["decision"]; got != "allow" {
		t.Fatalf("expected simulate decision allow, got %v (%v)", got, body)
	}

	records := owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/policy-evaluations")
	if len(records) != 0 {
		t.Fatalf("expected no evaluation records after simulate, got %d", len(records))
	}

	// Real evaluation of an allowed candidate: persists a record.
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/policies/"+policyID+"/evaluate", map[string]any{
		"candidate": map[string]any{
			"country":                          "AE",
			"operator_id":                      "op-1",
			"confidential_computing_available": true,
			"placement_role":                   "primary",
		},
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("evaluate allow: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["decision"]; got != "allow" {
		t.Fatalf("expected evaluate decision allow, got %v (%v)", got, body)
	}

	// Real evaluation of a denied candidate (country not in allowed set).
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/policies/"+policyID+"/evaluate", map[string]any{
		"candidate": map[string]any{
			"country":                          "US",
			"operator_id":                      "op-1",
			"confidential_computing_available": true,
			"placement_role":                   "primary",
		},
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("evaluate deny: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["decision"]; got != "deny" {
		t.Fatalf("expected evaluate decision deny, got %v (%v)", got, body)
	}

	records = owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/policy-evaluations")
	if len(records) != 2 {
		t.Fatalf("expected 2 evaluation records, got %d: %v", len(records), records)
	}
}

// TestSovereigntyPolicyPublishBlockedByConflict proves the fail-safe publish
// gate: approving a second policy whose allowed-country set is disjoint
// from an already-published policy's set is blocked, because the two
// policies contradict each other for any given candidate.
func TestSovereigntyPolicyPublishBlockedByConflict(t *testing.T) {
	srv, smtp, _ := testServer(t)
	base := httpTestServer{URL: srv.URL}

	owner := registerVerifyAndLogin(t, base, smtp, "conflict-owner@example.com")
	tenantID := createTenant(t, owner, "Conflict Test Tenant", "AE")

	approverEmail := "conflict-approver@example.com"
	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/invitations", map[string]string{
		"email": approverEmail, "role_key": "enterprise_admin",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("invite approver: expected 201, got %d: %v", resp.StatusCode, body)
	}
	msg, ok := smtp.LastMessageContaining(approverEmail)
	if !ok {
		t.Fatalf("no invitation email captured for %s", approverEmail)
	}
	token, err := testutil.ExtractToken(msg)
	if err != nil {
		t.Fatalf("extract invitation token: %v", err)
	}
	approver := registerVerifyAndLogin(t, base, smtp, approverEmail)
	resp, body = approver.post("/api/v1/invitations/accept", map[string]string{"token": token})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("accept invitation: expected 200, got %d: %v", resp.StatusCode, body)
	}

	publishPolicy := func(policyKey string, allowedCountries ...string) string {
		resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/policies", map[string]any{
			"policy_key": policyKey,
			"name":       policyKey,
			"document":   residencyDocument(allowedCountries...),
		})
		if resp.StatusCode != http.StatusCreated {
			t.Fatalf("create draft %s: expected 201, got %d: %v", policyKey, resp.StatusCode, body)
		}
		id := str(t, body, "id")

		resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/policies/"+id+"/request-publish", nil)
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("request publish %s: expected 200, got %d: %v", policyKey, resp.StatusCode, body)
		}

		resp, body = approver.post("/api/v1/enterprises/"+tenantID+"/policies/"+id+"/approve-publish", nil)
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("approve publish %s: expected 200, got %d: %v", policyKey, resp.StatusCode, body)
		}
		return id
	}

	publishPolicy("residency-ae", "AE")

	// A second policy whose allowed set is disjoint from the first must be
	// blocked at approval time.
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/policies", map[string]any{
		"policy_key": "residency-us",
		"name":       "residency-us",
		"document":   residencyDocument("US"),
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create draft residency-us: expected 201, got %d: %v", resp.StatusCode, body)
	}
	secondID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/policies/"+secondID+"/request-publish", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("request publish residency-us: expected 200, got %d: %v", resp.StatusCode, body)
	}

	resp, body = approver.post("/api/v1/enterprises/"+tenantID+"/policies/"+secondID+"/approve-publish", nil)
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("approve conflicting publish: expected 409, got %d: %v", resp.StatusCode, body)
	}
}

// TestSovereigntyPolicyRollback proves rollback creates a fresh draft
// carrying an earlier version's content rather than mutating history, and
// that draft must itself go through dual-control publish again.
func TestSovereigntyPolicyRollback(t *testing.T) {
	srv, smtp, _ := testServer(t)
	base := httpTestServer{URL: srv.URL}

	owner := registerVerifyAndLogin(t, base, smtp, "rollback-owner@example.com")
	tenantID := createTenant(t, owner, "Rollback Test Tenant", "AE")

	approverEmail := "rollback-approver@example.com"
	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/invitations", map[string]string{
		"email": approverEmail, "role_key": "enterprise_admin",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("invite approver: expected 201, got %d: %v", resp.StatusCode, body)
	}
	msg, ok := smtp.LastMessageContaining(approverEmail)
	if !ok {
		t.Fatalf("no invitation email captured for %s", approverEmail)
	}
	token, err := testutil.ExtractToken(msg)
	if err != nil {
		t.Fatalf("extract invitation token: %v", err)
	}
	approver := registerVerifyAndLogin(t, base, smtp, approverEmail)
	resp, body = approver.post("/api/v1/invitations/accept", map[string]string{"token": token})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("accept invitation: expected 200, got %d: %v", resp.StatusCode, body)
	}

	// Publish version 1.
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/policies", map[string]any{
		"policy_key": "rollback-policy",
		"name":       "v1",
		"document":   residencyDocument("AE"),
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create draft v1: expected 201, got %d: %v", resp.StatusCode, body)
	}
	v1ID := str(t, body, "id")
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/policies/"+v1ID+"/request-publish", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("request publish v1: expected 200, got %d: %v", resp.StatusCode, body)
	}
	resp, body = approver.post("/api/v1/enterprises/"+tenantID+"/policies/"+v1ID+"/approve-publish", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("approve publish v1: expected 200, got %d: %v", resp.StatusCode, body)
	}

	// Rollback to version 1 while it is still the only version creates a
	// new draft (version 2) carrying the same content.
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/policies/by-key/rollback-policy/rollback", map[string]any{
		"to_version": 1,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("rollback: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "draft" {
		t.Fatalf("expected rolled-back draft status draft, got %v", got)
	}
	if got, want := body["rolled_back_from_version"], float64(1); got != want {
		t.Fatalf("expected rolled_back_from_version 1, got %v", got)
	}

	versions := owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/policies/by-key/rollback-policy/versions")
	if len(versions) != 2 {
		t.Fatalf("expected 2 versions after rollback, got %d: %v", len(versions), versions)
	}
}
