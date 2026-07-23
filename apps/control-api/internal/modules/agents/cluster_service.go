package agents

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
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/pki"
	"gridkeep/control-api/internal/platform/security"
)

// signedAtWindow bounds how far a signed message's claimed signing time may
// drift from the server's clock before it is rejected -- the second half
// of replay protection alongside the nonce-uniqueness constraint: a
// captured, valid signature over a stale timestamp is rejected even if its
// nonce happens not to collide (e.g. an attacker who captured a message
// before it was ever submitted).
const signedAtWindow = 5 * time.Minute

var (
	ErrClusterAgentNotFound   = errors.New("cluster agent not found for this operator")
	ErrNoActiveClusterAgent   = errors.New("cluster has no active cluster agent")
	ErrControlMessageNotFound = errors.New("control message not found")
	ErrReplay                 = errors.New("nonce already used or signing time outside the acceptance window")
	ErrUnknownReservation     = errors.New("capacity reservation does not exist for this operator")
)

// ---------------------------------------------------------------------
// Cluster agent registration / revocation (session-authenticated,
// operator.agents.manage) -- mirrors RegisterAgent/RevokeAgent exactly,
// scoped one level narrower.
// ---------------------------------------------------------------------

func (s *Service) RegisterClusterAgent(ctx context.Context, clusterID uuid.UUID, name string) (ClusterAgent, string, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := registry.ClusterBelongsToOperator(ctx, scopedTx.Tx, clusterID, *scope.OperatorID)
	if err != nil {
		return ClusterAgent{}, "", err
	}
	if !ok {
		return ClusterAgent{}, "", ErrUnknownCluster
	}

	rawToken, tokenHash, err := security.GenerateOpaqueToken(32)
	if err != nil {
		return ClusterAgent{}, "", err
	}

	a, err := createClusterAgent(ctx, scopedTx.Tx, *scope.OperatorID, clusterID, name, *actor, tokenHash, time.Now().Add(s.cfg.BootstrapTokenTTL))
	if err != nil {
		return ClusterAgent{}, "", err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "agents.cluster_agent_registered", TargetType: "cluster_agent", TargetID: &a.ID,
		Evidence: map[string]any{"name": name, "cluster_id": clusterID},
	}); err != nil {
		return ClusterAgent{}, "", err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ClusterAgent{}, "", err
	}
	return a, rawToken, nil
}

