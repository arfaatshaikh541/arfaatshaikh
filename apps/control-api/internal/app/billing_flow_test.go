package app_test

import (
	"encoding/json"
	"net/http"
	"testing"

	"gridkeep/control-api/internal/platform/pki"
)

// usageReportBody signs a usage-event report body with the agent's key,
// mirroring exactly what cmd/mockclusteragent's reportUsage does.
func usageReportBody(t *testing.T, keyPEM string, networkReservationID, metricKey string, quantity float64, nonce string) ([]byte, string) {
	t.Helper()
	raw, err := json.Marshal(map[string]any{
		"network_reservation_id": networkReservationID,
		"usage_metric_key":       metricKey,
		"quantity":               quantity,
		"occurred_at":            rfc3339Now(),
		"nonce":                  nonce,
		"signed_at":              rfc3339Now(),
	})
	if err != nil {
		t.Fatalf("marshal usage report: %v", err)
	}
	signature, err := pki.SignMessage(keyPEM, raw)
	if err != nil {
		t.Fatalf("sign usage report: %v", err)
	}
	return raw, signature
}

// TestBillingUsageAggregationInvoiceSettlementDisputeAndBudgetAlert exercises
// Milestone 11's full round trip end to end: a cluster agent signs and
// reports one real usage event against a committed network reservation
// (reusing Milestone 9's network-service fixture), the operator prices,
// aggregates, and invoices it against its own active price book, the
// tenant disputes and the operator resolves the dispute, the operator
// reconciles a settlement covering that invoice, a tenant-requested quote
// is priced the same way against the same price book, and a
// budget_utilization alert rule (reusing Milestone 10's alert
// infrastructure) fires because real usage exceeds the budget's threshold.
func TestBillingUsageAggregationInvoiceSettlementDisputeAndBudgetAlert(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "billing-platform-admin@example.com")
	grantPlatformRole(t, store, "billing-platform-admin@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE"})
	aeJurisdiction := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1-billing", "name": "Middle East Central", "jurisdiction_id": aeJurisdiction})
	aeRegionID := str(t, body, "id")

	operatorOwner, operatorID, _, agentID, keyPEM := setUpOperatorWithNetworkOffer(t, base, smtp, platformAdmin, "billing-operator", aeRegionID, 100, 2.00)

	owner := registerVerifyAndLogin(t, base, smtp, "billing-tenant-owner@example.com")
	tenantID := createTenant(t, owner, "Billing Test Tenant", "AE")

	resp, body := owner.post("/api/v1/enterprises/"+tenantID+"/network-service-requests", map[string]any{
		"required_bandwidth_gbps": 10.0, "simulate": false,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("evaluate network service: expected 201, got %d: %v", resp.StatusCode, body)
	}
	reservation := body["reservation"].(map[string]any)
	reservationID := reservation["id"].(string)

	// --- Price book -----------------------------------------------------
	resp, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/price-books", map[string]any{
		"currency": "USD",
		"rules": []map[string]any{
			{"usage_metric_key": "network_slice_gbps_hours", "unit_price": 3.0},
		},
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create price book: expected 201, got %d: %v", resp.StatusCode, body)
	}
	priceBookID := str(t, body, "id")
	if got := body["status"]; got != "draft" {
		t.Fatalf("expected new price book status draft, got %v", got)
	}

	resp, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/price-books/"+priceBookID+"/activate", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("activate price book: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "active" {
		t.Fatalf("expected activated price book status active, got %v", got)
	}

	// --- Signed usage report ---------------------------------------------
	rawBody, signature := usageReportBody(t, keyPEM, reservationID, "network_slice_gbps_hours", 20.0, "usage-report-1")
	anon := newClient(t, srv.URL)
	resp, body = anon.postRaw("/api/v1/cluster-agents/"+agentID+"/usage-events", rawBody, map[string]string{"X-Agent-Signature": signature})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("report usage: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if got := body["quantity"]; got != 20.0 {
		t.Fatalf("expected reported quantity 20, got %v", got)
	}

	// Replaying the exact same nonce for this cluster agent must be
	// rejected at the database level (usage_events' own UNIQUE constraint),
	// not silently accepted a second time.
	resp, _ = anon.postRaw("/api/v1/cluster-agents/"+agentID+"/usage-events", rawBody, map[string]string{"X-Agent-Signature": signature})
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("replay usage report: expected 409, got %d", resp.StatusCode)
	}

	operatorUsageEvents := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/usage-events")
	if len(operatorUsageEvents) != 1 {
		t.Fatalf("expected exactly 1 usage event on record, got %d", len(operatorUsageEvents))
	}

	// --- Aggregation -------------------------------------------------------
	resp, body = operatorOwner.do(http.MethodPost, "/api/v1/operators/"+operatorID+"/usage-aggregations", map[string]any{
		"enterprise_tenant_id": tenantID, "period_start": "2020-01-01T00:00:00Z", "period_end": "2030-01-01T00:00:00Z",
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("aggregate usage: expected 200, got %d: %v", resp.StatusCode, body)
	}

	// --- Quote (priced against the same active price book) -----------------
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/quotes", map[string]any{
		"operator_id": operatorID,
		"items":       []map[string]any{{"usage_metric_key": "network_slice_gbps_hours", "quantity": 5.0}},
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create quote: expected 201, got %d: %v", resp.StatusCode, body)
	}
	if got := body["estimated_total"]; got != 15.0 {
		t.Fatalf("expected quote estimated_total 15 (5 * 3.00), got %v", got)
	}

	// --- Invoice generation --------------------------------------------
	resp, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/invoices", map[string]any{
		"enterprise_tenant_id": tenantID, "period_start": "2020-01-01T00:00:00Z", "period_end": "2030-01-01T00:00:00Z", "tax_amount": 0.0,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("generate invoice: expected 201, got %d: %v", resp.StatusCode, body)
	}
	invoiceID := str(t, body, "id")
	if got := body["total"]; got != 60.0 {
		t.Fatalf("expected invoice total 60 (20 * 3.00), got %v", got)
	}
	if got := body["status"]; got != "issued" {
		t.Fatalf("expected invoice status issued, got %v", got)
	}
	if body["external_ref"] == nil || body["external_ref"] == "" {
		t.Fatalf("expected a non-empty external_ref from the mock billing provider sync, got %v", body["external_ref"])
	}

	tenantInvoices := owner.getArray(t, "/api/v1/enterprises/"+tenantID+"/invoices")
	if len(tenantInvoices) != 1 {
		t.Fatalf("expected the tenant to see exactly 1 invoice, got %d", len(tenantInvoices))
	}

	providerEvents := operatorOwner.getArray(t, "/api/v1/operators/"+operatorID+"/invoices/"+invoiceID+"/provider-events")
	if len(providerEvents) != 1 || providerEvents[0]["event_type"] != "invoice_sync_succeeded" {
		t.Fatalf("expected 1 invoice_sync_succeeded provider event, got %v", providerEvents)
	}

	// --- Dispute lifecycle -------------------------------------------------
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/billing-disputes", map[string]any{
		"invoice_id": invoiceID, "reason": "quantity looks too high",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("open dispute: expected 201, got %d: %v", resp.StatusCode, body)
	}
	disputeID := str(t, body, "id")
	if got := body["status"]; got != "open" {
		t.Fatalf("expected dispute status open, got %v", got)
	}

	resp, body = owner.get("/api/v1/enterprises/" + tenantID + "/invoices/" + invoiceID)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("get disputed invoice: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "disputed" {
		t.Fatalf("expected invoice status disputed after opening a dispute, got %v", got)
	}

	resp, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/billing-disputes/"+disputeID+"/resolve", map[string]any{
		"status": "resolved", "resolution_note": "usage confirmed correct against signed agent reports",
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("resolve dispute: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "resolved" {
		t.Fatalf("expected dispute status resolved, got %v", got)
	}

	resp, body = owner.get("/api/v1/enterprises/" + tenantID + "/invoices/" + invoiceID)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("get resolved invoice: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "issued" {
		t.Fatalf("expected invoice status back to issued after dispute resolution, got %v", got)
	}

	// --- Settlement ----------------------------------------------------
	resp, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/settlements", map[string]any{
		"period_start": "2020-01-01T00:00:00Z", "period_end": "2030-01-01T00:00:00Z", "platform_fee_rate": 0.10,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create settlement: expected 201, got %d: %v", resp.StatusCode, body)
	}
	settlementID := str(t, body, "id")
	if got := body["gross_amount"]; got != 60.0 {
		t.Fatalf("expected settlement gross_amount 60, got %v", got)
	}
	if got := body["net_amount"]; got != 54.0 {
		t.Fatalf("expected settlement net_amount 54 (60 * 0.9), got %v", got)
	}
	if got := body["status"]; got != "pending" {
		t.Fatalf("expected settlement status pending, got %v", got)
	}

	resp, body = operatorOwner.post("/api/v1/operators/"+operatorID+"/settlements/"+settlementID+"/reconcile", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("reconcile settlement: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := body["status"]; got != "reconciled" {
		t.Fatalf("expected settlement status reconciled, got %v", got)
	}

	// --- Budget + budget_utilization alert (Milestone 10 infrastructure) ---
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/budgets", map[string]any{
		"name": "billing-test-budget", "period_days": 30, "threshold_amount": 30.0, "currency": "USD", "hard_limit": false,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create budget: expected 201, got %d: %v", resp.StatusCode, body)
	}
	budgetID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/alert-rules", map[string]any{
		"name": "budget-utilization-alert", "metric_source": "budget_utilization", "resource_id": budgetID,
		"comparison": "gt", "threshold": 50.0, "severity": "warning",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create budget alert rule: expected 201, got %d: %v", resp.StatusCode, body)
	}
	ruleID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/alert-rules/"+ruleID+"/evaluate", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("evaluate budget alert rule: expected 200, got %d: %v", resp.StatusCode, body)
	}
	alert, ok := body["alert"].(map[string]any)
	if !ok {
		t.Fatalf("expected a firing alert (60 spent / 30 threshold = 200%% utilization > 50%% threshold), got %v", body["alert"])
	}
	if got := alert["status"]; got != "firing" {
		t.Fatalf("expected alert status firing, got %v", got)
	}
	if got := alert["value_at_fire"]; got != 200.0 {
		t.Fatalf("expected value_at_fire 200 (60 spent / 30 threshold * 100), got %v", got)
	}
}
