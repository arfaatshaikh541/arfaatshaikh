package policyengine

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// Client calls the policy-engine service. Every exported method fails
// closed (approved architecture §22: "if policy-engine is unreachable,
// times out, or returns an ambiguous result, control-api treats this
// identically to DENY -- there is no code path where 'policy engine down'
// resolves to 'allow'"). Callers should still inspect the returned error
// to distinguish a genuine deny from a fail-closed synthetic one for
// logging/evidence purposes, but must never treat a non-nil error as
// license to bypass the (always-safe) Decision/HasConflicts value.
type Client struct {
	baseURL string
	http    *http.Client
}

func NewClient(baseURL string, timeout time.Duration) *Client {
	return &Client{
		baseURL: baseURL,
		http:    &http.Client{Timeout: timeout},
	}
}

// Evaluate calls POST /evaluate. On any failure (network error, timeout,
// non-200 status, unparseable body) it returns a synthetic deny result
// (reason code POLICY_ENGINE_UNAVAILABLE) alongside a non-nil error --
// the result's Decision is always safe to act on even if the caller
// ignores the error.
func (c *Client) Evaluate(ctx context.Context, req EvaluationRequest) (EvaluationResult, error) {
	var result EvaluationResult
	if err := c.post(ctx, "/evaluate", req, &result); err != nil {
		return EvaluationResult{
			Decision:      DecisionDeny,
			ReasonCodes:   []string{ReasonCodePolicyEngineUnavailable},
			PolicyID:      req.PolicyID,
			PolicyVersion: req.PolicyVersion,
		}, fmt.Errorf("evaluate: %w", err)
	}
	if result.Decision != DecisionAllow && result.Decision != DecisionDeny {
		// An ambiguous decision is treated identically to policy-engine
		// being unreachable -- fail closed, not "trust whatever came back."
		return EvaluationResult{
			Decision:      DecisionDeny,
			ReasonCodes:   []string{ReasonCodePolicyEngineUnavailable},
			PolicyID:      req.PolicyID,
			PolicyVersion: req.PolicyVersion,
		}, fmt.Errorf("evaluate: ambiguous decision %q", result.Decision)
	}
	return result, nil
}

// CheckConflicts calls POST /conflicts. On any failure it returns
// HasConflicts=true (a publish this package cannot verify is safe must be
// blocked, not silently allowed through) alongside a non-nil error.
func (c *Client) CheckConflicts(ctx context.Context, req ConflictCheckRequest) (ConflictCheckResult, error) {
	var result ConflictCheckResult
	if err := c.post(ctx, "/conflicts", req, &result); err != nil {
		return ConflictCheckResult{
			HasConflicts: true,
			Conflicts: []PolicyConflict{{
				Code:        ReasonCodePolicyEngineUnavailable,
				Description: "policy-engine could not be reached to verify this policy does not conflict with another",
			}},
		}, fmt.Errorf("check conflicts: %w", err)
	}
	return result, nil
}

func (c *Client) post(ctx context.Context, path string, reqBody, respBody any) error {
	encoded, err := json.Marshal(reqBody)
	if err != nil {
		return fmt.Errorf("encode request: %w", err)
	}
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+path, bytes.NewReader(encoded))
	if err != nil {
		return fmt.Errorf("build request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.http.Do(httpReq)
	if err != nil {
		return fmt.Errorf("call policy-engine: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("read response: %w", err)
	}
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("policy-engine returned HTTP %d: %s", resp.StatusCode, string(raw))
	}
	if err := json.Unmarshal(raw, respBody); err != nil {
		return fmt.Errorf("decode response: %w", err)
	}
	return nil
}
