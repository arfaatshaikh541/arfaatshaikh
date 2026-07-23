package agents

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

// conn is satisfied by both *pgxpool.Pool and pgx.Tx, matching the pattern
// every other module's repository layer uses.
type conn interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

// ---------------------------------------------------------------------
// Operator agents
// ---------------------------------------------------------------------

func createOperatorAgent(ctx context.Context, c conn, operatorID uuid.UUID, name string, registeredBy uuid.UUID, bootstrapTokenHash string, bootstrapExpiresAt time.Time) (OperatorAgent, error) {
	var a OperatorAgent
	err := c.QueryRow(ctx, `
		INSERT INTO operator_agents (operator_id, name, registered_by, bootstrap_token_hash, bootstrap_token_expires_at)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, operator_id, name, status, created_at, updated_at
	`, operatorID, name, registeredBy, bootstrapTokenHash, bootstrapExpiresAt).Scan(&a.ID, &a.OperatorID, &a.Name, &a.Status, &a.CreatedAt, &a.UpdatedAt)
	if err != nil {
		return OperatorAgent{}, fmt.Errorf("insert operator agent: %w", err)
	}
	return a, nil
}

func listOperatorAgents(ctx context.Context, c conn, operatorID uuid.UUID) ([]OperatorAgent, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, name, status, created_at, updated_at
		FROM operator_agents WHERE operator_id = $1 ORDER BY created_at DESC
	`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list operator agents: %w", err)
	}
	defer rows.Close()

	var out []OperatorAgent
	for rows.Next() {
		var a OperatorAgent
		if err := rows.Scan(&a.ID, &a.OperatorID, &a.Name, &a.Status, &a.CreatedAt, &a.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan operator agent: %w", err)
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

func agentBelongsToOperator(ctx context.Context, c conn, id, operatorID uuid.UUID) (bool, error) {
	var exists bool
	err := c.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM operator_agents WHERE id = $1 AND operator_id = $2)`, id, operatorID).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("check agent ownership: %w", err)
	}
	return exists, nil
}

// agentOperatorID resolves an agent's owning operator by agent ID alone --
// used only by the signed, session-less capacity-snapshot ingestion path,
// where the caller authenticates by proving possession of the agent's
// certificate private key rather than by presenting an already-scoped
// operator session.
func agentOperatorID(ctx context.Context, c conn, agentID uuid.UUID) (uuid.UUID, bool, error) {
	var operatorID uuid.UUID
	err := c.QueryRow(ctx, `SELECT operator_id FROM operator_agents WHERE id = $1 AND status = 'active'`, agentID).Scan(&operatorID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, false, nil
		}
		return uuid.Nil, false, fmt.Errorf("resolve agent operator: %w", err)
	}
	return operatorID, true, nil
}

// consumeBootstrapToken atomically finds the still-valid, unconsumed
// bootstrap token matching tokenHash and marks it consumed in the same
// statement, returning the agent's operator_id and id. It does not also
// mark the agent active -- that happens only once the CSR it authorizes has
// actually been signed successfully (see Service.Bootstrap), in the same
// transaction as this consumption so both succeed or both roll back
// together (unlike the MFA-challenge bug fixed in the Milestone 1 audit,
// there is no fallible "guess" step here after consumption -- CSR signing
// either succeeds for the legitimate holder or the whole request fails and
// the token is correctly left consumable again for a retry).
func consumeBootstrapToken(ctx context.Context, c conn, tokenHash string) (operatorID, agentID uuid.UUID, ok bool, err error) {
	err = c.QueryRow(ctx, `
		UPDATE operator_agents
		SET bootstrap_consumed_at = now()
		WHERE bootstrap_token_hash = $1
		  AND bootstrap_consumed_at IS NULL
		  AND bootstrap_token_expires_at > now()
		  AND status = 'pending_bootstrap'
		RETURNING operator_id, id
	`, tokenHash).Scan(&operatorID, &agentID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, uuid.Nil, false, nil
		}
		return uuid.Nil, uuid.Nil, false, fmt.Errorf("consume bootstrap token: %w", err)
	}
	return operatorID, agentID, true, nil
}

func markAgentActive(ctx context.Context, c conn, agentID uuid.UUID) error {
	_, err := c.Exec(ctx, `UPDATE operator_agents SET status = 'active', updated_at = now() WHERE id = $1`, agentID)
	if err != nil {
		return fmt.Errorf("mark agent active: %w", err)
	}
	return nil
}

