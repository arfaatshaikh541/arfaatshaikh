// Package deployments implements Milestone 7's Secure Deployment
// Orchestration: turning a Milestone 5 committed capacity_reservation into a
// running (fictionally -- no real cluster exists in this environment)
// workload on a Milestone 6 cluster agent, and every lifecycle action after
// that (scale/pause/resume/rollback/terminate).
//
// A deployment plan is an immutable, versioned, signed snapshot of a
// workload version's components, health checks, and resource/network/
// security declarations at the moment it was drafted -- it never follows a
// live reference to workload_versions, so a later edit to the workload
// version cannot silently change an already-approved plan. Its manifest
// only ever references a secret by key name (see buildManifest in
// service.go); no decrypted secret value is ever embedded in a plan,
// returned by any session-authenticated route in this package, or logged.
// The one place a decrypted value exists is the agent-facing secrets
// endpoint, scoped to the single cluster agent actually running the
// deployment that references it (see AgentFetchSecrets).
//
// Plan approval reuses the requested_by/approved_by dual-control pattern
// this codebase has now applied seven times (support_access_grants,
// sovereignty_policies, model_versions, workload_versions,
// vulnerability_exceptions, capacity_reservations, deployment_plans) rather
// than the architecture document's fuller multi-step ApprovalPolicy/
// ApprovalStep/EmergencyOverride system, which is not itself a numbered
// milestone and is deliberately deferred (see docs/project-status.md's
// Unresolved Risks).
//
// Deployment lifecycle actions are delivered to the assigned cluster agent
// over Milestone 6's signed, replay-protected control-message channel, using
// two new generic message types (deployment_command / deployment_command_result)
// introduced in migration 0027 -- rather than one message_type enum value
// per action, a command payload's "action" field discriminates deploy vs.
// scale vs. pause vs. resume vs. rollback vs. terminate. Every command this
// package sends is signed by the platform CA (internal/platform/pki),
// exactly as Milestone 6's deployment-plan-validate messages are; a cluster
// agent independently verifies that signature before ever calling
// internal/platform/clusteradapter -- this package never calls
// clusteradapter itself, since control-api never holds cluster access
// directly (see clusteradapter's package doc).
package deployments

import (
	"time"

	"github.com/google/uuid"
)

// Deployment is the running (fictionally) instance of one committed
// capacity reservation. Like capacity_reservations, it legitimately belongs
// to two scope dimensions (the tenant that owns the workload, the operator
// whose capacity/cluster hosts it), so its RLS uses the same
// three-permissive-policy dual-scope shape.
type Deployment struct {
	ID                    uuid.UUID `json:"id"`
	EnterpriseTenantID    uuid.UUID `json:"enterprise_tenant_id"`
	OperatorID            uuid.UUID `json:"operator_id"`
	ClusterAgentID        uuid.UUID `json:"cluster_agent_id"`
	WorkloadVersionID     uuid.UUID `json:"workload_version_id"`
	CapacityReservationID uuid.UUID `json:"capacity_reservation_id"`
	Namespace             string    `json:"namespace"`
	ReplicaCount          int       `json:"replica_count"`
	Status                string    `json:"status"`
	RequestedBy           uuid.UUID `json:"requested_by"`
	CreatedAt             time.Time `json:"created_at"`
	UpdatedAt             time.Time `json:"updated_at"`
}

// DeploymentPlan is the signed manifest artefact. Manifest is built once at
// draft time (see service.go's buildManifest) and never mutated after that
// -- a rescale via a full manifest change or a rollback creates a new
// version instead of editing an existing row, which is what makes
// manifest_hash/signature meaningful as tamper evidence.
type DeploymentPlan struct {
	ID                 uuid.UUID      `json:"id"`
	DeploymentID       uuid.UUID      `json:"deployment_id"`
	EnterpriseTenantID uuid.UUID      `json:"enterprise_tenant_id"`
	Version            int            `json:"version"`
	Status             string         `json:"status"`
	Manifest           map[string]any `json:"manifest"`
	ManifestHash       string         `json:"manifest_hash"`
	Signature          *string        `json:"signature,omitempty"`
	RequestedBy        uuid.UUID      `json:"requested_by"`
	ApprovedBy         *uuid.UUID     `json:"approved_by,omitempty"`
	RejectedReason     *string        `json:"rejected_reason,omitempty"`
	CreatedAt          time.Time      `json:"created_at"`
	UpdatedAt          time.Time      `json:"updated_at"`
}

// DeploymentEvent is one row of the append-only lifecycle stream --
// user-initiated actions carry ActorUserID; agent-reported outcomes (a
// command result arriving asynchronously) do not.
type DeploymentEvent struct {
	ID                 uuid.UUID      `json:"id"`
	DeploymentID       uuid.UUID      `json:"deployment_id"`
	EnterpriseTenantID uuid.UUID      `json:"enterprise_tenant_id"`
	OperatorID         uuid.UUID      `json:"operator_id"`
	EventType          string         `json:"event_type"`
	Detail             map[string]any `json:"detail"`
	ActorUserID        *uuid.UUID     `json:"actor_user_id,omitempty"`
	CreatedAt          time.Time      `json:"created_at"`
}

// WorkloadSecret is the metadata-only read model. It deliberately has no
// Value field at all -- not merely one omitted from JSON -- so there is no
// struct literal in this package that could accidentally be populated with
// a decrypted value and serialized back out through a session-authenticated
// response. The one code path that does hand a decrypted value to anyone
// (AgentFetchSecrets, in service.go) builds its own unexported response
// shape instead of reusing this type.
type WorkloadSecret struct {
	ID                 uuid.UUID `json:"id"`
	EnterpriseTenantID uuid.UUID `json:"enterprise_tenant_id"`
	WorkloadVersionID  uuid.UUID `json:"workload_version_id"`
	Key                string    `json:"key"`
	CreatedBy          uuid.UUID `json:"created_by"`
	CreatedAt          time.Time `json:"created_at"`
	UpdatedAt          time.Time `json:"updated_at"`
}

// deploymentCommandPayload is the to_agent control-message payload for
// every lifecycle action this package sends -- "action" discriminates
// which one, matching migration 0027's decision to widen message_type
// generically rather than add one enum value per action.
type deploymentCommandPayload struct {
	Action       string         `json:"action"`
	DeploymentID string         `json:"deployment_id"`
	Namespace    string         `json:"namespace,omitempty"`
	Manifest     map[string]any `json:"manifest,omitempty"`
	ReplicaCount int            `json:"replica_count,omitempty"`
	// PlanVersion identifies which deployment_plans row a "deploy" or
	// "rollback" action's manifest came from, so AgentReportCommandResult
	// can mark exactly that version active (and supersede the rest)
	// without needing extra server-side state beyond the original message.
	PlanVersion int `json:"plan_version,omitempty"`
}

// deploymentCommandResult is the from_agent response body a cluster agent
// signs and posts back -- see AgentReportCommandResult in service.go.
type deploymentCommandResult struct {
	Action   string `json:"action"`
	Success  bool   `json:"success"`
	Detail   string `json:"detail"`
	Nonce    string `json:"nonce"`
	SignedAt string `json:"signed_at"`
}
