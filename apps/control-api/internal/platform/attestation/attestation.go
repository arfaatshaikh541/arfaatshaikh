// Package attestation defines the provider-neutral remote-attestation
// verification boundary Milestone 8 ("Confidential Computing and
// Attestation") requires. Provider is the abstraction the approved
// architecture asks for -- a fixed, narrow interface future adapters for
// AMD SEV-SNP, Intel TDX, NVIDIA confidential computing, cloud-provider
// confidential VMs, and HSM-backed workloads would each implement, exactly
// one per real hardware attestation format.
//
// Unlike internal/platform/clusteradapter (an agent-side abstraction --
// only a cluster agent ever calls it), Provider is verifier-side: control-api
// itself holds and calls an implementation, because remote attestation is
// inherently something the relying party verifies about the prover, and
// control-api is the relying party making a key-release decision on the
// result (see internal/modules/deployments' AgentFetchSecrets). This is the
// opposite trust direction from Milestone 6/7's "local enforcement" model,
// where the cluster agent is the one deciding and control-api only records
// the decision.
//
// The only implementation in this codebase is MockProvider, a plain
// expected-vs-reported measurement comparison with no cryptographic
// evidence-format parsing at all. It makes no claim of verifying genuine
// confidential-computing hardware -- see its own doc comment -- consistent
// with the approved architecture's explicit "no fake claims of confidential
// computing" requirement. A real provider verifying an actual attestation
// report (parsing vendor-specific evidence structures, checking a hardware
// vendor's certificate chain, validating report signatures against a
// vendor root of trust) is future work for whichever milestone integrates
// real confidential-computing hardware.
package attestation

import (
	"context"
	"fmt"
	"reflect"
)

// Policy is what a verifier checks submitted evidence against -- mirrors
// internal/modules/attestation's AttestationPolicy database row, passed in
// by value so this package has no database dependency of its own.
type Policy struct {
	ProviderType         string
	ExpectedMeasurements map[string]any
}

// Evidence is what a cluster agent submits for verification.
type Evidence struct {
	ProviderType string
	Measurements map[string]any
	RawEvidence  string
}

// Result is the verifier's decision. ReasonCodes is always non-nil (an
// empty slice, not nil) so it marshals to `[]` rather than `null`.
type Result struct {
	Decision    string
	ReasonCodes []string
}

const (
	DecisionPass = "pass"
	DecisionFail = "fail"
)

// Provider verifies a piece of submitted evidence against a policy. Verify
// never has side effects beyond its return value -- persisting the result
// as an AttestationResult row is the caller's job (internal/modules/attestation),
// keeping this package a pure verification primitive, easy to swap for a
// real hardware-backed implementation later without touching any
// persistence or authorization code.
type Provider interface {
	Verify(ctx context.Context, policy Policy, evidence Evidence) (Result, error)
}

// MockProvider is a clearly-labelled stand-in for a real hardware
// attestation verifier, exactly what the approved architecture requires
// for local development ("local development must use a clearly labelled
// mock attestation provider"). It does the one thing every real provider
// must also do -- compare reported measurements against what a policy
// expects -- without parsing any real evidence format; RawEvidence is
// retained (see the caller's evidence-retention requirement) but never
// interpreted by this provider at all.
type MockProvider struct{}

func NewMockProvider() *MockProvider { return &MockProvider{} }

// Verify fails closed: a provider-type mismatch, a missing expected
// measurement, or a mismatched measurement value each independently
// produce a reason code and a "fail" decision. Only when every expected
// measurement is present and matches exactly does it return "pass".
func (p *MockProvider) Verify(_ context.Context, policy Policy, evidence Evidence) (Result, error) {
	reasonCodes := []string{}

	if evidence.ProviderType != policy.ProviderType {
		reasonCodes = append(reasonCodes, "PROVIDER_TYPE_MISMATCH")
	}
	for key, expected := range policy.ExpectedMeasurements {
		actual, ok := evidence.Measurements[key]
		if !ok {
			reasonCodes = append(reasonCodes, fmt.Sprintf("MISSING_MEASUREMENT:%s", key))
			continue
		}
		if !reflect.DeepEqual(actual, expected) {
			reasonCodes = append(reasonCodes, fmt.Sprintf("MEASUREMENT_MISMATCH:%s", key))
		}
	}

	if len(reasonCodes) > 0 {
		return Result{Decision: DecisionFail, ReasonCodes: reasonCodes}, nil
	}
	return Result{Decision: DecisionPass, ReasonCodes: reasonCodes}, nil
}
