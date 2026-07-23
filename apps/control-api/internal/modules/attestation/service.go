package attestation

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/modules/registry"
	attestationpkg "gridkeep/control-api/internal/platform/attestation"
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
	"gridkeep/control-api/internal/platform/pki"
)

// sessionTTL bounds how long an issued attestation challenge remains
// redeemable -- short, since its only job is to prove the evidence being
// submitted right now was produced after this specific challenge was
// issued, not to serve as a long-lived credential.
const sessionTTL = 5 * time.Minute

// signedAtWindow bounds how far a submission's claimed signing time may
// drift from the server's clock -- the same replay-protection window
// Milestone 6/7 established, duplicated here per this codebase's
// established convention of small per-consumer primitives.
const signedAtWindow = 5 * time.Minute

var (
	ErrClusterNotFound      = errors.New("cluster does not exist for this operator")
	ErrPolicyNotFound       = errors.New("attestation policy not found")
	ErrClusterAgentNotFound = errors.New("cluster agent not found for this operator")
	ErrDeploymentNotFound   = errors.New("deployment not found")
	ErrNoTrustedCertificate = errors.New("no currently valid certificate for this cluster agent")
	ErrInvalidSignature     = errors.New("signature verification failed")
	ErrReplay               = errors.New("attestation session invalid, expired, or already used")
	ErrNotAssignedAgent     = errors.New("this cluster agent is not the one assigned to the deployment")
)

type Service struct {
	store    *dbpkg.Store
	provider attestationpkg.Provider
}

func NewService(store *dbpkg.Store, provider attestationpkg.Provider) *Service {
	return &Service{store: store, provider: provider}
}

func actorFromContext(ctx context.Context) uuid.UUID {
	if authUser, ok := httpserver.AuthUser(ctx); ok {
		return authUser.UserID
	}
	return uuid.Nil
}

// ---------------------------------------------------------------------
// Attestation policies (operator-scoped, operator.attestation.manage)
// ---------------------------------------------------------------------

