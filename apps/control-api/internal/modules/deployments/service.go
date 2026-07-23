package deployments

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
	"gridkeep/control-api/internal/platform/pki"
	"gridkeep/control-api/internal/platform/secretsvault"
)

// signedAtWindow bounds how far a machine-authenticated request's claimed
// signing time may drift from the server's clock -- the same
// replay-protection window internal/modules/agents established for
// Milestone 6's control-message channel (duplicated here rather than
// exported from that package, per this codebase's established convention of
// small per-consumer primitives; see repository.go's doc comment on
// activeClusterAgentForCluster).
const signedAtWindow = 5 * time.Minute

// attestationFreshnessWindow bounds how long a passing Milestone 8
// attestation_results row remains acceptable for a key-release decision --
// "freshness" in the approved attestation scope. A confidential-computing-required
// deployment must have attested successfully within this window, not merely
// at some point in its history, before AgentFetchSecrets will decrypt
// anything for it.
const attestationFreshnessWindow = 30 * time.Minute

var (
	ErrReservationNotFound        = errors.New("capacity reservation not found")
	ErrReservationNotCommitted    = errors.New("only a committed capacity reservation can be deployed")
	ErrReservationAlreadyDeployed = errors.New("this capacity reservation already has a deployment")
	ErrNoActiveClusterAgent       = errors.New("the reserved capacity's cluster has no active cluster agent")
	ErrDeploymentNotFound         = errors.New("deployment not found")
	ErrPlanNotFound               = errors.New("deployment plan not found")
	ErrPlanNotDraft               = errors.New("deployment plan is not in draft status")
	ErrPlanNotPendingApproval     = errors.New("deployment plan is not awaiting approval")
	ErrCannotSelfApprovePlan      = errors.New("the same user cannot both request and approve a deployment plan")
	ErrNoApprovedPlan             = errors.New("deployment has no approved plan ready to submit")
	ErrDeploymentNotRunning       = errors.New("deployment is not currently running")
	ErrDeploymentNotPaused        = errors.New("deployment is not currently paused")
	ErrDeploymentNotFailed        = errors.New("deployment is not in a failed state")
	ErrNoRollbackTarget           = errors.New("no executable plan exists at that version to roll back to")
	ErrNoPlanToRetry              = errors.New("deployment has no previously approved or active plan to retry")
	ErrSecretNotFound             = errors.New("workload secret not found")
	ErrNoTrustedCertificate       = errors.New("no currently valid certificate for this cluster agent")
	ErrInvalidSignature           = errors.New("signature verification failed")
	ErrReplay                     = errors.New("nonce already used or signing time outside the acceptance window")
	ErrControlMessageNotFound     = errors.New("control message not found")
	ErrActionMismatch             = errors.New("reported action does not match the original command")
	ErrNotAssignedAgent           = errors.New("this cluster agent is not the one assigned to the deployment")
	ErrAttestationRequired        = errors.New("this deployment requires confidential computing and has no fresh, passing attestation result")
)

type Service struct {
	store *dbpkg.Store
	ca    *pki.CA
	vault *secretsvault.Vault
}

func NewService(store *dbpkg.Store, ca *pki.CA, vault *secretsvault.Vault) *Service {
	return &Service{store: store, ca: ca, vault: vault}
}

func actorFromContext(ctx context.Context) uuid.UUID {
	if authUser, ok := httpserver.AuthUser(ctx); ok {
		return authUser.UserID
	}
	return uuid.Nil
}

// ---------------------------------------------------------------------
// Deployments (enterprise-scoped)
// ---------------------------------------------------------------------

// CreateDeployment turns a Milestone 5 committed capacity_reservation into a
// deployment row -- resolving the owning operator and workload version from
// the reservation itself (never trusted from the request body) and the
// assigned cluster agent from the reservation's capacity offer's cluster.
// One reservation can back at most one deployment (capacity_reservation_id
// is UNIQUE on deployments), so a second attempt against an
// already-deployed reservation is rejected rather than silently creating a
// duplicate.
func (s *Service) CreateDeployment(ctx context.Context, reservationID uuid.UUID, namespace string, replicaCount int) (Deployment, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	facts, exists, err := getReservationFacts(ctx, scopedTx.Tx, tenantID, reservationID)
	if err != nil {
		return Deployment{}, err
	}
	if !exists {
		return Deployment{}, ErrReservationNotFound
	}
	if facts.Status != "committed" {
		return Deployment{}, ErrReservationNotCommitted
	}
	already, err := reservationAlreadyDeployed(ctx, scopedTx.Tx, reservationID)
	if err != nil {
		return Deployment{}, err
	}
	if already {
		return Deployment{}, ErrReservationAlreadyDeployed
	}

	clusterID, err := capacityOfferClusterID(ctx, scopedTx.Tx, facts.CapacityOfferID)
	if err != nil {
		return Deployment{}, err
	}
	var agentID uuid.UUID
	var agentFound bool
	if err := withPlatformBypass(ctx, scopedTx.Tx, func() error {
		var berr error
		agentID, agentFound, berr = activeClusterAgentForCluster(ctx, scopedTx.Tx, clusterID)
		return berr
	}); err != nil {
		return Deployment{}, err
	}
	if !agentFound {
		return Deployment{}, ErrNoActiveClusterAgent
	}

	d, err := createDeployment(ctx, scopedTx.Tx, tenantID, facts.OperatorID, agentID, facts.WorkloadVersionID, reservationID, namespace, replicaCount, actor)
	if err != nil {
		return Deployment{}, err
	}
	if _, err := insertDeploymentEvent(ctx, scopedTx.Tx, d.ID, tenantID, d.OperatorID, "deployment_created",
		map[string]any{"capacity_reservation_id": reservationID, "namespace": namespace, "replica_count": replicaCount}, &actor); err != nil {
		return Deployment{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "deployments.created", TargetType: "deployment", TargetID: &d.ID,
		Evidence: map[string]any{"capacity_reservation_id": reservationID, "cluster_agent_id": agentID},
	}); err != nil {
		return Deployment{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Deployment{}, err
	}
	return d, nil
}

func (s *Service) ListDeployments(ctx context.Context) ([]Deployment, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listDeploymentsForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) GetDeployment(ctx context.Context, id uuid.UUID) (Deployment, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	d, exists, err := getDeploymentByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return Deployment{}, err
	}
	if !exists {
		return Deployment{}, ErrDeploymentNotFound
	}
	return d, nil
}

