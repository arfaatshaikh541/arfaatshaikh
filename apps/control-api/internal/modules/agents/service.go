package agents

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/modules/registry"
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
	"gridkeep/control-api/internal/platform/pki"
	"gridkeep/control-api/internal/platform/security"
)

var (
	ErrInvalidBootstrapToken = errors.New("bootstrap token is invalid, expired, or already used")
	ErrInvalidCSR            = errors.New("certificate signing request is invalid")
	ErrAgentNotFound         = errors.New("agent not found for this operator")
	ErrNoTrustedCertificate  = errors.New("no currently valid certificate for this agent")
	ErrInvalidSignature      = errors.New("signature verification failed")
	ErrUnknownCluster        = errors.New("cluster does not exist for this operator")
)

type Config struct {
	BootstrapTokenTTL time.Duration
	CertificateTTL    time.Duration
}

type Service struct {
	store *dbpkg.Store
	ca    *pki.CA
	cfg   Config
}

func NewService(store *dbpkg.Store, ca *pki.CA, cfg Config) *Service {
	return &Service{store: store, ca: ca, cfg: cfg}
}

func actorFromContext(ctx context.Context) *uuid.UUID {
	if authUser, ok := httpserver.AuthUser(ctx); ok {
		return &authUser.UserID
	}
	return nil
}

// ---------------------------------------------------------------------
// Registration (session-authenticated, operator.agents.manage)
// ---------------------------------------------------------------------

// RegisterAgent creates a new agent record and returns the raw, single-use
// bootstrap token the operator must relay to the agent out of band (it is
// never shown again -- only its hash is persisted).
func (s *Service) RegisterAgent(ctx context.Context, name string) (OperatorAgent, string, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	rawToken, tokenHash, err := security.GenerateOpaqueToken(32)
	if err != nil {
		return OperatorAgent{}, "", err
	}

	a, err := createOperatorAgent(ctx, scopedTx.Tx, *scope.OperatorID, name, *actor, tokenHash, time.Now().Add(s.cfg.BootstrapTokenTTL))
	if err != nil {
		return OperatorAgent{}, "", err
	}

	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actor,
		ScopeType:   audit.ScopeOperator,
		ScopeID:     scope.OperatorID,
		Action:      "agents.agent_registered",
		TargetType:  "operator_agent",
		TargetID:    &a.ID,
		Evidence:    map[string]any{"name": name},
	}); err != nil {
		return OperatorAgent{}, "", err
	}

	if err := scopedTx.Commit(ctx); err != nil {
		return OperatorAgent{}, "", err
	}
	return a, rawToken, nil
}

