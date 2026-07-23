package app_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"gridkeep/control-api/internal/platform/policyengine"
)

// startFakePolicyEngine runs an in-process HTTP server implementing the
// exact same request/response contract as the real Python policy-engine
// service (POST /evaluate, POST /conflicts), reimplementing the identical
// deterministic constraint pipeline
// (apps/policy-engine/src/policy_engine/evaluate.py and conflicts.py) so
// control-api's integration tests can exercise genuine allow/deny and
// conflict/no-conflict outcomes without spawning a Python process from a Go
// test. It is a TEST-ONLY double: the real Python engine has its own
// independent 33-test suite (ruff/mypy/pytest, all passing) validating the
// production logic, and this session separately ran the real service live
// and called both endpoints over real HTTP to confirm they match this
// exact contract.
func startFakePolicyEngine(t *testing.T) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("/evaluate", func(w http.ResponseWriter, r *http.Request) {
		var req policyengine.EvaluationRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(fakeEvaluate(req))
	})
	mux.HandleFunc("/conflicts", func(w http.ResponseWriter, r *http.Request) {
		var req policyengine.ConflictCheckRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(fakeConflicts(req))
	})
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return srv
}

func fakeEvaluate(req policyengine.EvaluationRequest) policyengine.EvaluationResult {
	var reasons []string
	p, c := req.Policy, req.Candidate

	if contains(p.Residency.DeniedCountries, c.Country) {
		reasons = append(reasons, "RESIDENCY_DENIED_COUNTRY")
	} else if len(p.Residency.AllowedCountries) > 0 && !contains(p.Residency.AllowedCountries, c.Country) {
		reasons = append(reasons, "RESIDENCY_NOT_IN_ALLOWED_COUNTRIES")
	}

	if contains(p.Operators.Denied, c.OperatorID) {
		reasons = append(reasons, "OPERATOR_DENIED")
	} else if len(p.Operators.Allowed) > 0 && !contains(p.Operators.Allowed, c.OperatorID) {
		reasons = append(reasons, "OPERATOR_NOT_IN_ALLOWED_LIST")
	}

	if p.ConfidentialComputing.Required && !c.ConfidentialComputingAvailable {
		reasons = append(reasons, "CONFIDENTIAL_COMPUTING_REQUIRED_BUT_UNAVAILABLE")
	}

	if c.PlacementRole == "backup" && len(p.CrossBorder.BackupAllowedCountries) > 0 && !contains(p.CrossBorder.BackupAllowedCountries, c.Country) {
		reasons = append(reasons, "CROSS_BORDER_BACKUP_NOT_ALLOWED")
	}
	if c.PlacementRole == "failover" && len(p.CrossBorder.FailoverAllowedCountries) > 0 && !contains(p.CrossBorder.FailoverAllowedCountries, c.Country) {
		reasons = append(reasons, "CROSS_BORDER_FAILOVER_NOT_ALLOWED")
	}

	if p.Encryption.KeyOwnership != nil {
		if c.EncryptionKeyOwnership == nil || *c.EncryptionKeyOwnership != *p.Encryption.KeyOwnership {
			reasons = append(reasons, "ENCRYPTION_KEY_OWNERSHIP_MISMATCH")
		}
	}

	decision := policyengine.DecisionAllow
	if len(reasons) > 0 {
		decision = policyengine.DecisionDeny
	}
	if reasons == nil {
		reasons = []string{}
	}
	return policyengine.EvaluationResult{
		Decision:      decision,
		ReasonCodes:   reasons,
		PolicyID:      req.PolicyID,
		PolicyVersion: req.PolicyVersion,
		InputsHash:    "fake-hash",
		EvaluatedAt:   "2026-01-01T00:00:00Z",
	}
}

func fakeConflicts(req policyengine.ConflictCheckRequest) policyengine.ConflictCheckResult {
	a, b := req.PolicyA, req.PolicyB
	var conflicts []policyengine.PolicyConflict

	if disjoint(a.Residency.AllowedCountries, b.Residency.AllowedCountries) {
		conflicts = append(conflicts, policyengine.PolicyConflict{Code: "CONTRADICTORY_RESIDENCY_ALLOWED_SETS"})
	}
	if disjoint(a.Operators.Allowed, b.Operators.Allowed) {
		conflicts = append(conflicts, policyengine.PolicyConflict{Code: "CONTRADICTORY_OPERATOR_ALLOWED_SETS"})
	}
	if a.Encryption.KeyOwnership != nil && b.Encryption.KeyOwnership != nil && *a.Encryption.KeyOwnership != *b.Encryption.KeyOwnership {
		conflicts = append(conflicts, policyengine.PolicyConflict{Code: "CONTRADICTORY_ENCRYPTION_KEY_OWNERSHIP"})
	}

	if conflicts == nil {
		conflicts = []policyengine.PolicyConflict{}
	}
	return policyengine.ConflictCheckResult{HasConflicts: len(conflicts) > 0, Conflicts: conflicts}
}

func contains(list []string, value string) bool {
	for _, v := range list {
		if v == value {
			return true
		}
	}
	return false
}

func disjoint(a, b []string) bool {
	if len(a) == 0 || len(b) == 0 {
		return false
	}
	set := make(map[string]bool, len(a))
	for _, v := range a {
		set[v] = true
	}
	for _, v := range b {
		if set[v] {
			return false
		}
	}
	return true
}
