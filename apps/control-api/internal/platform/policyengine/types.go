// Package policyengine is control-api's HTTP client for the Python
// policy-engine service (see docs/adr/0008-policy-engine-http-transport.md
// for why this is plain HTTP/JSON rather than gRPC). Every type here
// mirrors policy_engine/schema.go's Pydantic models field-for-field, since
// both sides serialize/deserialize the same JSON shape.
package policyengine

type ResidencyConstraint struct {
	AllowedCountries []string `json:"allowed_countries"`
	DeniedCountries  []string `json:"denied_countries"`
}

type OperatorConstraint struct {
	Allowed []string `json:"allowed"`
	Denied  []string `json:"denied"`
}

type ConfidentialComputingConstraint struct {
	Required bool `json:"required"`
}

type CrossBorderConstraint struct {
	BackupAllowedCountries   []string `json:"backup_allowed_countries"`
	FailoverAllowedCountries []string `json:"failover_allowed_countries"`
}

type EncryptionConstraint struct {
	KeyOwnership *string `json:"key_ownership,omitempty"`
}

// PolicyDocument is the evaluatable content of one sovereignty_policies
// row's `document` column -- exactly what gets persisted and exactly what
// gets sent to policy-engine for evaluation.
type PolicyDocument struct {
	Residency             ResidencyConstraint             `json:"residency"`
	Operators             OperatorConstraint              `json:"operators"`
	ConfidentialComputing ConfidentialComputingConstraint `json:"confidential_computing"`
	CrossBorder           CrossBorderConstraint           `json:"cross_border"`
	Encryption            EncryptionConstraint            `json:"encryption"`
}

type EvaluationCandidate struct {
	Country                        string  `json:"country"`
	OperatorID                     string  `json:"operator_id"`
	ConfidentialComputingAvailable bool    `json:"confidential_computing_available"`
	PlacementRole                  string  `json:"placement_role"`
	EncryptionKeyOwnership         *string `json:"encryption_key_ownership,omitempty"`
}

type EvaluationRequest struct {
	PolicyID      string              `json:"policy_id"`
	PolicyVersion int                 `json:"policy_version"`
	Policy        PolicyDocument      `json:"policy"`
	Candidate     EvaluationCandidate `json:"candidate"`
}

// Decision values. ReasonCodePolicyEngineUnavailable is synthesized by
// this package itself (never returned by the real service) when the call
// could not be completed -- see Client.Evaluate.
const (
	DecisionAllow = "allow"
	DecisionDeny  = "deny"

	ReasonCodePolicyEngineUnavailable = "POLICY_ENGINE_UNAVAILABLE"
)

type EvaluationResult struct {
	Decision      string   `json:"decision"`
	ReasonCodes   []string `json:"reason_codes"`
	PolicyID      string   `json:"policy_id"`
	PolicyVersion int      `json:"policy_version"`
	InputsHash    string   `json:"inputs_hash"`
	EvaluatedAt   string   `json:"evaluated_at"`
}

type ConflictCheckRequest struct {
	PolicyAID string         `json:"policy_a_id"`
	PolicyA   PolicyDocument `json:"policy_a"`
	PolicyBID string         `json:"policy_b_id"`
	PolicyB   PolicyDocument `json:"policy_b"`
}

type PolicyConflict struct {
	Code        string `json:"code"`
	Description string `json:"description"`
}

type ConflictCheckResult struct {
	HasConflicts bool             `json:"has_conflicts"`
	Conflicts    []PolicyConflict `json:"conflicts"`
}