func (s *Service) ListAgents(ctx context.Context) ([]OperatorAgent, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listOperatorAgents(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) ListAgentCertificates(ctx context.Context, agentID uuid.UUID) ([]AgentCertificate, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	ok, err := agentBelongsToOperator(ctx, scopedTx.Tx, agentID, *scope.OperatorID)
	if err != nil {
		return nil, err
	}
	if !ok {
		return nil, ErrAgentNotFound
	}
	return listAgentCertificates(ctx, scopedTx.Tx, *scope.OperatorID, agentID)
}

func (s *Service) RevokeAgent(ctx context.Context, agentID uuid.UUID, reason string) error {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := agentBelongsToOperator(ctx, scopedTx.Tx, agentID, *scope.OperatorID)
	if err != nil {
		return err
	}
	if !ok {
		return ErrAgentNotFound
	}

	if err := markAgentRevoked(ctx, scopedTx.Tx, *scope.OperatorID, agentID); err != nil {
		return err
	}
	if err := revokeCurrentCertificates(ctx, scopedTx.Tx, *scope.OperatorID, agentID, reason); err != nil {
		return err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: actor,
		ScopeType:   audit.ScopeOperator,
		ScopeID:     scope.OperatorID,
		Action:      "agents.agent_revoked",
		TargetType:  "operator_agent",
		TargetID:    &agentID,
		Evidence:    map[string]any{"reason": reason},
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

// ---------------------------------------------------------------------
// Bootstrap (unauthenticated -- the bootstrap token itself is the
// credential, exactly like an invitation token)
// ---------------------------------------------------------------------

// Bootstrap exchanges a valid, unconsumed bootstrap token and a CSR for a
// signed certificate. It runs as a single transaction: token consumption,
// CSR signing, certificate persistence, and marking the agent active all
// commit together, or none of them do.
func (s *Service) Bootstrap(ctx context.Context, rawToken string, csrPEM []byte) (certPEM, serialNumber string, expiresAt time.Time, err error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return "", "", time.Time{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	tokenHash := security.HashToken(rawToken)
	operatorID, agentID, ok, cerr := consumeBootstrapToken(ctx, tx, tokenHash)
	if cerr != nil {
		return "", "", time.Time{}, cerr
	}
	if !ok {
		return "", "", time.Time{}, ErrInvalidBootstrapToken
	}

	// The CA sets the certificate's Subject from agentID (resolved above
	// from the validated token, never from anything the CSR itself
	// claims) -- see pki.CA.SignCSR.
	certPEM, serialNumber, expiresAt, err = s.ca.SignCSR(csrPEM, agentID.String(), s.cfg.CertificateTTL)
	if err != nil {
		return "", "", time.Time{}, fmt.Errorf("%w: %v", ErrInvalidCSR, err)
	}

	if _, err := createAgentCertificate(ctx, tx, operatorID, agentID, serialNumber, certPEM, expiresAt); err != nil {
		return "", "", time.Time{}, err
	}
	if err := markAgentActive(ctx, tx, agentID); err != nil {
		return "", "", time.Time{}, err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ScopeType:  audit.ScopeOperator,
		ScopeID:    &operatorID,
		Action:     "agents.certificate_issued",
		TargetType: "operator_agent",
		TargetID:   &agentID,
		Evidence:   map[string]any{"serial_number": serialNumber, "expires_at": expiresAt},
	}); err != nil {
		return "", "", time.Time{}, err
	}

	if err := tx.Commit(ctx); err != nil {
		return "", "", time.Time{}, fmt.Errorf("commit bootstrap: %w", err)
	}
	return certPEM, serialNumber, expiresAt, nil
}

// ---------------------------------------------------------------------
// Capacity snapshot ingestion (agent-signed, not session-authenticated)
// ---------------------------------------------------------------------

// SubmitCapacitySnapshot verifies rawBody was signed by the private key
// matching operatorID/agentID's current, unrevoked, unexpired certificate,
// then records the snapshot. There is no user session here, so this
// deliberately opens a platform_bypass transaction rather than relying on
// RLS's session-derived app.operator_id GUC (which has no meaning for a
// machine caller) -- the ECDSA signature check below is the actual
// authorization control for this endpoint, checked in application code
// before any row is read or written for this operator/agent, exactly the
// same "verify before trusting the URL's claimed identity" discipline RLS
// exists to enforce for session-authenticated routes.
func (s *Service) SubmitCapacitySnapshot(ctx context.Context, agentID, clusterID uuid.UUID, rawBody []byte, signatureB64 string, payload map[string]any, collectedAt time.Time) (CapacitySnapshot, error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return CapacitySnapshot{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	operatorID, ok, err := agentOperatorID(ctx, tx, agentID)
	if err != nil {
		return CapacitySnapshot{}, err
	}
	if !ok {
		return CapacitySnapshot{}, ErrNoTrustedCertificate
	}

	certPEM, ok, err := currentValidCertificatePEM(ctx, tx, operatorID, agentID)
	if err != nil {
		return CapacitySnapshot{}, err
	}
	if !ok {
		return CapacitySnapshot{}, ErrNoTrustedCertificate
	}

	valid, err := pki.VerifySignature(certPEM, rawBody, signatureB64)
	if err != nil {
		return CapacitySnapshot{}, fmt.Errorf("%w: %v", ErrInvalidSignature, err)
	}
	if !valid {
		return CapacitySnapshot{}, ErrInvalidSignature
	}

	clusterOK, err := registry.ClusterBelongsToOperator(ctx, tx, clusterID, operatorID)
	if err != nil {
		return CapacitySnapshot{}, err
	}
	if !clusterOK {
		return CapacitySnapshot{}, ErrUnknownCluster
	}

	cs, err := createCapacitySnapshot(ctx, tx, operatorID, agentID, clusterID, payload, collectedAt, signatureB64)
	if err != nil {
		return CapacitySnapshot{}, err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ScopeType:  audit.ScopeOperator,
		ScopeID:    &operatorID,
		Action:     "agents.capacity_snapshot_ingested",
		TargetType: "cluster",
		TargetID:   &clusterID,
		Evidence:   map[string]any{"operator_agent_id": agentID, "capacity_snapshot_id": cs.ID},
	}); err != nil {
		return CapacitySnapshot{}, err
	}

	if err := tx.Commit(ctx); err != nil {
		return CapacitySnapshot{}, fmt.Errorf("commit capacity snapshot: %w", err)
	}
	return cs, nil
}

func (s *Service) ListCapacitySnapshots(ctx context.Context) ([]CapacitySnapshot, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listCapacitySnapshots(ctx, scopedTx.Tx, *scope.OperatorID)
}
