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
