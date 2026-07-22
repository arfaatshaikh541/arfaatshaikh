// Package audit provides the append-only, hash-chained audit log writer
// used by every module. Every state-changing action in the system must call
// Record within the same database transaction as the change it describes,
// so the audit entry and the change it documents commit or roll back
// together atomically.
package audit

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

type ScopeType string

const (
	ScopeEnterprise ScopeType = "enterprise"
	ScopeOperator   ScopeType = "operator"
	ScopePlatform   ScopeType = "platform"
)

type Event struct {
	ActorUserID *uuid.UUID
	ScopeType   ScopeType
	ScopeID     *uuid.UUID
	Action      string
	TargetType  string
	TargetID    *uuid.UUID
	Evidence    map[string]any
}

// Record appends a tamper-evident audit entry inside tx. The previous row's
// hash is read with a row lock (FOR UPDATE) to serialize concurrent writers
// and guarantee a single, unbroken chain: hash = sha256(prevHash || canonical(event)).
func Record(ctx context.Context, tx pgx.Tx, ev Event) error {
	var prevHash string
	err := tx.QueryRow(ctx, `
		SELECT hash FROM audit_events ORDER BY seq DESC LIMIT 1 FOR UPDATE
	`).Scan(&prevHash)
	if err != nil {
		if err != pgx.ErrNoRows {
			return fmt.Errorf("lock last audit row: %w", err)
		}
		prevHash = "genesis"
	}

	evidenceJSON, err := json.Marshal(ev.Evidence)
	if err != nil {
		return fmt.Errorf("marshal audit evidence: %w", err)
	}

	id := uuid.New()
	canonical := fmt.Sprintf("%s|%v|%s|%v|%s|%s|%v|%s",
		id, ev.ActorUserID, ev.ScopeType, ev.ScopeID, ev.Action, ev.TargetType, ev.TargetID, evidenceJSON)
	sum := sha256.Sum256([]byte(prevHash + "|" + canonical))
	hash := hex.EncodeToString(sum[:])

	_, err = tx.Exec(ctx, `
		INSERT INTO audit_events
			(id, actor_user_id, scope_type, scope_id, action, target_type, target_id, evidence, prev_hash, hash)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
	`, id, ev.ActorUserID, string(ev.ScopeType), ev.ScopeID, ev.Action, ev.TargetType, ev.TargetID, evidenceJSON, prevHash, hash)
	if err != nil {
		return fmt.Errorf("insert audit event: %w", err)
	}

	return nil
}