func (s *Service) ListDeploymentEvents(ctx context.Context, deploymentID uuid.UUID) ([]DeploymentEvent, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listDeploymentEventsForTenant(ctx, scopedTx.Tx, *scope.TenantID, deploymentID)
}

// ---------------------------------------------------------------------
// Deployments (operator-scoped read access -- an operator sees deployments
// running on its own clusters, never anything about the tenant that owns
// them beyond what deployments/deployment_events already carry.)
// ---------------------------------------------------------------------

func (s *Service) ListOperatorDeployments(ctx context.Context) ([]Deployment, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listDeploymentsForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) ListOperatorDeploymentEvents(ctx context.Context, deploymentID uuid.UUID) ([]DeploymentEvent, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listDeploymentEventsForOperator(ctx, scopedTx.Tx, *scope.OperatorID, deploymentID)
}

// ---------------------------------------------------------------------
// Deployment plans (enterprise-scoped, dual-control approval)
// ---------------------------------------------------------------------

// CreatePlan snapshots the deployment's workload version's current
// components (digest-pinned images, command/args/non-secret env), health
// checks, resource/network/security requirement blocks, and the workload
// version's secret *key names* (never values) into a new, immutable plan
// version -- see buildManifest below.
func (s *Service) CreatePlan(ctx context.Context, deploymentID uuid.UUID) (DeploymentPlan, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	d, exists, err := getDeploymentByID(ctx, scopedTx.Tx, tenantID, deploymentID)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if !exists {
		return DeploymentPlan{}, ErrDeploymentNotFound
	}

	facts, exists, err := getWorkloadVersionFacts(ctx, scopedTx.Tx, tenantID, d.WorkloadVersionID)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if !exists {
		return DeploymentPlan{}, ErrDeploymentNotFound
	}
	components, err := listComponentsWithImagesAndHealthChecks(ctx, scopedTx.Tx, tenantID, d.WorkloadVersionID)
	if err != nil {
		return DeploymentPlan{}, err
	}
	secretKeys, err := workloadSecretKeys(ctx, scopedTx.Tx, d.WorkloadVersionID)
	if err != nil {
		return DeploymentPlan{}, err
	}

	manifest := buildManifest(d.Namespace, d.ReplicaCount, facts, components, secretKeys)
	hash, err := manifestHash(manifest)
	if err != nil {
		return DeploymentPlan{}, err
	}
	version, err := nextPlanVersion(ctx, scopedTx.Tx, deploymentID)
	if err != nil {
		return DeploymentPlan{}, err
	}
	plan, err := createDeploymentPlan(ctx, scopedTx.Tx, tenantID, deploymentID, version, manifest, hash, actor)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if _, err := insertDeploymentEvent(ctx, scopedTx.Tx, deploymentID, tenantID, d.OperatorID, "plan_drafted",
		map[string]any{"plan_id": plan.ID, "version": version, "manifest_hash": hash}, &actor); err != nil {
		return DeploymentPlan{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "deployment_plans.drafted", TargetType: "deployment_plan", TargetID: &plan.ID,
		Evidence: map[string]any{"deployment_id": deploymentID, "version": version},
	}); err != nil {
		return DeploymentPlan{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return DeploymentPlan{}, err
	}
	return plan, nil
}

func (s *Service) ListPlans(ctx context.Context, deploymentID uuid.UUID) ([]DeploymentPlan, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listDeploymentPlans(ctx, scopedTx.Tx, *scope.TenantID, deploymentID)
}

func (s *Service) RequestPlanApproval(ctx context.Context, deploymentID, planID uuid.UUID) (DeploymentPlan, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	d, exists, err := getDeploymentByID(ctx, scopedTx.Tx, tenantID, deploymentID)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if !exists {
		return DeploymentPlan{}, ErrDeploymentNotFound
	}
	plan, exists, err := getDeploymentPlanByID(ctx, scopedTx.Tx, tenantID, deploymentID, planID)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if !exists {
		return DeploymentPlan{}, ErrPlanNotFound
	}
	ok, err := setPlanStatus(ctx, scopedTx.Tx, planID, "draft", "pending_approval")
	if err != nil {
		return DeploymentPlan{}, err
	}
	if !ok {
		return DeploymentPlan{}, ErrPlanNotDraft
	}
	if _, err := insertDeploymentEvent(ctx, scopedTx.Tx, deploymentID, tenantID, d.OperatorID, "plan_approval_requested",
		map[string]any{"plan_id": planID, "version": plan.Version}, &actor); err != nil {
		return DeploymentPlan{}, err
	}
	updated, exists, err := getDeploymentPlanByID(ctx, scopedTx.Tx, tenantID, deploymentID, planID)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if !exists {
		return DeploymentPlan{}, ErrPlanNotFound
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return DeploymentPlan{}, err
	}
	return updated, nil
}

// ApprovePlan is the dual-control gate: a genuinely different user than
// whoever drafted the plan must approve it, enforced both here and by the
// deployment_plans_no_self_approval DB CHECK constraint. Approval is also
// where the platform CA signs the plan's manifest hash -- the same
// mechanism (internal/platform/pki.CA.SignMessage) Milestone 6 uses for
// deployment-plan-validate messages -- so a cluster agent can independently
// verify the manifest it eventually receives was genuinely approved, not
// tampered with in transit or in storage.
func (s *Service) ApprovePlan(ctx context.Context, deploymentID, planID uuid.UUID) (DeploymentPlan, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	d, exists, err := getDeploymentByID(ctx, scopedTx.Tx, tenantID, deploymentID)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if !exists {
		return DeploymentPlan{}, ErrDeploymentNotFound
	}
	plan, exists, err := getDeploymentPlanByID(ctx, scopedTx.Tx, tenantID, deploymentID, planID)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if !exists {
		return DeploymentPlan{}, ErrPlanNotFound
	}
	if plan.Status != "pending_approval" {
		return DeploymentPlan{}, ErrPlanNotPendingApproval
	}
	if plan.RequestedBy == actor {
		return DeploymentPlan{}, ErrCannotSelfApprovePlan
	}

	signature, err := s.ca.SignMessage([]byte(plan.ManifestHash))
	if err != nil {
		return DeploymentPlan{}, fmt.Errorf("sign deployment plan manifest: %w", err)
	}
	ok, err := approveDeploymentPlan(ctx, scopedTx.Tx, planID, actor, signature)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if !ok {
		return DeploymentPlan{}, ErrPlanNotPendingApproval
	}
	if err := setDeploymentStatus(ctx, scopedTx.Tx, deploymentID, "plan_approved"); err != nil {
		return DeploymentPlan{}, err
	}
	if _, err := insertDeploymentEvent(ctx, scopedTx.Tx, deploymentID, tenantID, d.OperatorID, "plan_approved",
		map[string]any{"plan_id": planID, "version": plan.Version, "requested_by": plan.RequestedBy}, &actor); err != nil {
		return DeploymentPlan{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "deployment_plans.approved", TargetType: "deployment_plan", TargetID: &planID,
		Evidence: map[string]any{"deployment_id": deploymentID, "requested_by": plan.RequestedBy},
	}); err != nil {
		return DeploymentPlan{}, err
	}
	updated, exists, err := getDeploymentPlanByID(ctx, scopedTx.Tx, tenantID, deploymentID, planID)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if !exists {
		return DeploymentPlan{}, ErrPlanNotFound
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return DeploymentPlan{}, err
	}
	return updated, nil
}

func (s *Service) RejectPlan(ctx context.Context, deploymentID, planID uuid.UUID, reason string) (DeploymentPlan, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	d, exists, err := getDeploymentByID(ctx, scopedTx.Tx, tenantID, deploymentID)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if !exists {
		return DeploymentPlan{}, ErrDeploymentNotFound
	}
	plan, exists, err := getDeploymentPlanByID(ctx, scopedTx.Tx, tenantID, deploymentID, planID)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if !exists {
		return DeploymentPlan{}, ErrPlanNotFound
	}
	ok, err := rejectDeploymentPlan(ctx, scopedTx.Tx, planID, reason)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if !ok {
		return DeploymentPlan{}, ErrPlanNotPendingApproval
	}
	if _, err := insertDeploymentEvent(ctx, scopedTx.Tx, deploymentID, tenantID, d.OperatorID, "plan_rejected",
		map[string]any{"plan_id": planID, "version": plan.Version, "reason": reason}, &actor); err != nil {
		return DeploymentPlan{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "deployment_plans.rejected", TargetType: "deployment_plan", TargetID: &planID,
		Evidence: map[string]any{"deployment_id": deploymentID, "reason": reason},
	}); err != nil {
		return DeploymentPlan{}, err
	}
	updated, exists, err := getDeploymentPlanByID(ctx, scopedTx.Tx, tenantID, deploymentID, planID)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if !exists {
		return DeploymentPlan{}, ErrPlanNotFound
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return DeploymentPlan{}, err
	}
	return updated, nil
}

// ---------------------------------------------------------------------
// Lifecycle actions -- each sends a signed deployment_command control
// message to the deployment's assigned cluster agent and moves the
// deployment into the corresponding in-flight status; the terminal status
// (running/paused/terminated/failed) is only ever set by
// AgentReportCommandResult once the agent reports back what actually
// happened, never optimistically here.
// ---------------------------------------------------------------------

// SubmitPlan sends an approved plan's manifest to the assigned cluster
// agent for execution -- the only path that moves a deployment out of
// pending_plan_approval/plan_approved and into the submitted/running
// lifecycle.
func (s *Service) SubmitPlan(ctx context.Context, deploymentID, planID uuid.UUID) (Deployment, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	d, exists, err := getDeploymentByID(ctx, scopedTx.Tx, tenantID, deploymentID)
	if err != nil {
		return Deployment{}, err
	}
	if !exists {
		return Deployment{}, ErrDeploymentNotFound
	}
	plan, exists, err := getDeploymentPlanByID(ctx, scopedTx.Tx, tenantID, deploymentID, planID)
	if err != nil {
		return Deployment{}, err
	}
	if !exists {
		return Deployment{}, ErrPlanNotFound
	}
	if plan.Status != "approved" {
		return Deployment{}, ErrNoApprovedPlan
	}

	if err := s.sendCommand(ctx, scopedTx.Tx, d, deploymentCommandPayload{
		Action: "deploy", DeploymentID: d.ID.String(), Namespace: d.Namespace,
		Manifest: plan.Manifest, ReplicaCount: d.ReplicaCount, PlanVersion: plan.Version,
	}); err != nil {
		return Deployment{}, err
	}
	if ok, err := setPlanStatus(ctx, scopedTx.Tx, planID, "approved", "submitted"); err != nil {
		return Deployment{}, err
	} else if !ok {
		return Deployment{}, ErrNoApprovedPlan
	}
	if err := setDeploymentStatus(ctx, scopedTx.Tx, deploymentID, "submitted"); err != nil {
		return Deployment{}, err
	}
	if _, err := insertDeploymentEvent(ctx, scopedTx.Tx, deploymentID, tenantID, d.OperatorID, "plan_submitted",
		map[string]any{"plan_id": planID, "version": plan.Version}, &actor); err != nil {
		return Deployment{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "deployments.plan_submitted", TargetType: "deployment", TargetID: &deploymentID,
		Evidence: map[string]any{"plan_id": planID, "version": plan.Version},
	}); err != nil {
		return Deployment{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Deployment{}, err
	}
	d.Status = "submitted"
	return d, nil
}

func (s *Service) Scale(ctx context.Context, deploymentID uuid.UUID, replicaCount int) (Deployment, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	d, exists, err := getDeploymentByID(ctx, scopedTx.Tx, tenantID, deploymentID)
	if err != nil {
		return Deployment{}, err
	}
	if !exists {
		return Deployment{}, ErrDeploymentNotFound
	}
	if d.Status != "running" {
		return Deployment{}, ErrDeploymentNotRunning
	}
	if err := s.sendCommand(ctx, scopedTx.Tx, d, deploymentCommandPayload{
		Action: "scale", DeploymentID: d.ID.String(), ReplicaCount: replicaCount,
	}); err != nil {
		return Deployment{}, err
	}
	if err := setDeploymentStatus(ctx, scopedTx.Tx, deploymentID, "scaling"); err != nil {
		return Deployment{}, err
	}
	if err := s.recordActionAndCommit(ctx, scopedTx, scope, actor, d, deploymentID, "scale_requested", map[string]any{"replica_count": replicaCount}); err != nil {
		return Deployment{}, err
	}
	d.Status = "scaling"
	return d, nil
}

func (s *Service) Pause(ctx context.Context, deploymentID uuid.UUID) (Deployment, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	d, exists, err := getDeploymentByID(ctx, scopedTx.Tx, tenantID, deploymentID)
	if err != nil {
		return Deployment{}, err
	}
	if !exists {
		return Deployment{}, ErrDeploymentNotFound
	}
	if d.Status != "running" {
		return Deployment{}, ErrDeploymentNotRunning
	}
	if err := s.sendCommand(ctx, scopedTx.Tx, d, deploymentCommandPayload{Action: "pause", DeploymentID: d.ID.String()}); err != nil {
		return Deployment{}, err
	}
	if err := setDeploymentStatus(ctx, scopedTx.Tx, deploymentID, "pausing"); err != nil {
		return Deployment{}, err
	}
	if err := s.recordActionAndCommit(ctx, scopedTx, scope, actor, d, deploymentID, "pause_requested", map[string]any{}); err != nil {
		return Deployment{}, err
	}
	d.Status = "pausing"
	return d, nil
}

func (s *Service) Resume(ctx context.Context, deploymentID uuid.UUID) (Deployment, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	d, exists, err := getDeploymentByID(ctx, scopedTx.Tx, tenantID, deploymentID)
	if err != nil {
		return Deployment{}, err
	}
	if !exists {
		return Deployment{}, ErrDeploymentNotFound
	}
	if d.Status != "paused" {
		return Deployment{}, ErrDeploymentNotPaused
	}
	if err := s.sendCommand(ctx, scopedTx.Tx, d, deploymentCommandPayload{Action: "resume", DeploymentID: d.ID.String()}); err != nil {
		return Deployment{}, err
	}
	if err := setDeploymentStatus(ctx, scopedTx.Tx, deploymentID, "resuming"); err != nil {
		return Deployment{}, err
	}
	if err := s.recordActionAndCommit(ctx, scopedTx, scope, actor, d, deploymentID, "resume_requested", map[string]any{}); err != nil {
		return Deployment{}, err
	}
	d.Status = "resuming"
	return d, nil
}

func (s *Service) Terminate(ctx context.Context, deploymentID uuid.UUID) (Deployment, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	d, exists, err := getDeploymentByID(ctx, scopedTx.Tx, tenantID, deploymentID)
	if err != nil {
		return Deployment{}, err
	}
	if !exists {
		return Deployment{}, ErrDeploymentNotFound
	}
	if d.Status == "terminated" || d.Status == "terminating" {
		return Deployment{}, ErrDeploymentNotRunning
	}
	if err := s.sendCommand(ctx, scopedTx.Tx, d, deploymentCommandPayload{Action: "terminate", DeploymentID: d.ID.String()}); err != nil {
		return Deployment{}, err
	}
	if err := setDeploymentStatus(ctx, scopedTx.Tx, deploymentID, "terminating"); err != nil {
		return Deployment{}, err
	}
	if err := s.recordActionAndCommit(ctx, scopedTx, scope, actor, d, deploymentID, "terminate_requested", map[string]any{}); err != nil {
		return Deployment{}, err
	}
	d.Status = "terminating"
	return d, nil
}

// Rollback re-submits a previously executed plan version's already-approved
// manifest -- it does not go through a new draft/approval cycle, since that
// exact manifest was already approved once; deployments.rollback is its own
// permission gate instead.
func (s *Service) Rollback(ctx context.Context, deploymentID uuid.UUID, targetVersion int) (Deployment, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	d, exists, err := getDeploymentByID(ctx, scopedTx.Tx, tenantID, deploymentID)
	if err != nil {
		return Deployment{}, err
	}
	if !exists {
		return Deployment{}, ErrDeploymentNotFound
	}
	plan, exists, err := getDeploymentPlanByVersion(ctx, scopedTx.Tx, tenantID, deploymentID, targetVersion)
	if err != nil {
		return Deployment{}, err
	}
	if !exists || (plan.Status != "active" && plan.Status != "superseded") {
		return Deployment{}, ErrNoRollbackTarget
	}
	if err := s.sendCommand(ctx, scopedTx.Tx, d, deploymentCommandPayload{
		Action: "rollback", DeploymentID: d.ID.String(), Namespace: d.Namespace,
		Manifest: plan.Manifest, ReplicaCount: d.ReplicaCount, PlanVersion: plan.Version,
	}); err != nil {
		return Deployment{}, err
	}
	if err := setDeploymentStatus(ctx, scopedTx.Tx, deploymentID, "rolling_back"); err != nil {
		return Deployment{}, err
	}
	if err := s.recordActionAndCommit(ctx, scopedTx, scope, actor, d, deploymentID, "rollback_requested", map[string]any{"target_version": targetVersion}); err != nil {
		return Deployment{}, err
	}
	d.Status = "rolling_back"
	return d, nil
}

// Retry re-submits the deployment's currently active plan (or, if it has
// never successfully deployed, its most recently approved plan) after a
// failure -- workloads.retry's stated purpose.
func (s *Service) Retry(ctx context.Context, deploymentID uuid.UUID) (Deployment, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	d, exists, err := getDeploymentByID(ctx, scopedTx.Tx, tenantID, deploymentID)
	if err != nil {
		return Deployment{}, err
	}
	if !exists {
		return Deployment{}, ErrDeploymentNotFound
	}
	if d.Status != "failed" {
		return Deployment{}, ErrDeploymentNotFailed
	}
	plan, exists, err := latestPlanByStatuses(ctx, scopedTx.Tx, tenantID, deploymentID, "active", "approved")
	if err != nil {
		return Deployment{}, err
	}
	if !exists {
		return Deployment{}, ErrNoPlanToRetry
	}
	if err := s.sendCommand(ctx, scopedTx.Tx, d, deploymentCommandPayload{
		Action: "deploy", DeploymentID: d.ID.String(), Namespace: d.Namespace,
		Manifest: plan.Manifest, ReplicaCount: d.ReplicaCount, PlanVersion: plan.Version,
	}); err != nil {
		return Deployment{}, err
	}
	if err := setDeploymentStatus(ctx, scopedTx.Tx, deploymentID, "submitted"); err != nil {
		return Deployment{}, err
	}
	if err := s.recordActionAndCommit(ctx, scopedTx, scope, actor, d, deploymentID, "retry_requested", map[string]any{"plan_id": plan.ID, "version": plan.Version}); err != nil {
		return Deployment{}, err
	}
	d.Status = "submitted"
	return d, nil
}

// sendCommand signs and persists a to_agent deployment_command control
// message -- the same signed, replay-protected mechanism Milestone 6
// established (a fresh random nonce, the platform CA's signature over the
// exact payload bytes), addressed to the one cluster agent assigned to this
// deployment. Every caller of sendCommand runs inside a tenant-scoped
// transaction (only app.tenant_id is set), but control_messages is
// operator-scoped RLS (control_messages_operator_scope/_platform_bypass
// only -- see migration 0026), so the insert itself needs the same
// withPlatformBypass elevation CreateDeployment's cluster-agent lookup uses.
func (s *Service) sendCommand(ctx context.Context, tx conn, d Deployment, payload deploymentCommandPayload) error {
	payloadJSON, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("encode deployment command: %w", err)
	}
	signature, err := s.ca.SignMessage(payloadJSON)
	if err != nil {
		return fmt.Errorf("sign deployment command: %w", err)
	}
	nonce, err := generateNonce()
	if err != nil {
		return err
	}
	return withPlatformBypass(ctx, tx, func() error {
		_, err := createControlMessage(ctx, tx, d.OperatorID, d.ClusterAgentID, "to_agent", "deployment_command",
			nil, nonce, payloadJSON, signature, time.Now(), "pending")
		return err
	})
}

// recordActionAndCommit is the small, repeated tail shared by every
// lifecycle action above: write the append-only event, write the audit
// record, commit.
func (s *Service) recordActionAndCommit(ctx context.Context, scopedTx *rbac.ScopedTx, scope rbac.Scope, actor uuid.UUID, d Deployment, deploymentID uuid.UUID, eventType string, detail map[string]any) error {
	if _, err := insertDeploymentEvent(ctx, scopedTx.Tx, deploymentID, d.EnterpriseTenantID, d.OperatorID, eventType, detail, &actor); err != nil {
		return err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "deployments." + eventType, TargetType: "deployment", TargetID: &deploymentID,
		Evidence: detail,
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

// buildManifest assembles the immutable manifest snapshot a plan signs and
// a cluster agent eventually executes. Secret values never appear here --
// only the key names a deployed workload's environment is expected to
// receive; a cluster agent fetches the actual decrypted values separately,
// through AgentFetchSecrets, only once it holds an executing deployment
// referencing them.
func buildManifest(namespace string, replicaCount int, facts workloadVersionFacts, components []componentFacts, secretKeys []string) map[string]any {
	componentDocs := make([]map[string]any, 0, len(components))
	for _, comp := range components {
		healthChecks := make([]map[string]any, 0, len(comp.HealthChecks))
		for _, hc := range comp.HealthChecks {
			healthChecks = append(healthChecks, map[string]any{
				"check_type": hc.CheckType, "path": hc.Path, "port": hc.Port, "command": hc.Command,
				"interval_seconds": hc.IntervalSeconds, "timeout_seconds": hc.TimeoutSeconds, "failure_threshold": hc.FailureThreshold,
			})
		}
		componentDocs = append(componentDocs, map[string]any{
			"component_key": comp.ComponentKey, "name": comp.Name, "image": comp.Image,
			"command": comp.Command, "args": comp.Args, "env": comp.Env, "is_primary": comp.IsPrimary,
			"health_checks": healthChecks,
		})
	}
	if secretKeys == nil {
		secretKeys = []string{}
	}
	return map[string]any{
		"namespace":             namespace,
		"replica_count":         replicaCount,
		"components":            componentDocs,
		"secret_keys":           secretKeys,
		"resource_requirements": facts.ResourceRequirements,
		"network_requirements":  facts.NetworkRequirements,
		"security_requirements": facts.SecurityRequirements,
	}
}

func manifestHash(manifest map[string]any) (string, error) {
	raw, err := json.Marshal(manifest)
	if err != nil {
		return "", fmt.Errorf("encode manifest for hashing: %w", err)
	}
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:]), nil
}

func generateNonce() (string, error) {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return "", fmt.Errorf("generate nonce: %w", err)
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}

// ---------------------------------------------------------------------
// Workload secrets (values encrypted at rest; never returned decrypted by
// any session-authenticated route)
// ---------------------------------------------------------------------

func (s *Service) CreateWorkloadSecret(ctx context.Context, workloadVersionID uuid.UUID, key, value string) (WorkloadSecret, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	encrypted, err := s.vault.Encrypt(value)
	if err != nil {
		return WorkloadSecret{}, fmt.Errorf("encrypt workload secret: %w", err)
	}
	secret, err := createWorkloadSecret(ctx, scopedTx.Tx, tenantID, workloadVersionID, key, encrypted, actor)
	if err != nil {
		return WorkloadSecret{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "workload_secrets.created", TargetType: "workload_secret", TargetID: &secret.ID,
		Evidence: map[string]any{"workload_version_id": workloadVersionID, "key": key},
	}); err != nil {
		return WorkloadSecret{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return WorkloadSecret{}, err
	}
	return secret, nil
}

func (s *Service) ListWorkloadSecrets(ctx context.Context, workloadVersionID uuid.UUID) ([]WorkloadSecret, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listWorkloadSecrets(ctx, scopedTx.Tx, *scope.TenantID, workloadVersionID)
}

func (s *Service) DeleteWorkloadSecret(ctx context.Context, workloadVersionID, secretID uuid.UUID) error {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	ok, err := deleteWorkloadSecret(ctx, scopedTx.Tx, tenantID, workloadVersionID, secretID)
	if err != nil {
		return err
	}
	if !ok {
		return ErrSecretNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "workload_secrets.deleted", TargetType: "workload_secret", TargetID: &secretID,
		Evidence: map[string]any{"workload_version_id": workloadVersionID},
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

// ---------------------------------------------------------------------
// Agent-facing (machine-authenticated, no session -- identity proved by a
// signature made with the calling cluster agent's current certificate,
// exactly Milestone 6's PollPendingControlMessages/RespondToControlMessage
// posture)
// ---------------------------------------------------------------------

func agentChallenge(agentID, deploymentID uuid.UUID, nonce, signedAtRFC3339 string) string {
	return fmt.Sprintf("agent-secrets:%s:%s:%s:%s", agentID, deploymentID, nonce, signedAtRFC3339)
}

// AgentFetchSecrets is the one path in this codebase authorized to hand
// back decrypted workload secret values -- and only to the single cluster
// agent this specific deployment is assigned to (deployments.cluster_agent_id),
// never to any other agent, operator, or tenant session. It never touches a
// session-derived RLS scope: a machine caller has none, so, like every
// other agent-facing method in this codebase, it opens a platform_bypass
// transaction and treats the verified signature as the authorization
// control instead.
func (s *Service) AgentFetchSecrets(ctx context.Context, agentID, deploymentID uuid.UUID, nonce, signedAtRFC3339, signatureB64 string) (map[string]string, error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return nil, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	_, certPEM, ok, err := clusterAgentIdentity(ctx, tx, agentID)
	if err != nil {
		return nil, err
	}
	if !ok {
		return nil, ErrNoTrustedCertificate
	}
	signedAt, err := time.Parse(time.RFC3339, signedAtRFC3339)
	if err != nil {
		return nil, fmt.Errorf("%w: invalid signed_at", ErrReplay)
	}
	if time.Since(signedAt).Abs() > signedAtWindow {
		return nil, ErrReplay
	}
	valid, err := pki.VerifySignature(certPEM, []byte(agentChallenge(agentID, deploymentID, nonce, signedAtRFC3339)), signatureB64)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrInvalidSignature, err)
	}
	if !valid {
		return nil, ErrInvalidSignature
	}

	d, exists, err := getDeploymentByIDAnyScope(ctx, tx, deploymentID)
	if err != nil {
		return nil, err
	}
	if !exists {
		return nil, ErrDeploymentNotFound
	}
	if d.ClusterAgentID != agentID {
		return nil, ErrNotAssignedAgent
	}

	requiresAttestation, err := workloadVersionRequiresConfidentialComputing(ctx, tx, d.WorkloadVersionID)
	if err != nil {
		return nil, err
	}
	if requiresAttestation {
		passed, err := latestAttestationPasses(ctx, tx, deploymentID, time.Now().Add(-attestationFreshnessWindow))
		if err != nil {
			return nil, err
		}
		if !passed {
			return nil, ErrAttestationRequired
		}
	}

	rows, err := listWorkloadSecretsWithValues(ctx, tx, d.WorkloadVersionID)
	if err != nil {
		return nil, err
	}
	out := make(map[string]string, len(rows))
	for _, row := range rows {
		plaintext, err := s.vault.Decrypt(row.EncryptedValue)
		if err != nil {
			return nil, fmt.Errorf("decrypt workload secret %q: %w", row.Key, err)
		}
		out[row.Key] = plaintext
	}
	if err := tx.Commit(ctx); err != nil {
		return nil, fmt.Errorf("commit agent secret fetch: %w", err)
	}
	return out, nil
}

// AgentReportCommandResult records a cluster agent's signed report of what
// happened when it executed a deployment_command -- the deployments-owned
// counterpart to Milestone 6's RespondToControlMessage, which is hardcoded
// to the deployment_plan_validate flow and cannot handle these newer
// message types (see its MessageType == "deployment_plan_validate" check).
// Replay protection is identical: signature verified against the agent's
// current certificate, nonce uniqueness checked before any write, claimed
// signing time bounded by signedAtWindow.
func (s *Service) AgentReportCommandResult(ctx context.Context, agentID, messageID uuid.UUID, rawBody []byte, signatureB64 string) (DeploymentEvent, error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return DeploymentEvent{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	operatorID, certPEM, ok, err := clusterAgentIdentity(ctx, tx, agentID)
	if err != nil {
		return DeploymentEvent{}, err
	}
	if !ok {
		return DeploymentEvent{}, ErrNoTrustedCertificate
	}
	valid, err := pki.VerifySignature(certPEM, rawBody, signatureB64)
	if err != nil {
		return DeploymentEvent{}, fmt.Errorf("%w: %v", ErrInvalidSignature, err)
	}
	if !valid {
		return DeploymentEvent{}, ErrInvalidSignature
	}

	var body deploymentCommandResult
	if err := json.Unmarshal(rawBody, &body); err != nil {
		return DeploymentEvent{}, fmt.Errorf("decode command result: %w", err)
	}
	signedAt, err := time.Parse(time.RFC3339, body.SignedAt)
	if err != nil {
		return DeploymentEvent{}, fmt.Errorf("%w: invalid signed_at", ErrReplay)
	}
	if time.Since(signedAt).Abs() > signedAtWindow {
		return DeploymentEvent{}, ErrReplay
	}
	nonceUsed, err := controlMessageNonceExists(ctx, tx, agentID, body.Nonce)
	if err != nil {
		return DeploymentEvent{}, err
	}
	if nonceUsed {
		return DeploymentEvent{}, ErrReplay
	}

	original, exists, err := getPendingCommandMessage(ctx, tx, agentID, messageID)
	if err != nil {
		return DeploymentEvent{}, err
	}
	if !exists {
		return DeploymentEvent{}, ErrControlMessageNotFound
	}
	if original.Action != body.Action {
		return DeploymentEvent{}, ErrActionMismatch
	}
	deploymentID, err := uuid.Parse(original.DeploymentID)
	if err != nil {
		return DeploymentEvent{}, fmt.Errorf("decode original command deployment_id: %w", err)
	}

	if _, err := createControlMessage(ctx, tx, operatorID, agentID, "from_agent", "deployment_command_result",
		&messageID, body.Nonce, rawBody, signatureB64, signedAt, "responded"); err != nil {
		return DeploymentEvent{}, err
	}
	if ok, err := markControlMessageResponded(ctx, tx, messageID); err != nil {
		return DeploymentEvent{}, err
	} else if !ok {
		return DeploymentEvent{}, ErrControlMessageNotFound
	}

	d, exists, err := getDeploymentByIDAnyScope(ctx, tx, deploymentID)
	if err != nil {
		return DeploymentEvent{}, err
	}
	if !exists {
		return DeploymentEvent{}, ErrDeploymentNotFound
	}

	newStatus := resolveStatusAfterCommand(body.Action, body.Success)
	if body.Action == "scale" && body.Success {
		if err := setDeploymentStatusAndReplicaCount(ctx, tx, deploymentID, newStatus, original.ReplicaCount); err != nil {
			return DeploymentEvent{}, err
		}
	} else {
		if err := setDeploymentStatus(ctx, tx, deploymentID, newStatus); err != nil {
			return DeploymentEvent{}, err
		}
	}

	if body.Success && (body.Action == "deploy" || body.Action == "rollback") && original.PlanVersion > 0 {
		plan, exists, err := getDeploymentPlanByVersionAnyScope(ctx, tx, deploymentID, original.PlanVersion)
		if err != nil {
			return DeploymentEvent{}, err
		}
		if exists {
			if err := setPlanStatusUnconditional(ctx, tx, plan.ID, "active"); err != nil {
				return DeploymentEvent{}, err
			}
			if err := supersedeActivePlans(ctx, tx, deploymentID, plan.ID); err != nil {
				return DeploymentEvent{}, err
			}
		}
	}

	event, err := insertDeploymentEvent(ctx, tx, deploymentID, d.EnterpriseTenantID, d.OperatorID, "command_result:"+body.Action,
		map[string]any{"success": body.Success, "detail": body.Detail, "plan_version": original.PlanVersion}, nil)
	if err != nil {
		return DeploymentEvent{}, err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ScopeType: audit.ScopeOperator, ScopeID: &operatorID,
		Action: "deployments.command_result", TargetType: "deployment", TargetID: &deploymentID,
		Evidence: map[string]any{"action": body.Action, "success": body.Success, "cluster_agent_id": agentID},
	}); err != nil {
		return DeploymentEvent{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return DeploymentEvent{}, fmt.Errorf("commit command result: %w", err)
	}
	return event, nil
}

// resolveStatusAfterCommand maps a reported action+success pair to the
// deployment's next terminal status -- any failure lands on 'failed'
// (workloads.retry exists specifically so an operator/tenant can recover
// from it), any success lands on the status that action's name implies.
func resolveStatusAfterCommand(action string, success bool) string {
	if !success {
		return "failed"
	}
	switch action {
	case "deploy", "rollback", "scale", "resume":
		return "running"
	case "pause":
		return "paused"
	case "terminate":
		return "terminated"
	default:
		return "failed"
	}
}
