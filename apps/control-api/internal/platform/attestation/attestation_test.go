package attestation

import (
	"context"
	"testing"
)

func TestMockProviderPassesWhenMeasurementsMatch(t *testing.T) {
	policy := Policy{
		ProviderType: "mock",
		ExpectedMeasurements: map[string]any{
			"platform":      "mock-tee-v1",
			"firmware_hash": "abc123",
		},
	}
	evidence := Evidence{
		ProviderType: "mock",
		Measurements: map[string]any{
			"platform":      "mock-tee-v1",
			"firmware_hash": "abc123",
			"extra_field":   "ignored, not in the policy",
		},
		RawEvidence: `{"raw":"blob"}`,
	}

	result, err := NewMockProvider().Verify(context.Background(), policy, evidence)
	if err != nil {
		t.Fatalf("verify: %v", err)
	}
	if result.Decision != DecisionPass {
		t.Fatalf("expected pass, got %s (reasons: %v)", result.Decision, result.ReasonCodes)
	}
	if len(result.ReasonCodes) != 0 {
		t.Fatalf("expected no reason codes on pass, got %v", result.ReasonCodes)
	}
}

func TestMockProviderFailsOnMismatchedMeasurement(t *testing.T) {
	policy := Policy{
		ProviderType:         "mock",
		ExpectedMeasurements: map[string]any{"firmware_hash": "abc123"},
	}
	evidence := Evidence{
		ProviderType: "mock",
		Measurements: map[string]any{"firmware_hash": "tampered-value"},
	}

	result, err := NewMockProvider().Verify(context.Background(), policy, evidence)
	if err != nil {
		t.Fatalf("verify: %v", err)
	}
	if result.Decision != DecisionFail {
		t.Fatalf("expected fail, got %s", result.Decision)
	}
	if len(result.ReasonCodes) != 1 || result.ReasonCodes[0] != "MEASUREMENT_MISMATCH:firmware_hash" {
		t.Fatalf("expected exactly one MEASUREMENT_MISMATCH reason code, got %v", result.ReasonCodes)
	}
}

func TestMockProviderFailsOnMissingMeasurement(t *testing.T) {
	policy := Policy{
		ProviderType:         "mock",
		ExpectedMeasurements: map[string]any{"firmware_hash": "abc123", "platform": "mock-tee-v1"},
	}
	evidence := Evidence{
		ProviderType: "mock",
		Measurements: map[string]any{"firmware_hash": "abc123"},
	}

	result, err := NewMockProvider().Verify(context.Background(), policy, evidence)
	if err != nil {
		t.Fatalf("verify: %v", err)
	}
	if result.Decision != DecisionFail {
		t.Fatalf("expected fail, got %s", result.Decision)
	}
	if len(result.ReasonCodes) != 1 || result.ReasonCodes[0] != "MISSING_MEASUREMENT:platform" {
		t.Fatalf("expected exactly one MISSING_MEASUREMENT reason code, got %v", result.ReasonCodes)
	}
}

func TestMockProviderFailsOnProviderTypeMismatch(t *testing.T) {
	policy := Policy{ProviderType: "mock", ExpectedMeasurements: map[string]any{}}
	evidence := Evidence{ProviderType: "amd_sev_snp", Measurements: map[string]any{}}

	result, err := NewMockProvider().Verify(context.Background(), policy, evidence)
	if err != nil {
		t.Fatalf("verify: %v", err)
	}
	if result.Decision != DecisionFail {
		t.Fatalf("expected fail, got %s", result.Decision)
	}
	if len(result.ReasonCodes) != 1 || result.ReasonCodes[0] != "PROVIDER_TYPE_MISMATCH" {
		t.Fatalf("expected exactly one PROVIDER_TYPE_MISMATCH reason code, got %v", result.ReasonCodes)
	}
}
