package agents

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

// ---------------------------------------------------------------------
// Cluster agents
// ---------------------------------------------------------------------

func createClusterAgent(ctx context.Context, c conn, operatorID, clusterID uuid.UUID, name string, registeredBy uuid.UUID, bootstrapTokenHash string, bootstrapExpiresAt time.Time) (ClusterAgent, error) {
	var a ClusterAgent
	err := c.QueryRow(ctx, `
		INSERT INTO cluster_agents (operator_id, cluster_id, name, registered_by, bootstrap_token_hash, bootstrap_token_expires_at)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, operator_id, cluster_id, name, status, created_at, updated_at
	`, operatorID, clusterID, name, registeredBy, bootstrapTokenHash, bootstrapExpiresAt).Scan(
		&a.ID, &a.OperatorID, &a.ClusterID, &a.Name, &a.Status, &a.CreatedAt, &a.UpdatedAt)
	if err != nil {
		return ClusterAgent{}, fmt.Errorf("insert cluster agent: %w", err)
	}
	return a, nil
}

func listClusterAgents(ctx context.Context, c conn, operatorID uuid.UUID) ([]ClusterAgent, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, cluster_id, name, status, created_at, updated_at
		FROM cluster_agents WHERE operator_id = $1 ORDER BY created_at DESC
	`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list cluster agents: %w", err)
	}
	defer rows.Close()

	var out []ClusterAgent
	for rows.Next() {
		var a ClusterAgent
		if err := rows.Scan(&a.ID, &a.OperatorID, &a.ClusterID, &a.Name, &a.Status, &a.CreatedAt, &a.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan cluster agent: %w", err)
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

func clusterAgentBelongsToOperator(ctx context.Context, c conn, id, operatorID uuid.UUID) (bool, error) {
	var exists bool
	err := c.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM cluster_agents WHERE id = $1 AND operator_id = $2)`, id, operatorID).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("check cluster agent ownership: %w", err)
	}
	return exists, nil
}

// clusterAgentOperatorID resolves a cluster agent's owning operator by
// agent ID alone -- used only by machine-authenticated paths (poll,
// respond, rotate) where the caller proves identity by certificate
// signature rather than by presenting an operator session.
func clusterAgentOperatorID(ctx context.Context, c conn, agentID uuid.UUID) (uuid.UUID, bool, error) {
	var operatorID uuid.UUID
	err := c.QueryRow(ctx, `SELECT operator_id FROM cluster_agents WHERE id = $1 AND status = 'active'`, agentID).Scan(&operatorID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, false, nil
		}
		return uuid.Nil, false, fmt.Errorf("resolve cluster agent operator: %w", err)
	}
	return operatorID, true, nil
}

func consumeClusterAgentBootstrapToken(ctx context.Context, c conn, tokenHash string) (operatorID, agentID uuid.UUID, ok bool, err error) {
	err = c.QueryRow(ctx, `
		UPDATE cluster_agents
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
		return uuid.Nil, uuid.Nil, false, fmt.Errorf("consume cluster agent bootstrap token: %w", err)
	}
	return operatorID, agentID, true, nil
}

func markClusterAgentActive(ctx context.Context, c conn, agentID uuid.UUID) error {
	_, err := c.Exec(ctx, `UPDATE cluster_agents SET status = 'active', updated_at = now() WHERE id = $1`, agentID)
	if err != nil {
		return fmt.Errorf("mark cluster agent active: %w", err)
	}
	return nil
}

func markClusterAgentRevoked(ctx context.Context, c conn, operatorID, agentID uuid.UUID) error {
	tag, err := c.Exec(ctx, `
		UPDATE cluster_agents SET status = 'revoked', updated_at = now()
		WHERE id = $1 AND operator_id = $2
	`, agentID, operatorID)
	if err != nil {
		return fmt.Errorf("mark cluster agent revoked: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return pgx.ErrNoRows
	}
	return nil
}

// ---------------------------------------------------------------------
// Cluster agent certificates (including rotation lineage)
// ---------------------------------------------------------------------

func createClusterAgentCertificate(ctx context.Context, c conn, operatorID, agentID uuid.UUID, serialNumber, certPEM string, expiresAt time.Time, rotatedFrom *uuid.UUID) (ClusterAgentCertificate, error) {
	var cert ClusterAgentCertificate
	err := c.QueryRow(ctx, `
		INSERT INTO cluster_agent_certificates (operator_id, cluster_agent_id, serial_number, certificate_pem, expires_at, rotated_from_certificate_id)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, operator_id, cluster_agent_id, serial_number, rotated_from_certificate_id, issued_at, expires_at, revoked_at, revoked_reason
	`, operatorID, agentID, serialNumber, certPEM, expiresAt, rotatedFrom).Scan(
		&cert.ID, &cert.OperatorID, &cert.ClusterAgentID, &cert.SerialNumber, &cert.RotatedFromCertificateID,
		&cert.IssuedAt, &cert.ExpiresAt, &cert.RevokedAt, &cert.RevokedReason)
	if err != nil {
		return ClusterAgentCertificate{}, fmt.Errorf("insert cluster agent certificate: %w", err)
	}
	return cert, nil
}

func listClusterAgentCertificates(ctx context.Context, c conn, operatorID, agentID uuid.UUID) ([]ClusterAgentCertificate, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, cluster_agent_id, serial_number, rotated_from_certificate_id, issued_at, expires_at, revoked_at, revoked_reason
		FROM cluster_agent_certificates WHERE operator_id = $1 AND cluster_agent_id = $2 ORDER BY issued_at DESC
	`, operatorID, agentID)
	if err != nil {
		return nil, fmt.Errorf("list cluster agent certificates: %w", err)
	}
	defer rows.Close()

	var out []ClusterAgentCertificate
	for rows.Next() {
		var cert ClusterAgentCertificate
		if err := rows.Scan(&cert.ID, &cert.OperatorID, &cert.ClusterAgentID, &cert.SerialNumber, &cert.RotatedFromCertificateID,
			&cert.IssuedAt, &cert.ExpiresAt, &cert.RevokedAt, &cert.RevokedReason); err != nil {
			return nil, fmt.Errorf("scan cluster agent certificate: %w", err)
		}
		out = append(out, cert)
	}
	return out, rows.Err()
}

