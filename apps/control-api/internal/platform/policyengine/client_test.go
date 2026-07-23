package policyengine

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestEvaluate_ReturnsRealDecisionOnSuccess(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(EvaluationResult{
			Decision: DecisionAllow, ReasonCodes: []string{}, PolicyID: "p1", PolicyVersion: 1, InputsHash: "abc",
		})
	}))
	defer srv.Close()

	client := NewClient(srv.URL, 5*time.Second)
	result, err := client.Evaluate(context.Background(), EvaluationRequest{PolicyID: "p1", PolicyVersion: 1})
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if result.Decision != DecisionAllow {
		t.Fatalf("expected allow, got %s", result.Decision)
	}
}

func TestEvaluate_FailsClosedOnNetworkError(t *testing.T) {
	// A server address nothing is listening on -- guarantees a connection
	// error rather than depending on timing.
	client := NewClient("http://127.0.0.1:1", 200*time.Millisecond)
	result, err := client.Evaluate(context.Background(), EvaluationRequest{PolicyID: "p1", PolicyVersion: 1})
	if err == nil {
		t.Fatalf("expected an error for an unreachable policy-engine")
	}
	if result.Decision != DecisionDeny {
		t.Fatalf("expected fail-closed deny, got %s", result.Decision)
	}
	if len(result.ReasonCodes) != 1 || result.ReasonCodes[0] != ReasonCodePolicyEngineUnavailable {
		t.Fatalf("expected POLICY_ENGINE_UNAVAILABLE reason code, got %v", result.ReasonCodes)
	}
}

func TestEvaluate_FailsClosedOnTimeout(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(200 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	client := NewClient(srv.URL, 20*time.Millisecond)
	result, err := client.Evaluate(context.Background(), EvaluationRequest{PolicyID: "p1", PolicyVersion: 1})
	if err == nil {
		t.Fatalf("expected a timeout error")
	}
	if result.Decision != DecisionDeny {
		t.Fatalf("expected fail-closed deny on timeout, got %s", result.Decision)
	}
}

func TestEvaluate_FailsClosedOnNon200Status(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte(`{"error":"internal"}`))
	}))
	defer srv.Close()

	client := NewClient(srv.URL, 5*time.Second)
	result, err := client.Evaluate(context.Background(), EvaluationRequest{PolicyID: "p1", PolicyVersion: 1})
	if err == nil {
		t.Fatalf("expected an error for a 500 response")
	}
	if result.Decision != DecisionDeny {
		t.Fatalf("expected fail-closed deny, got %s", result.Decision)
	}
}

func TestEvaluate_FailsClosedOnMalformedBody(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`not valid json`))
	}))
	defer srv.Close()

	client := NewClient(srv.URL, 5*time.Second)
	result, err := client.Evaluate(context.Background(), EvaluationRequest{PolicyID: "p1", PolicyVersion: 1})
	if err == nil {
		t.Fatalf("expected an error for a malformed body")
	}
	if result.Decision != DecisionDeny {
		t.Fatalf("expected fail-closed deny, got %s", result.Decision)
	}
}

func TestEvaluate_FailsClosedOnAmbiguousDecision(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"decision":"maybe","reason_codes":[],"policy_id":"p1","policy_version":1,"inputs_hash":"x","evaluated_at":"now"}`))
	}))
	defer srv.Close()

	client := NewClient(srv.URL, 5*time.Second)
	result, err := client.Evaluate(context.Background(), EvaluationRequest{PolicyID: "p1", PolicyVersion: 1})
	if err == nil {
		t.Fatalf("expected an error for an ambiguous decision")
	}
	if result.Decision != DecisionDeny {
		t.Fatalf("expected fail-closed deny for ambiguous decision %q, got %s", "maybe", result.Decision)
	}
}

func TestCheckConflicts_ReturnsRealResultOnSuccess(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(ConflictCheckResult{HasConflicts: false, Conflicts: []PolicyConflict{}})
	}))
	defer srv.Close()

	client := NewClient(srv.URL, 5*time.Second)
	result, err := client.CheckConflicts(context.Background(), ConflictCheckRequest{})
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if result.HasConflicts {
		t.Fatalf("expected no conflicts")
	}
}

func TestCheckConflicts_FailsClosedOnNetworkError(t *testing.T) {
	client := NewClient("http://127.0.0.1:1", 200*time.Millisecond)
	result, err := client.CheckConflicts(context.Background(), ConflictCheckRequest{})
	if err == nil {
		t.Fatalf("expected an error for an unreachable policy-engine")
	}
	if !result.HasConflicts {
		t.Fatalf("expected fail-closed HasConflicts=true when policy-engine is unreachable")
	}
}
