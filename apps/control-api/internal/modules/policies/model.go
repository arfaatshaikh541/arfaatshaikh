// Package policies implements sovereignty policy management: drafting,
// dual-control publish/approve, rollback, simulation, and real evaluation
// (approved architecture §22-23). Policy CRUD/versioning/lifecycle lives
// here in control-api; the deterministic constraint evaluation itself runs
// in the policy-engine service, called through
// internal/platform/policyengine's fail-closed client.
package policies

import (
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/platform/policyengine"
)

type SovereigntyPolicy struct {
	ID                    uuid.UUID                   `json:"id"`
	TenantID              uuid.UUID                   `json:"enterprise_tenant_id"`
	PolicyKey             string                      `json:"policy_key"`
	Version               int                         `json:"version"`
	Status                string                      `json:"status"`
	Name                  string                      `json:"name"`
	Document              policyengine.PolicyDocument `json:"document"`
	RequestedBy           uuid.UUID                   `json:"requested_by"`
	RequestedPublishAt    *time.Time                  `json:"requested_publish_at,omitempty"`
	ApprovedBy            *uuid.UUID                  `json:"approved_by,omitempty"`
	PublishedAt           *time.Time                  `json:"published_at,omitempty"`
	SupersededAt          *time.Time                  `json:"superseded_at,omitempty"`
	RolledBackFromVersion *int                        `json:"rolled_back_from_version,omitempty"`
	CreatedAt             time.Time                   `json:"created_at"`
	UpdatedAt             time.Time                   `json:"updated_at"`
}

type EvaluationRecord struct {
	ID                  uuid.UUID      `json:"id"`
	TenantID            uuid.UUID      `json:"enterprise_tenant_id"`
	SovereigntyPolicyID uuid.UUID      `json:"sovereignty_policy_id"`
	PolicyVersion       int            `json:"policy_version"`
	Decision            string         `json:"decision"`
	ReasonCodes         []string       `json:"reason_codes"`
	Candidate           map[string]any `json:"candidate"`
	InputsHash          string         `json:"inputs_hash"`
	IsSimulation        bool           `json:"is_simulation"`
	EvaluatedBy         *uuid.UUID     `json:"evaluated_by,omitempty"`
	EvaluatedAt         time.Time      `json:"evaluated_at"`
	CreatedAt           time.Time      `json:"created_at"`
}