// currentValidClusterAgentCertificate returns both the id and PEM of the
// agent's current, unrevoked, unexpired certificate -- rotation needs the
// id (to record rotated_from_certificate_id and to revoke it), everything
// else needs only the PEM.
func currentValidClusterAgentCertificate(ctx context.Context, c conn, operatorID, agentID uuid.UUID) (id uuid.UUID, certPEM string, ok bool, err error) {
	err = c.QueryRow(ctx, `
		SELECT id, certificate_pem FROM cluster_agent_certificates
		WHERE operator_id = $1 AND cluster_agent_id = $2
		  AND revoked_at IS NULL AND expires_at > now()
		ORDER BY issued_at DESC LIMIT 1
	`, operatorID, agentID).Scan(&id, &certPEM)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, "", false, nil
		}
		return uuid.Nil, "", false, fmt.Errorf("load current cluster agent certificate: %w", err)
	}
	return id, certPEM, true, nil
}

func revokeClusterAgentCertificate(ctx context.Context, c conn, certID uuid.UUID, reason string) error {
	_, err := c.Exec(ctx, `
		UPDATE cluster_agent_certificates SET revoked_at = now(), revoked_reason = $2 WHERE id = $1 AND revoked_at IS NULL
	`, certID, reason)
	if err != nil {
		return fmt.Errorf("revoke cluster agent certificate: %w", err)
	}
	return nil
}

func revokeAllClusterAgentCertificates(ctx context.Context, c conn, operatorID, agentID uuid.UUID, reason string) error {
	_, err := c.Exec(ctx, `
		UPDATE cluster_agent_certificates SET revoked_at = now(), revoked_reason = $3
		WHERE operator_id = $1 AND cluster_agent_id = $2 AND revoked_at IS NULL
	`, operatorID, agentID, reason)
	if err != nil {
		return fmt.Errorf("revoke cluster agent certificates: %w", err)
	}
	return nil
}

// ---------------------------------------------------------------------
// Operator agent certificate rotation (extends Milestone 2's existing
// operator_agents/agent_certificates -- rotation is a capability of the
// agent model generally, not just cluster agents).
// ---------------------------------------------------------------------

func currentValidOperatorAgentCertificate(ctx context.Context, c conn, operatorID, agentID uuid.UUID) (id uuid.UUID, certPEM string, ok bool, err error) {
	err = c.QueryRow(ctx, `
		SELECT id, certificate_pem FROM agent_certificates
		WHERE operator_id = $1 AND operator_agent_id = $2
		  AND revoked_at IS NULL AND expires_at > now()
		ORDER BY issued_at DESC LIMIT 1
	`, operatorID, agentID).Scan(&id, &certPEM)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, "", false, nil
		}
		return uuid.Nil, "", false, fmt.Errorf("load current operator agent certificate: %w", err)
	}
	return id, certPEM, true, nil
}