func markAgentRevoked(ctx context.Context, c conn, operatorID, agentID uuid.UUID) error {
	tag, err := c.Exec(ctx, `
		UPDATE operator_agents SET status = 'revoked', updated_at = now()
		WHERE id = $1 AND operator_id = $2
	`, agentID, operatorID)
	if err != nil {
		return fmt.Errorf("mark agent revoked: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return pgx.ErrNoRows
	}
	return nil
}

// ---------------------------------------------------------------------
// Agent certificates
// ---------------------------------------------------------------------

func createAgentCertificate(ctx context.Context, c conn, operatorID, agentID uuid.UUID, serialNumber, certPEM string, expiresAt time.Time) (AgentCertificate, error) {
	var cert AgentCertificate
	err := c.QueryRow(ctx, `
		INSERT INTO agent_certificates (operator_id, operator_agent_id, serial_number, certificate_pem, expires_at)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, operator_id, operator_agent_id, serial_number, issued_at, expires_at, revoked_at, revoked_reason
	`, operatorID, agentID, serialNumber, certPEM, expiresAt).Scan(
		&cert.ID, &cert.OperatorID, &cert.OperatorAgentID, &cert.SerialNumber, &cert.IssuedAt, &cert.ExpiresAt, &cert.RevokedAt, &cert.RevokedReason)
	if err != nil {
		return AgentCertificate{}, fmt.Errorf("insert agent certificate: %w", err)
	}
	return cert, nil
}

func listAgentCertificates(ctx context.Context, c conn, operatorID, agentID uuid.UUID) ([]AgentCertificate, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, operator_agent_id, serial_number, issued_at, expires_at, revoked_at, revoked_reason
		FROM agent_certificates WHERE operator_id = $1 AND operator_agent_id = $2 ORDER BY issued_at DESC
	`, operatorID, agentID)
	if err != nil {
		return nil, fmt.Errorf("list agent certificates: %w", err)
	}
	defer rows.Close()

	var out []AgentCertificate
	for rows.Next() {
		var cert AgentCertificate
		if err := rows.Scan(&cert.ID, &cert.OperatorID, &cert.OperatorAgentID, &cert.SerialNumber, &cert.IssuedAt, &cert.ExpiresAt, &cert.RevokedAt, &cert.RevokedReason); err != nil {
			return nil, fmt.Errorf("scan agent certificate: %w", err)
		}
		out = append(out, cert)
	}
	return out, rows.Err()
}

// currentValidCertificatePEM returns the PEM of the most recently issued,
// still-unrevoked, unexpired certificate for the given agent, if any --
// exactly the certificate a capacity-snapshot signature must verify
// against.
func currentValidCertificatePEM(ctx context.Context, c conn, operatorID, agentID uuid.UUID) (string, bool, error) {
	var pem string
	err := c.QueryRow(ctx, `
		SELECT certificate_pem FROM agent_certificates
		WHERE operator_id = $1 AND operator_agent_id = $2
		  AND revoked_at IS NULL AND expires_at > now()
		ORDER BY issued_at DESC LIMIT 1
	`, operatorID, agentID).Scan(&pem)
	if err != nil {
		if err == pgx.ErrNoRows {
			return "", false, nil
		}
		return "", false, fmt.Errorf("load current agent certificate: %w", err)
	}
	return pem, true, nil
}

func revokeCurrentCertificates(ctx context.Context, c conn, operatorID, agentID uuid.UUID, reason string) error {
	_, err := c.Exec(ctx, `
		UPDATE agent_certificates SET revoked_at = now(), revoked_reason = $3
		WHERE operator_id = $1 AND operator_agent_id = $2 AND revoked_at IS NULL
	`, operatorID, agentID, reason)
	if err != nil {
		return fmt.Errorf("revoke agent certificates: %w", err)
	}
	return nil
}

// ---------------------------------------------------------------------
// Capacity snapshots
// ---------------------------------------------------------------------

func createCapacitySnapshot(ctx context.Context, c conn, operatorID, agentID, clusterID uuid.UUID, payload map[string]any, collectedAt time.Time, signature string) (CapacitySnapshot, error) {
	payloadJSON, err := json.Marshal(payload)
	if err != nil {
		return CapacitySnapshot{}, fmt.Errorf("marshal capacity snapshot payload: %w", err)
	}
	var cs CapacitySnapshot
	var rawPayload []byte
	err = c.QueryRow(ctx, `
		INSERT INTO capacity_snapshots (operator_id, operator_agent_id, cluster_id, source, trust_status, payload, signature, collected_at)
		VALUES ($1, $2, $3, 'operator_agent', 'verified', $4, $5, $6)
		RETURNING id, operator_id, operator_agent_id, cluster_id, source, trust_status, payload, collected_at, created_at
	`, operatorID, agentID, clusterID, payloadJSON, signature, collectedAt).Scan(
		&cs.ID, &cs.OperatorID, &cs.OperatorAgentID, &cs.ClusterID, &cs.Source, &cs.TrustStatus, &rawPayload, &cs.CollectedAt, &cs.CreatedAt)
	if err != nil {
		return CapacitySnapshot{}, fmt.Errorf("insert capacity snapshot: %w", err)
	}
	if err := json.Unmarshal(rawPayload, &cs.Payload); err != nil {
		return CapacitySnapshot{}, fmt.Errorf("unmarshal stored payload: %w", err)
	}
	return cs, nil
}

func listCapacitySnapshots(ctx context.Context, c conn, operatorID uuid.UUID) ([]CapacitySnapshot, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, operator_agent_id, cluster_id, source, trust_status, payload, collected_at, created_at
		FROM capacity_snapshots WHERE operator_id = $1 ORDER BY collected_at DESC LIMIT 200
	`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list capacity snapshots: %w", err)
	}
	defer rows.Close()

	var out []CapacitySnapshot
	for rows.Next() {
		var cs CapacitySnapshot
		var rawPayload []byte
		if err := rows.Scan(&cs.ID, &cs.OperatorID, &cs.OperatorAgentID, &cs.ClusterID, &cs.Source, &cs.TrustStatus, &rawPayload, &cs.CollectedAt, &cs.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan capacity snapshot: %w", err)
		}
		if err := json.Unmarshal(rawPayload, &cs.Payload); err != nil {
			return nil, fmt.Errorf("unmarshal stored payload: %w", err)
		}
		out = append(out, cs)
	}
	return out, rows.Err()
}