func (s *Service) ListClusterAgents(ctx context.Context) ([]ClusterAgent, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listClusterAgents(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) ListClusterAgentCertificates(ctx context.Context, agentID uuid.UUID) ([]ClusterAgentCertificate, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	ok, err := clusterAgentBelongsToOperator(ctx, scopedTx.Tx, agentID, *scope.OperatorID)
	if err != nil {
		return nil, err
	}
	if !ok {
		return nil, ErrClusterAgentNotFound
	}
	return listClusterAgentCertificates(ctx, scopedTx.Tx, *scope.OperatorID, agentID)
}

func (s *Service) RevokeClusterAgent(ctx context.Context, agentID uuid.UUID, reason string) error {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := clusterAgentBelongsToOperator(ctx, scopedTx.Tx, agentID, *scope.OperatorID)
	if err != nil {
		return err
	}
	if !ok {
		return ErrClusterAgentNotFound
	}
	if err := markClusterAgentRevoked(ctx, scopedTx.Tx, *scope.OperatorID, agentID); err != nil {
		return err
	}
	if err := revokeAllClusterAgentCertificates(ctx, scopedTx.Tx, *scope.OperatorID, agentID, reason); err != nil {
		return err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "agents.cluster_agent_revoked", TargetType: "cluster_agent", TargetID: &agentID,
		Evidence: map[string]any{"reason": reason},
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

// ---------------------------------------------------------------------
// Bootstrap (unauthenticated -- mirrors Bootstrap exactly)
// ---------------------------------------------------------------------

func (s *Service) ClusterAgentBootstrap(ctx context.Context, rawToken string, csrPEM []byte) (certPEM, serialNumber string, expiresAt time.Time, err error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return "", "", time.Time{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	tokenHash := security.HashToken(rawToken)
	operatorID, agentID, ok, cerr := consumeClusterAgentBootstrapToken(ctx, tx, tokenHash)
	if cerr != nil {
		return "", "", time.Time{}, cerr
	}
	if !ok {
		return "", "", time.Time{}, ErrInvalidBootstrapToken
	}

	certPEM, serialNumber, expiresAt, err = s.ca.SignCSR(csrPEM, agentID.String(), s.cfg.CertificateTTL)
	if err != nil {
		return "", "", time.Time{}, fmt.Errorf("%w: %v", ErrInvalidCSR, err)
	}
	if _, err := createClusterAgentCertificate(ctx, tx, operatorID, agentID, serialNumber, certPEM, expiresAt, nil); err != nil {
		return "", "", time.Time{}, err
	}
	if err := markClusterAgentActive(ctx, tx, agentID); err != nil {
		return "", "", time.Time{}, err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ScopeType: audit.ScopeOperator, ScopeID: &operatorID,
		Action: "agents.cluster_agent_certificate_issued", TargetType: "cluster_agent", TargetID: &agentID,
		Evidence: map[string]any{"serial_number": serialNumber, "expires_at": expiresAt},
	}); err != nil {
		return "", "", time.Time{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return "", "", time.Time{}, fmt.Errorf("commit cluster agent bootstrap: %w", err)
	}
	return certPEM, serialNumber, expiresAt, nil
}

// ---------------------------------------------------------------------
// Certificate rotation (machine-authenticated: proof of possession of the
// CURRENT certificate's private key, via a signature over the new CSR's
// raw bytes, is what authorizes issuing a replacement -- there is no
// bootstrap token involved, since the agent already has a trusted identity
// it is renewing, not establishing for the first time).
// ---------------------------------------------------------------------

func (s *Service) RotateClusterAgentCertificate(ctx context.Context, agentID uuid.UUID, csrPEM []byte, signatureB64 string) (certPEM, serialNumber string, expiresAt time.Time, err error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return "", "", time.Time{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	operatorID, ok, cerr := clusterAgentOperatorID(ctx, tx, agentID)
	if cerr != nil {
		return "", "", time.Time{}, cerr
	}
	if !ok {
		return "", "", time.Time{}, ErrNoTrustedCertificate
	}
	currentCertID, currentCertPEM, ok, cerr := currentValidClusterAgentCertificate(ctx, tx, operatorID, agentID)
	if cerr != nil {
		return "", "", time.Time{}, cerr
	}
	if !ok {
		return "", "", time.Time{}, ErrNoTrustedCertificate
	}
	valid, verr := pki.VerifySignature(currentCertPEM, csrPEM, signatureB64)
	if verr != nil {
		return "", "", time.Time{}, fmt.Errorf("%w: %v", ErrInvalidSignature, verr)
	}
	if !valid {
		return "", "", time.Time{}, ErrInvalidSignature
	}

	certPEM, serialNumber, expiresAt, err = s.ca.SignCSR(csrPEM, agentID.String(), s.cfg.CertificateTTL)
	if err != nil {
		return "", "", time.Time{}, fmt.Errorf("%w: %v", ErrInvalidCSR, err)
	}
	if _, err := createClusterAgentCertificate(ctx, tx, operatorID, agentID, serialNumber, certPEM, expiresAt, &currentCertID); err != nil {
		return "", "", time.Time{}, err
	}
	if err := revokeClusterAgentCertificate(ctx, tx, currentCertID, "rotated"); err != nil {
		return "", "", time.Time{}, err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ScopeType: audit.ScopeOperator, ScopeID: &operatorID,
		Action: "agents.cluster_agent_certificate_rotated", TargetType: "cluster_agent", TargetID: &agentID,
		Evidence: map[string]any{"previous_certificate_id": currentCertID, "new_serial_number": serialNumber},
	}); err != nil {
		return "", "", time.Time{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return "", "", time.Time{}, fmt.Errorf("commit certificate rotation: %w", err)
	}
	return certPEM, serialNumber, expiresAt, nil
}

// RotateOperatorAgentCertificate is the same capability for Milestone 2's
// original operator-wide agent identity -- certificate rotation is a
// property of the agent model generally, not something unique to cluster
// agents.
func (s *Service) RotateOperatorAgentCertificate(ctx context.Context, agentID uuid.UUID, csrPEM []byte, signatureB64 string) (certPEM, serialNumber string, expiresAt time.Time, err error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return "", "", time.Time{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	operatorID, ok, cerr := agentOperatorID(ctx, tx, agentID)
	if cerr != nil {
		return "", "", time.Time{}, cerr
	}
	if !ok {
		return "", "", time.Time{}, ErrNoTrustedCertificate
	}
	currentCertID, currentCertPEM, ok, cerr := currentValidOperatorAgentCertificate(ctx, tx, operatorID, agentID)
	if cerr != nil {
		return "", "", time.Time{}, cerr
	}
	if !ok {
		return "", "", time.Time{}, ErrNoTrustedCertificate
	}
	valid, verr := pki.VerifySignature(currentCertPEM, csrPEM, signatureB64)
	if verr != nil {
		return "", "", time.Time{}, fmt.Errorf("%w: %v", ErrInvalidSignature, verr)
	}
	if !valid {
		return "", "", time.Time{}, ErrInvalidSignature
	}

	certPEM, serialNumber, expiresAt, err = s.ca.SignCSR(csrPEM, agentID.String(), s.cfg.CertificateTTL)
	if err != nil {
		return "", "", time.Time{}, fmt.Errorf("%w: %v", ErrInvalidCSR, err)
	}
	if _, err := createRotatedOperatorAgentCertificate(ctx, tx, operatorID, agentID, serialNumber, certPEM, expiresAt, currentCertID); err != nil {
		return "", "", time.Time{}, err
	}
	if err := revokeOperatorAgentCertificate(ctx, tx, currentCertID, "rotated"); err != nil {
		return "", "", time.Time{}, err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ScopeType: audit.ScopeOperator, ScopeID: &operatorID,
		Action: "agents.operator_agent_certificate_rotated", TargetType: "operator_agent", TargetID: &agentID,
		Evidence: map[string]any{"previous_certificate_id": currentCertID, "new_serial_number": serialNumber},
	}); err != nil {
		return "", "", time.Time{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return "", "", time.Time{}, fmt.Errorf("commit certificate rotation: %w", err)
	}
	return certPEM, serialNumber, expiresAt, nil
}

// ---------------------------------------------------------------------
// Deployment-plan validation request (session-authenticated, operator side)
// -- stands in for what Milestone 7's real orchestrator will eventually
// trigger automatically once it exists; this milestone only builds the
// cluster agent's receive/validate/respond machinery, not a real plan
// producer.
// ---------------------------------------------------------------------

func (s *Service) RequestDeploymentPlanValidation(ctx context.Context, clusterID uuid.UUID, workloadVersionID, capacityReservationID *uuid.UUID, namespace string, resourceQuota, networkPolicy, securityContext map[string]any) (ControlMessage, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := registry.ClusterBelongsToOperator(ctx, scopedTx.Tx, clusterID, *scope.OperatorID)
	if err != nil {
		return ControlMessage{}, err
	}
	if !ok {
		return ControlMessage{}, ErrUnknownCluster
	}
	if capacityReservationID != nil {
		reservationOperatorID, exists, rerr := capacityReservationOperatorID(ctx, scopedTx.Tx, *capacityReservationID)
		if rerr != nil {
			return ControlMessage{}, rerr
		}
		if !exists || reservationOperatorID != *scope.OperatorID {
			return ControlMessage{}, ErrUnknownReservation
		}
	}

	agentID, agentOK, err := activeClusterAgentForCluster(ctx, scopedTx.Tx, *scope.OperatorID, clusterID)
	if err != nil {
		return ControlMessage{}, err
	}
	if !agentOK {
		return ControlMessage{}, ErrNoActiveClusterAgent
	}

	planID := uuid.NewString()
	var workloadVersionIDStr, capacityReservationIDStr *string
	if workloadVersionID != nil {
		v := workloadVersionID.String()
		workloadVersionIDStr = &v
	}
	if capacityReservationID != nil {
		v := capacityReservationID.String()
		capacityReservationIDStr = &v
	}
	plan := DeploymentPlanPayload{
		PlanID: planID, ClusterID: clusterID.String(), WorkloadVersionID: workloadVersionIDStr,
		CapacityReservationID: capacityReservationIDStr, Namespace: namespace,
		ResourceQuota: resourceQuota, NetworkPolicy: networkPolicy, SecurityContext: securityContext,
	}
	planJSON, err := json.Marshal(plan)
	if err != nil {
		return ControlMessage{}, fmt.Errorf("marshal deployment plan: %w", err)
	}
	signature, err := s.ca.SignMessage(planJSON)
	if err != nil {
		return ControlMessage{}, fmt.Errorf("sign deployment plan: %w", err)
	}
	nonce, err := generateNonce()
	if err != nil {
		return ControlMessage{}, err
	}

	signedAt := time.Now()
	msg, err := createControlMessage(ctx, scopedTx.Tx, *scope.OperatorID, agentID, "to_agent", "deployment_plan_validate", nil, nonce, planJSON, signature, signedAt, "pending")
	if err != nil {
		return ControlMessage{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "agents.deployment_plan_validation_requested", TargetType: "cluster_agent", TargetID: &agentID,
		Evidence: map[string]any{"plan_id": planID, "cluster_id": clusterID},
	}); err != nil {
		return ControlMessage{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ControlMessage{}, err
	}
	return msg, nil
}

func (s *Service) ListControlMessages(ctx context.Context, agentID uuid.UUID) ([]ControlMessage, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	ok, err := clusterAgentBelongsToOperator(ctx, scopedTx.Tx, agentID, *scope.OperatorID)
	if err != nil {
		return nil, err
	}
	if !ok {
		return nil, ErrClusterAgentNotFound
	}
	return listControlMessages(ctx, scopedTx.Tx, *scope.OperatorID, agentID)
}

func (s *Service) ListDeploymentPlanValidations(ctx context.Context, agentID uuid.UUID) ([]DeploymentPlanValidation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	ok, err := clusterAgentBelongsToOperator(ctx, scopedTx.Tx, agentID, *scope.OperatorID)
	if err != nil {
		return nil, err
	}
	if !ok {
		return nil, ErrClusterAgentNotFound
	}
	return listDeploymentPlanValidations(ctx, scopedTx.Tx, *scope.OperatorID, agentID)
}

// ---------------------------------------------------------------------
// Agent-facing poll/respond (machine-authenticated: a valid signature made
// with the agent's current certificate proves identity; no session, no
// RLS-derived operator scope -- exactly SubmitCapacitySnapshot's posture).
// ---------------------------------------------------------------------

// PollPendingControlMessages verifies the poll request itself was signed
// by the agent's current certificate within the acceptance window, then
// returns every 'to_agent' message still awaiting a response. The poll
// itself is read-only and idempotent, so unlike RespondToControlMessage it
// does not need nonce-uniqueness tracking -- replaying an old, valid poll
// request just re-fetches the same pending list, not a security-relevant
// action.
func (s *Service) PollPendingControlMessages(ctx context.Context, agentID uuid.UUID, nonce, signedAtRFC3339, signatureB64 string) ([]ControlMessage, error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return nil, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	_, certPEM, ok, err := currentClusterAgentIdentity(ctx, tx, agentID)
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
	challenge := pollChallenge(agentID, nonce, signedAtRFC3339)
	valid, err := pki.VerifySignature(certPEM, []byte(challenge), signatureB64)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrInvalidSignature, err)
	}
	if !valid {
		return nil, ErrInvalidSignature
	}
	return listPendingControlMessages(ctx, tx, agentID)
}

func pollChallenge(agentID uuid.UUID, nonce, signedAtRFC3339 string) string {
	return fmt.Sprintf("poll:%s:%s:%s", agentID, nonce, signedAtRFC3339)
}

type respondInput struct {
	Decision    string   `json:"decision"`
	ReasonCodes []string `json:"reason_codes"`
	Nonce       string   `json:"nonce"`
	SignedAt    string   `json:"signed_at"`
}

// RespondToControlMessage is where a cluster agent reports back the
// decision it reached through its own local enforcement (signature
// verification and policy check performed on the agent side, not here --
// see cmd/mockclusteragent). This is the security-critical direction:
// rawBody's signature is verified against the agent's current certificate,
// its nonce must not have been used by this agent before (the actual
// replay-protection mechanism, enforced by controlMessageNonceExists
// before any insert), and its claimed signing time must fall within the
// acceptance window.
func (s *Service) RespondToControlMessage(ctx context.Context, agentID, messageID uuid.UUID, rawBody []byte, signatureB64 string) (DeploymentPlanValidation, error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return DeploymentPlanValidation{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	operatorID, certPEM, ok, err := currentClusterAgentIdentity(ctx, tx, agentID)
	if err != nil {
		return DeploymentPlanValidation{}, err
	}
	if !ok {
		return DeploymentPlanValidation{}, ErrNoTrustedCertificate
	}

	valid, err := pki.VerifySignature(certPEM, rawBody, signatureB64)
	if err != nil {
		return DeploymentPlanValidation{}, fmt.Errorf("%w: %v", ErrInvalidSignature, err)
	}
	if !valid {
		return DeploymentPlanValidation{}, ErrInvalidSignature
	}

	var body respondInput
	if err := json.Unmarshal(rawBody, &body); err != nil {
		return DeploymentPlanValidation{}, fmt.Errorf("decode response body: %w", err)
	}
	if body.Decision != "allow" && body.Decision != "deny" {
		return DeploymentPlanValidation{}, fmt.Errorf("decision must be \"allow\" or \"deny\"")
	}
	signedAt, err := time.Parse(time.RFC3339, body.SignedAt)
	if err != nil {
		return DeploymentPlanValidation{}, fmt.Errorf("%w: invalid signed_at", ErrReplay)
	}
	if time.Since(signedAt).Abs() > signedAtWindow {
		return DeploymentPlanValidation{}, ErrReplay
	}
	nonceUsed, err := controlMessageNonceExists(ctx, tx, agentID, body.Nonce)
	if err != nil {
		return DeploymentPlanValidation{}, err
	}
	if nonceUsed {
		return DeploymentPlanValidation{}, ErrReplay
	}

	original, exists, err := getControlMessageByID(ctx, tx, agentID, messageID)
	if err != nil {
		return DeploymentPlanValidation{}, err
	}
	if !exists || original.Status != "pending" || original.MessageType != "deployment_plan_validate" {
		return DeploymentPlanValidation{}, ErrControlMessageNotFound
	}

	responseMsg, err := createControlMessage(ctx, tx, operatorID, agentID, "from_agent", "deployment_plan_validation_result",
		&messageID, body.Nonce, rawBody, signatureB64, signedAt, "responded")
	if err != nil {
		return DeploymentPlanValidation{}, err
	}
	if ok, err := markControlMessageResponded(ctx, tx, messageID); err != nil {
		return DeploymentPlanValidation{}, err
	} else if !ok {
		return DeploymentPlanValidation{}, ErrControlMessageNotFound
	}

	var originalPlan map[string]any
	if err := json.Unmarshal(original.Payload, &originalPlan); err != nil {
		return DeploymentPlanValidation{}, fmt.Errorf("decode original plan payload: %w", err)
	}
	planID, _ := originalPlan["plan_id"].(string)
	var workloadVersionID, capacityReservationID *uuid.UUID
	if v, ok := originalPlan["workload_version_id"].(string); ok && v != "" {
		if id, err := uuid.Parse(v); err == nil {
			workloadVersionID = &id
		}
	}
	if v, ok := originalPlan["capacity_reservation_id"].(string); ok && v != "" {
		if id, err := uuid.Parse(v); err == nil {
			capacityReservationID = &id
		}
	}

	validation, err := createDeploymentPlanValidation(ctx, tx, operatorID, agentID, responseMsg.ID, planID,
		workloadVersionID, capacityReservationID, true, body.Decision, body.ReasonCodes, signedAt)
	if err != nil {
		return DeploymentPlanValidation{}, err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ScopeType: audit.ScopeOperator, ScopeID: &operatorID,
		Action: "agents.deployment_plan_validated", TargetType: "cluster_agent", TargetID: &agentID,
		Evidence: map[string]any{"plan_id": planID, "decision": body.Decision, "reason_codes": body.ReasonCodes},
	}); err != nil {
		return DeploymentPlanValidation{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return DeploymentPlanValidation{}, fmt.Errorf("commit control message response: %w", err)
	}
	return validation, nil
}

// currentClusterAgentIdentity resolves both the owning operator and the
// current valid certificate PEM for a cluster agent in one call -- every
// machine-authenticated cluster-agent endpoint needs both.
func currentClusterAgentIdentity(ctx context.Context, c conn, agentID uuid.UUID) (operatorID uuid.UUID, certPEM string, ok bool, err error) {
	operatorID, ok, err = clusterAgentOperatorID(ctx, c, agentID)
	if err != nil || !ok {
		return uuid.Nil, "", false, err
	}
	_, certPEM, ok, err = currentValidClusterAgentCertificate(ctx, c, operatorID, agentID)
	if err != nil || !ok {
		return uuid.Nil, "", false, err
	}
	return operatorID, certPEM, true, nil
}

// activeClusterAgentForCluster picks the single active cluster agent
// registered for a cluster, if any. This milestone's model is one agent
// per cluster at a time (mirroring one kubelet-equivalent process per
// cluster); if an operator has registered more than one (e.g. mid
// migration to a replacement agent), the most recently created active one
// is used.
func activeClusterAgentForCluster(ctx context.Context, c conn, operatorID, clusterID uuid.UUID) (uuid.UUID, bool, error) {
	agents, err := listClusterAgents(ctx, c, operatorID)
	if err != nil {
		return uuid.Nil, false, err
	}
	for _, a := range agents {
		if a.ClusterID == clusterID && a.Status == "active" {
			return a.ID, true, nil
		}
	}
	return uuid.Nil, false, nil
}

// PlatformCACertificatePEM returns the platform CA's own certificate --
// public information a cluster agent fetches once so it can verify every
// subsequently received control message's signature.
func (s *Service) PlatformCACertificatePEM() string {
	return s.ca.CertificatePEM()
}

func generateNonce() (string, error) {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return "", fmt.Errorf("generate nonce: %w", err)
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}