func createRotatedOperatorAgentCertificate(ctx context.Context, c conn, operatorID, agentID uuid.UUID, serialNumber, certPEM string, expiresAt time.Time, rotatedFrom uuid.UUID) (AgentCertificate, error) {
	var cert AgentCertificate
	err := c.QueryRow(ctx, `
		INSERT INTO agent_certificates (operator_id, operator_agent_id, serial_number, certificate_pem, expires_at, rotated_from_certificate_id)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, operator_id, operator_agent_id, serial_number, issued_at, expires_at, revoked_at, revoked_reason
	`, operatorID, agentID, serialNumber, certPEM, expiresAt, rotatedFrom).Scan(
		&cert.ID, &cert.OperatorID, &cert.OperatorAgentID, &cert.SerialNumber, &cert.IssuedAt, &cert.ExpiresAt, &cert.RevokedAt, &cert.RevokedReason)
	if err != nil {
		return AgentCertificate{}, fmt.Errorf("insert rotated operator agent certificate: %w", err)
	}
	return cert, nil
}

func revokeOperatorAgentCertificate(ctx context.Context, c conn, certID uuid.UUID, reason string) error {
	_, err := c.Exec(ctx, `
		UPDATE agent_certificates SET revoked_at = now(), revoked_reason = $2 WHERE id = $1 AND revoked_at IS NULL
	`, certID, reason)
	if err != nil {
		return fmt.Errorf("revoke operator agent certificate: %w", err)
	}
	return nil
}

// ---------------------------------------------------------------------
// Control messages (signed, replay-protected)
// ---------------------------------------------------------------------

const controlMessageColumns = `id, operator_id, cluster_agent_id, direction, message_type, in_response_to,
	nonce, payload, signature, signed_at, status, received_at`

func scanControlMessage(row pgx.Row) (ControlMessage, error) {
	var m ControlMessage
	var rawPayload string
	err := row.Scan(&m.ID, &m.OperatorID, &m.ClusterAgentID, &m.Direction, &m.MessageType, &m.InResponseTo,
		&m.Nonce, &rawPayload, &m.Signature, &m.SignedAt, &m.Status, &m.ReceivedAt)
	if err != nil {
		return ControlMessage{}, err
	}
	// Assigned directly, not unmarshaled-then-remarshaled: rawPayload is
	// already the exact bytes Signature was computed over (see model.go's
	// doc comment on ControlMessage.Payload), and json.RawMessage embeds
	// them as-is when this struct is itself marshaled for an API response.
	m.Payload = json.RawMessage(rawPayload)
	return m, nil
}

// createControlMessage stores payload exactly as given -- callers pass the
// literal bytes that were (or will be) signed, never a re-marshaled
// reconstruction of them, so a later read returns byte-identical content
// for signature verification.
func createControlMessage(ctx context.Context, c conn, operatorID, agentID uuid.UUID, direction, messageType string, inResponseTo *uuid.UUID, nonce string, payload []byte, signature string, signedAt time.Time, status string) (ControlMessage, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO control_messages (operator_id, cluster_agent_id, direction, message_type, in_response_to, nonce, payload, signature, signed_at, status)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		RETURNING `+controlMessageColumns, operatorID, agentID, direction, messageType, inResponseTo, nonce, string(payload), signature, signedAt, status)
	return scanControlMessage(row)
}

func listPendingControlMessages(ctx context.Context, c conn, agentID uuid.UUID) ([]ControlMessage, error) {
	rows, err := c.Query(ctx, `
		SELECT `+controlMessageColumns+` FROM control_messages
		WHERE cluster_agent_id = $1 AND direction = 'to_agent' AND status = 'pending'
		ORDER BY received_at
	`, agentID)
	if err != nil {
		return nil, fmt.Errorf("list pending control messages: %w", err)
	}
	defer rows.Close()

	var out []ControlMessage
	for rows.Next() {
		m, err := scanControlMessage(rows)
		if err != nil {
			return nil, fmt.Errorf("scan control message: %w", err)
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

func listControlMessages(ctx context.Context, c conn, operatorID, agentID uuid.UUID) ([]ControlMessage, error) {
	rows, err := c.Query(ctx, `
		SELECT `+controlMessageColumns+` FROM control_messages
		WHERE operator_id = $1 AND cluster_agent_id = $2 ORDER BY received_at DESC LIMIT 200
	`, operatorID, agentID)
	if err != nil {
		return nil, fmt.Errorf("list control messages: %w", err)
	}
	defer rows.Close()

	var out []ControlMessage
	for rows.Next() {
		m, err := scanControlMessage(rows)
		if err != nil {
			return nil, fmt.Errorf("scan control message: %w", err)
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

func getControlMessageByID(ctx context.Context, c conn, agentID, id uuid.UUID) (ControlMessage, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+controlMessageColumns+` FROM control_messages WHERE id = $1 AND cluster_agent_id = $2`, id, agentID)
	m, err := scanControlMessage(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return ControlMessage{}, false, nil
		}
		return ControlMessage{}, false, fmt.Errorf("get control message: %w", err)
	}
	return m, true, nil
}

// controlMessageNonceExists checks (cluster_agent_id, nonce) uniqueness
// explicitly before inserting, rather than inserting and mapping a
// Postgres unique-violation error afterward -- consistent with how every
// other check-then-write path in this codebase is structured.
func controlMessageNonceExists(ctx context.Context, c conn, agentID uuid.UUID, nonce string) (bool, error) {
	var exists bool
	err := c.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM control_messages WHERE cluster_agent_id = $1 AND nonce = $2)`, agentID, nonce).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("check control message nonce: %w", err)
	}
	return exists, nil
}

