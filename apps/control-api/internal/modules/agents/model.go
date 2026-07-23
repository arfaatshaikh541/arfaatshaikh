// Package agents implements Milestone 2's operator-agent machine identity:
// registration with a single-use bootstrap token, certificate issuance from
// a CSR the agent generates itself (via internal/platform/pki), revocation,
// and ingestion of signed capacity-snapshot facts. An operator_agent is not
// a user — it never authenticates with a session cookie; its credential is
// either the one-time bootstrap token (only valid for its first CSR) or,
// afterward, the private key matching its issued certificate (proved by
// signing each capacity-snapshot submission).
package agents

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

type OperatorAgent struct {
	ID         uuid.UUID `json:"id"`
	OperatorID uuid.UUID `json:"operator_id"`
	Name       string    `json:"name"`
	Status     string    `json:"status"`
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

type AgentCertificate struct {
	ID              uuid.UUID  `json:"id"`
	OperatorID      uuid.UUID  `json:"operator_id"`
	OperatorAgentID uuid.UUID  `json:"operator_agent_id"`
	SerialNumber    string     `json:"serial_number"`
	IssuedAt        time.Time  `json:"issued_at"`
	ExpiresAt       time.Time  `json:"expires_at"`
	RevokedAt       *time.Time `json:"revoked_at,omitempty"`
	RevokedReason   *string    `json:"revoked_reason,omitempty"`
	// CertificatePEM is intentionally omitted from the default listing
	// representation (see handlers.go) -- it is public key material, safe
	// to expose, but callers that just want to know "is this agent
	// trusted right now" don't need the full PEM blob in every response.
}

type CapacitySnapshot struct {
	ID              uuid.UUID      `json:"id"`
	OperatorID      uuid.UUID      `json:"operator_id"`
	OperatorAgentID uuid.UUID      `json:"operator_agent_id"`
	ClusterID       uuid.UUID      `json:"cluster_id"`
	Source          string         `json:"source"`
	TrustStatus     string         `json:"trust_status"`
	Payload         map[string]any `json:"payload"`
	CollectedAt     time.Time      `json:"collected_at"`
	CreatedAt       time.Time      `json:"created_at"`
}

// ClusterAgent is Milestone 6's cluster-scoped machine identity -- narrower
// than an OperatorAgent (which speaks for the whole operator account): a
// cluster agent registers one specific cluster and is the identity that
// later receives signed deployment-plan-validation requests for it.
type ClusterAgent struct {
	ID         uuid.UUID `json:"id"`
	OperatorID uuid.UUID `json:"operator_id"`
	ClusterID  uuid.UUID `json:"cluster_id"`
	Name       string    `json:"name"`
	Status     string    `json:"status"`
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

type ClusterAgentCertificate struct {
	ID                       uuid.UUID  `json:"id"`
	OperatorID               uuid.UUID  `json:"operator_id"`
	ClusterAgentID           uuid.UUID  `json:"cluster_agent_id"`
	SerialNumber             string     `json:"serial_number"`
	RotatedFromCertificateID *uuid.UUID `json:"rotated_from_certificate_id,omitempty"`
	IssuedAt                 time.Time  `json:"issued_at"`
	ExpiresAt                time.Time  `json:"expires_at"`
	RevokedAt                *time.Time `json:"revoked_at,omitempty"`
	RevokedReason            *string    `json:"revoked_reason,omitempty"`
}

// ControlMessage is one entry in the signed, replay-protected channel
// between control-api and a cluster agent. direction='to_agent' messages
// are signed by the platform CA; direction='from_agent' messages are
// signed by the responding agent's own current certificate. (ClusterAgentID,
// Nonce) is unique -- a reused nonce is rejected regardless of signature
// validity, which is what makes this replay-protected rather than merely
// signed.
//
// Payload is json.RawMessage, not map[string]any -- it must survive
// storage and retrieval as the exact bytes Signature was computed over
// (see migration 0026's comment on the underlying TEXT column); Go's
// encoding/json embeds a json.RawMessage field's bytes directly rather
// than re-marshaling them, so this type choice is what keeps the API
// response's payload both genuinely structured JSON and byte-identical to
// what was signed.
type ControlMessage struct {
	ID             uuid.UUID       `json:"id"`
	OperatorID     uuid.UUID       `json:"operator_id"`
	ClusterAgentID uuid.UUID       `json:"cluster_agent_id"`
	Direction      string          `json:"direction"`
	MessageType    string          `json:"message_type"`
	InResponseTo   *uuid.UUID      `json:"in_response_to,omitempty"`
	Nonce          string          `json:"nonce"`
	Payload        json.RawMessage `json:"payload"`
	Signature      string          `json:"signature"`
	SignedAt       time.Time       `json:"signed_at"`
	Status         string          `json:"status"`
	ReceivedAt     time.Time       `json:"received_at"`
}

// DeploymentPlanValidation is the local-enforcement decision record: the
// cluster agent -- not control-api -- independently verified the plan's
// signature and decided allow/deny against its own view of policy.
// WorkloadVersionID/CapacityReservationID are informational
// cross-references into Milestone 4/5's tenant-owned entities; this table
// never grants an operator visibility into that tenant data itself, RLS
// on those tables is unaffected.
type DeploymentPlanValidation struct {
	ID                    uuid.UUID  `json:"id"`
	OperatorID            uuid.UUID  `json:"operator_id"`
	ClusterAgentID        uuid.UUID  `json:"cluster_agent_id"`
	ControlMessageID      uuid.UUID  `json:"control_message_id"`
	PlanID                string     `json:"plan_id"`
	WorkloadVersionID     *uuid.UUID `json:"workload_version_id,omitempty"`
	CapacityReservationID *uuid.UUID `json:"capacity_reservation_id,omitempty"`
	SignatureValid        bool       `json:"signature_valid"`
	PolicyDecision        string     `json:"policy_decision"`
	ReasonCodes           []string   `json:"reason_codes"`
	DecidedAt             time.Time  `json:"decided_at"`
	CreatedAt             time.Time  `json:"created_at"`
}

// DeploymentPlanPayload is the fictional, minimal shape of a "deployment
// plan" this milestone can construct and send for validation -- just
// enough to exercise the signed-control-message/local-enforcement round
// trip end to end. Milestone 7 (Secure Deployment Orchestration) owns the
// real plan format, signed manifests, and actual execution.
type DeploymentPlanPayload struct {
	PlanID                string         `json:"plan_id"`
	ClusterID             string         `json:"cluster_id"`
	WorkloadVersionID     *string        `json:"workload_version_id,omitempty"`
	CapacityReservationID *string        `json:"capacity_reservation_id,omitempty"`
	Namespace             string         `json:"namespace"`
	ResourceQuota         map[string]any `json:"resource_quota"`
	NetworkPolicy         map[string]any `json:"network_policy"`
	SecurityContext       map[string]any `json:"security_context"`
}