// CreatePolicy supersedes any existing active policy for the cluster in
// the same transaction (see supersedeActivePolicyForCluster) -- a policy's
// expected_measurements are immutable once created; a "new version" is a
// new row, the previous one revoked with a fixed, descriptive reason.
func (s *Service) CreatePolicy(ctx context.Context, clusterID uuid.UUID, providerType string, expectedMeasurements map[string]any) (AttestationPolicy, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	operatorID := *scope.OperatorID

	ok, err := registry.ClusterBelongsToOperator(ctx, scopedTx.Tx, clusterID, operatorID)
	if err != nil {
		return AttestationPolicy{}, err
	}
	if !ok {
		return AttestationPolicy{}, ErrClusterNotFound
	}

	if err := supersedeActivePolicyForCluster(ctx, scopedTx.Tx, clusterID, actor); err != nil {
		return AttestationPolicy{}, err
	}
	policy, err := createAttestationPolicy(ctx, scopedTx.Tx, operatorID, clusterID, providerType, expectedMeasurements, actor)
	if err != nil {
		return AttestationPolicy{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "attestation.policy_created", TargetType: "attestation_policy", TargetID: &policy.ID,
		Evidence: map[string]any{"cluster_id": clusterID, "provider_type": providerType},
	}); err != nil {
		return AttestationPolicy{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return AttestationPolicy{}, err
	}
	return policy, nil
}

func (s *Service) ListPolicies(ctx context.Context) ([]AttestationPolicy, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listAttestationPolicies(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) RevokePolicy(ctx context.Context, policyID uuid.UUID, reason string) (AttestationPolicy, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	operatorID := *scope.OperatorID

	policy, exists, err := getAttestationPolicyByID(ctx, scopedTx.Tx, operatorID, policyID)
	if err != nil {
		return AttestationPolicy{}, err
	}
	if !exists {
		return AttestationPolicy{}, ErrPolicyNotFound
	}
	ok, err := revokeAttestationPolicy(ctx, scopedTx.Tx, policyID, actor, reason)
	if err != nil {
		return AttestationPolicy{}, err
	}
	if !ok {
		return AttestationPolicy{}, ErrPolicyNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "attestation.policy_revoked", TargetType: "attestation_policy", TargetID: &policyID,
		Evidence: map[string]any{"cluster_id": policy.ClusterID, "reason": reason},
	}); err != nil {
		return AttestationPolicy{}, err
	}
	updated, exists, err := getAttestationPolicyByID(ctx, scopedTx.Tx, operatorID, policyID)
	if err != nil {
		return AttestationPolicy{}, err
	}
	if !exists {
		return AttestationPolicy{}, ErrPolicyNotFound
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return AttestationPolicy{}, err
	}
	return updated, nil
}

// ---------------------------------------------------------------------
// Results (view-only; operator membership / enterprise membership, no
// dedicated permission -- mirrors Milestone 6's control-message/validation
// history: view is membership, manage/mutate is a permission)
// ---------------------------------------------------------------------

func (s *Service) ListOperatorResults(ctx context.Context, agentID uuid.UUID) ([]AttestationResult, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	operatorID := *scope.OperatorID

	ok, err := clusterAgentBelongsToOperator(ctx, scopedTx.Tx, agentID, operatorID)
	if err != nil {
		return nil, err
	}
	if !ok {
		return nil, ErrClusterAgentNotFound
	}
	return listAttestationResultsForOperatorAgent(ctx, scopedTx.Tx, operatorID, agentID)
}

func (s *Service) ListTenantResults(ctx context.Context, deploymentID uuid.UUID) ([]RedactedAttestationResult, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	tenantID := *scope.TenantID

	ok, err := deploymentBelongsToTenant(ctx, scopedTx.Tx, deploymentID, tenantID)
	if err != nil {
		return nil, err
	}
	if !ok {
		return nil, ErrDeploymentNotFound
	}
	return listAttestationResultsForTenant(ctx, scopedTx.Tx, tenantID, deploymentID)
}

// ---------------------------------------------------------------------
// Agent-facing (machine-authenticated, no session -- identity proved by a
// signature made with the calling cluster agent's current certificate,
// exactly Milestone 6/7's posture for every other agent-facing endpoint)
// ---------------------------------------------------------------------

func challengeString(agentID uuid.UUID, nonce, signedAtRFC3339 string) string {
	return fmt.Sprintf("attestation-session:%s:%s:%s", agentID, nonce, signedAtRFC3339)
}

// RequestSession verifies the request itself was signed by the agent's
// current certificate within the acceptance window, then mints and
// persists a fresh, server-chosen attestation nonce -- see the package doc
// and migration 0028 for why control-api, not the agent, mints this value.
func (s *Service) RequestSession(ctx context.Context, agentID uuid.UUID, requestNonce, signedAtRFC3339, signatureB64 string) (AttestationSession, error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return AttestationSession{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	operatorID, _, certPEM, ok, err := clusterAgentIdentity(ctx, tx, agentID)
	if err != nil {
		return AttestationSession{}, err
	}
	if !ok {
		return AttestationSession{}, ErrNoTrustedCertificate
	}
	signedAt, err := time.Parse(time.RFC3339, signedAtRFC3339)
	if err != nil {
		return AttestationSession{}, fmt.Errorf("%w: invalid signed_at", ErrReplay)
	}
	if time.Since(signedAt).Abs() > signedAtWindow {
		return AttestationSession{}, ErrReplay
	}
	valid, err := pki.VerifySignature(certPEM, []byte(challengeString(agentID, requestNonce, signedAtRFC3339)), signatureB64)
	if err != nil {
		return AttestationSession{}, fmt.Errorf("%w: %v", ErrInvalidSignature, err)
	}
	if !valid {
		return AttestationSession{}, ErrInvalidSignature
	}

	attestationNonce, err := generateNonce()
	if err != nil {
		return AttestationSession{}, err
	}
	session, err := createAttestationSession(ctx, tx, operatorID, agentID, attestationNonce, time.Now().Add(sessionTTL))
	if err != nil {
		return AttestationSession{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return AttestationSession{}, fmt.Errorf("commit attestation session: %w", err)
	}
	return session, nil
}

// SubmitEvidence is the security-critical direction: verifies the agent's
// signature over the exact submitted bytes, atomically consumes the
// session (rejecting an expired or already-used one, or a nonce that does
// not match), confirms the referenced deployment is actually assigned to
// this agent, runs internal/platform/attestation.Provider.Verify against
// the cluster's current active policy (or fails closed with
// NO_ACTIVE_POLICY if none exists), and records the outcome as an
// immutable AttestationResult.
func (s *Service) SubmitEvidence(ctx context.Context, agentID, sessionID uuid.UUID, rawBody []byte, signatureB64 string) (AttestationResult, error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return AttestationResult{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	operatorID, clusterID, certPEM, ok, err := clusterAgentIdentity(ctx, tx, agentID)
	if err != nil {
		return AttestationResult{}, err
	}
	if !ok {
		return AttestationResult{}, ErrNoTrustedCertificate
	}
	valid, err := pki.VerifySignature(certPEM, rawBody, signatureB64)
	if err != nil {
		return AttestationResult{}, fmt.Errorf("%w: %v", ErrInvalidSignature, err)
	}
	if !valid {
		return AttestationResult{}, ErrInvalidSignature
	}

	var body evidenceSubmission
	if err := json.Unmarshal(rawBody, &body); err != nil {
		return AttestationResult{}, fmt.Errorf("decode evidence submission: %w", err)
	}
	signedAt, err := time.Parse(time.RFC3339, body.SignedAt)
	if err != nil {
		return AttestationResult{}, fmt.Errorf("%w: invalid signed_at", ErrReplay)
	}
	if time.Since(signedAt).Abs() > signedAtWindow {
		return AttestationResult{}, ErrReplay
	}

	session, ok, err := consumeAttestationSession(ctx, tx, sessionID, agentID)
	if err != nil {
		return AttestationResult{}, err
	}
	if !ok {
		return AttestationResult{}, ErrReplay
	}
	if body.Nonce != session.Nonce {
		return AttestationResult{}, ErrReplay
	}

	deploymentID, err := uuid.Parse(body.DeploymentID)
	if err != nil {
		return AttestationResult{}, fmt.Errorf("decode deployment_id: %w", err)
	}
	facts, exists, err := getDeploymentFacts(ctx, tx, deploymentID)
	if err != nil {
		return AttestationResult{}, err
	}
	if !exists {
		return AttestationResult{}, ErrDeploymentNotFound
	}
	if facts.ClusterAgentID != agentID {
		return AttestationResult{}, ErrNotAssignedAgent
	}

	evaluatedAt := time.Now()
	policy, policyExists, err := currentActivePolicyForCluster(ctx, tx, clusterID)
	if err != nil {
		return AttestationResult{}, err
	}

	var result attestationpkg.Result
	var policyID *uuid.UUID
	if !policyExists {
		result = attestationpkg.Result{Decision: attestationpkg.DecisionFail, ReasonCodes: []string{"NO_ACTIVE_POLICY"}}
	} else {
		policyID = &policy.ID
		result, err = s.provider.Verify(ctx, attestationpkg.Policy{
			ProviderType: policy.ProviderType, ExpectedMeasurements: policy.ExpectedMeasurements,
		}, attestationpkg.Evidence{
			ProviderType: body.ProviderType, Measurements: body.Measurements, RawEvidence: body.RawEvidence,
		})
		if err != nil {
			return AttestationResult{}, fmt.Errorf("verify attestation evidence: %w", err)
		}
	}

	record, err := createAttestationResult(ctx, tx, operatorID, facts.EnterpriseTenantID, agentID, session.ID, policyID,
		deploymentID, body.ProviderType, body.Measurements, body.RawEvidence, result.Decision, result.ReasonCodes,
		body.Nonce, signatureB64, evaluatedAt)
	if err != nil {
		return AttestationResult{}, err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ScopeType: audit.ScopeOperator, ScopeID: &operatorID,
		Action: "attestation.evidence_submitted", TargetType: "deployment", TargetID: &deploymentID,
		Evidence: map[string]any{"cluster_agent_id": agentID, "decision": result.Decision, "reason_codes": result.ReasonCodes},
	}); err != nil {
		return AttestationResult{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return AttestationResult{}, fmt.Errorf("commit attestation result: %w", err)
	}
	return record, nil
}

func generateNonce() (string, error) {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return "", fmt.Errorf("generate nonce: %w", err)
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}

// clusterAgentBelongsToOperator and deploymentBelongsToTenant are small,
// package-local ownership checks -- duplicated rather than imported from
// internal/modules/agents/internal/modules/deployments, per this
// codebase's established convention (see repository.go's doc comment on
// clusterAgentIdentity).
func clusterAgentBelongsToOperator(ctx context.Context, c conn, agentID, operatorID uuid.UUID) (bool, error) {
	var exists bool
	err := c.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM cluster_agents WHERE id = $1 AND operator_id = $2)`, agentID, operatorID).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("check cluster agent ownership: %w", err)
	}
	return exists, nil
}

func deploymentBelongsToTenant(ctx context.Context, c conn, deploymentID, tenantID uuid.UUID) (bool, error) {
	var exists bool
	err := c.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM deployments WHERE id = $1 AND enterprise_tenant_id = $2)`, deploymentID, tenantID).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("check deployment ownership: %w", err)
	}
	return exists, nil
}