func markControlMessageResponded(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `UPDATE control_messages SET status = 'responded' WHERE id = $1 AND status = 'pending'`, id)
	if err != nil {
		return false, fmt.Errorf("mark control message responded: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

// ---------------------------------------------------------------------
// Deployment plan validations
// ---------------------------------------------------------------------

func createDeploymentPlanValidation(ctx context.Context, c conn, operatorID, agentID, controlMessageID uuid.UUID, planID string, workloadVersionID, capacityReservationID *uuid.UUID, signatureValid bool, decision string, reasonCodes []string, decidedAt time.Time) (DeploymentPlanValidation, error) {
	reasonCodesJSON, err := json.Marshal(reasonCodes)
	if err != nil {
		return DeploymentPlanValidation{}, fmt.Errorf("marshal reason codes: %w", err)
	}
	var v DeploymentPlanValidation
	var rawReasonCodes []byte
	err = c.QueryRow(ctx, `
		INSERT INTO deployment_plan_validations (
			operator_id, cluster_agent_id, control_message_id, plan_id, workload_version_id,
			capacity_reservation_id, signature_valid, policy_decision, reason_codes, decided_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		RETURNING id, operator_id, cluster_agent_id, control_message_id, plan_id, workload_version_id,
			capacity_reservation_id, signature_valid, policy_decision, reason_codes, decided_at, created_at
	`, operatorID, agentID, controlMessageID, planID, workloadVersionID, capacityReservationID, signatureValid, decision, reasonCodesJSON, decidedAt).Scan(
		&v.ID, &v.OperatorID, &v.ClusterAgentID, &v.ControlMessageID, &v.PlanID, &v.WorkloadVersionID,
		&v.CapacityReservationID, &v.SignatureValid, &v.PolicyDecision, &rawReasonCodes, &v.DecidedAt, &v.CreatedAt)
	if err != nil {
		return DeploymentPlanValidation{}, fmt.Errorf("insert deployment plan validation: %w", err)
	}
	if err := json.Unmarshal(rawReasonCodes, &v.ReasonCodes); err != nil {
		return DeploymentPlanValidation{}, fmt.Errorf("unmarshal reason codes: %w", err)
	}
	return v, nil
}

func listDeploymentPlanValidations(ctx context.Context, c conn, operatorID, agentID uuid.UUID) ([]DeploymentPlanValidation, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, cluster_agent_id, control_message_id, plan_id, workload_version_id,
			capacity_reservation_id, signature_valid, policy_decision, reason_codes, decided_at, created_at
		FROM deployment_plan_validations WHERE operator_id = $1 AND cluster_agent_id = $2 ORDER BY decided_at DESC
	`, operatorID, agentID)
	if err != nil {
		return nil, fmt.Errorf("list deployment plan validations: %w", err)
	}
	defer rows.Close()

	var out []DeploymentPlanValidation
	for rows.Next() {
		var v DeploymentPlanValidation
		var rawReasonCodes []byte
		if err := rows.Scan(&v.ID, &v.OperatorID, &v.ClusterAgentID, &v.ControlMessageID, &v.PlanID, &v.WorkloadVersionID,
			&v.CapacityReservationID, &v.SignatureValid, &v.PolicyDecision, &rawReasonCodes, &v.DecidedAt, &v.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan deployment plan validation: %w", err)
		}
		if err := json.Unmarshal(rawReasonCodes, &v.ReasonCodes); err != nil {
			return nil, fmt.Errorf("unmarshal reason codes: %w", err)
		}
		out = append(out, v)
	}
	return out, rows.Err()
}

// capacityReservationOperatorID resolves a capacity reservation's owning
// operator so a deployment-plan-validation request can be rejected if an
// operator references a reservation that is not actually against its own
// capacity (cross-referencing Milestone 5's capacity_reservations table
// read-only; this module never writes to it).
func capacityReservationOperatorID(ctx context.Context, c conn, reservationID uuid.UUID) (uuid.UUID, bool, error) {
	var operatorID uuid.UUID
	err := c.QueryRow(ctx, `SELECT operator_id FROM capacity_reservations WHERE id = $1`, reservationID).Scan(&operatorID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, false, nil
		}
		return uuid.Nil, false, fmt.Errorf("resolve capacity reservation operator: %w", err)
	}
	return operatorID, true, nil
}
