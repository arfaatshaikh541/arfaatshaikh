// Package attestation implements Milestone 8's Confidential Computing and
// Attestation scope: an operator configures what a confidential-computing-capable
// cluster's hardware is expected to report (AttestationPolicy), a cluster
// agent requests a server-issued challenge and submits evidence bound to a
// specific deployment (AttestationSession/AttestationResult), and this
// package -- not the agent -- verifies that evidence via
// internal/platform/attestation.Provider and records the outcome.
//
// This is the opposite trust direction from Milestone 6/7's "local
// enforcement" model: there, the cluster agent independently verifies and
// decides, and control-api only records the decision. Here, the cluster
// agent is the *prover* (it produces evidence about its own hardware) and
// control-api is the *verifier* (it decides whether that evidence is
// acceptable) -- remote attestation is inherently verifier-side, since the
// verifier is the one making a key-release decision on the result (see
// internal/modules/deployments' AgentFetchSecrets, extended this milestone
// to require a fresh, passing AttestationResult before releasing any
// workload secret for a confidential-computing-required deployment).
//
// AttestationResult never exposes raw evidence or reported measurements to
// a tenant's "customer verification view" -- ListResultsForTenant's own SQL
// does not select those columns at all (the same stronger guarantee
// Milestone 7's WorkloadSecret established: a type that cannot hold the
// sensitive value, not one that merely omits it from JSON), while an
// operator viewing its own cluster's results sees full detail, since it is
// the operator's own infrastructure the evidence describes.
package attestation

import (
	"time"

	"github.com/google/uuid"
)

type AttestationPolicy struct {
	ID                   uuid.UUID      `json:"id"`
	OperatorID           uuid.UUID      `json:"operator_id"`
	ClusterID            uuid.UUID      `json:"cluster_id"`
	ProviderType         string         `json:"provider_type"`
	ExpectedMeasurements map[string]any `json:"expected_measurements"`
	Status               string         `json:"status"`
	CreatedBy            uuid.UUID      `json:"created_by"`
	RevokedBy            *uuid.UUID     `json:"revoked_by,omitempty"`
	RevokedAt            *time.Time     `json:"revoked_at,omitempty"`
	RevokedReason        *string        `json:"revoked_reason,omitempty"`
	CreatedAt            time.Time      `json:"created_at"`
	UpdatedAt            time.Time      `json:"updated_at"`
}

// AttestationSession is the server-issued attestation challenge -- Nonce is
// minted by control-api, not the agent (see the package doc and migration
// 0028's comment on why this is the reverse of Milestone 6/7's nonce
// handling).
type AttestationSession struct {
	ID             uuid.UUID `json:"id"`
	OperatorID     uuid.UUID `json:"operator_id"`
	ClusterAgentID uuid.UUID `json:"cluster_agent_id"`
	Nonce          string    `json:"nonce"`
	Status         string    `json:"status"`
	IssuedAt       time.Time `json:"issued_at"`
	ExpiresAt      time.Time `json:"expires_at"`
}

// AttestationResult is the full, operator-visible verification record --
// includes RawEvidence and Measurements, since this is the operator's own
// infrastructure the evidence describes. Never serialized to a tenant.
type AttestationResult struct {
	ID                   uuid.UUID      `json:"id"`
	OperatorID           uuid.UUID      `json:"operator_id"`
	EnterpriseTenantID   uuid.UUID      `json:"enterprise_tenant_id"`
	ClusterAgentID       uuid.UUID      `json:"cluster_agent_id"`
	AttestationSessionID uuid.UUID      `json:"attestation_session_id"`
	AttestationPolicyID  *uuid.UUID     `json:"attestation_policy_id,omitempty"`
	DeploymentID         uuid.UUID      `json:"deployment_id"`
	ProviderType         string         `json:"provider_type"`
	Measurements         map[string]any `json:"measurements"`
	RawEvidence          string         `json:"raw_evidence"`
	Decision             string         `json:"decision"`
	ReasonCodes          []string       `json:"reason_codes"`
	EvaluatedAt          time.Time      `json:"evaluated_at"`
	CreatedAt            time.Time      `json:"created_at"`
}

// RedactedAttestationResult is the tenant-facing "customer verification
// view" -- it has no field capable of holding raw evidence or reported
// measurements at all, so there is no code path where a future change to a
// handler could accidentally serialize either back to a tenant session.
// listAttestationResultsForTenant's own SQL does not select those columns.
type RedactedAttestationResult struct {
	ID           uuid.UUID `json:"id"`
	DeploymentID uuid.UUID `json:"deployment_id"`
	ProviderType string    `json:"provider_type"`
	Decision     string    `json:"decision"`
	ReasonCodes  []string  `json:"reason_codes"`
	EvaluatedAt  time.Time `json:"evaluated_at"`
}

// evidenceSubmission is the signed body a cluster agent posts to submit
// attestation evidence -- Nonce must equal the session's own Nonce (the
// freshness/replay-protection check), SignedAt bounds how far the agent's
// claimed signing time may drift from the server's clock, the same
// discipline every other agent-signed body in this codebase uses.
type evidenceSubmission struct {
	DeploymentID string         `json:"deployment_id"`
	ProviderType string         `json:"provider_type"`
	Measurements map[string]any `json:"measurements"`
	RawEvidence  string         `json:"raw_evidence"`
	Nonce        string         `json:"nonce"`
	SignedAt     string         `json:"signed_at"`
}
