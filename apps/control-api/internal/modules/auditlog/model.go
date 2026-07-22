package auditlog

import (
	"time"

	"github.com/google/uuid"
)

type Event struct {
	Seq         int64          `json:"seq"`
	ID          uuid.UUID      `json:"id"`
	OccurredAt  time.Time      `json:"occurred_at"`
	ActorUserID *uuid.UUID     `json:"actor_user_id,omitempty"`
	ScopeType   string         `json:"scope_type"`
	ScopeID     *uuid.UUID     `json:"scope_id,omitempty"`
	Action      string         `json:"action"`
	TargetType  string         `json:"target_type,omitempty"`
	TargetID    *uuid.UUID     `json:"target_id,omitempty"`
	Evidence    map[string]any `json:"evidence"`
	Hash        string         `json:"hash"`
	PrevHash    string         `json:"prev_hash"`
}
