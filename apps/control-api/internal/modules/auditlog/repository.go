package auditlog

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

type queryable interface {
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

func listEvents(ctx context.Context, c queryable, scopeType string, scopeID uuid.UUID, limit int) ([]Event, error) {
	rows, err := c.Query(ctx, `
		SELECT seq, id, occurred_at, actor_user_id, scope_type, scope_id, action, target_type, target_id, evidence, prev_hash, hash
		FROM audit_events
		WHERE scope_type = $1 AND scope_id = $2
		ORDER BY seq DESC
		LIMIT $3
	`, scopeType, scopeID, limit)
	if err != nil {
		return nil, fmt.Errorf("list audit events: %w", err)
	}
	defer rows.Close()
	return scanEvents(rows)
}

func listPlatformEvents(ctx context.Context, c queryable, limit int) ([]Event, error) {
	rows, err := c.Query(ctx, `
		SELECT seq, id, occurred_at, actor_user_id, scope_type, scope_id, action, target_type, target_id, evidence, prev_hash, hash
		FROM audit_events
		WHERE scope_type = 'platform'
		ORDER BY seq DESC
		LIMIT $1
	`, limit)
	if err != nil {
		return nil, fmt.Errorf("list platform audit events: %w", err)
	}
	defer rows.Close()
	return scanEvents(rows)
}

func scanEvents(rows pgx.Rows) ([]Event, error) {
	var out []Event
	for rows.Next() {
		var e Event
		var rawEvidence []byte
		var targetType *string
		if err := rows.Scan(&e.Seq, &e.ID, &e.OccurredAt, &e.ActorUserID, &e.ScopeType, &e.ScopeID, &e.Action, &targetType, &e.TargetID, &rawEvidence, &e.PrevHash, &e.Hash); err != nil {
			return nil, fmt.Errorf("scan audit event: %w", err)
		}
		if targetType != nil {
			e.TargetType = *targetType
		}
		if len(rawEvidence) > 0 {
			_ = json.Unmarshal(rawEvidence, &e.Evidence)
		}
		out = append(out, e)
	}
	return out, rows.Err()
}
