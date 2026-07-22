package platformadmin

import (
	"time"

	"github.com/google/uuid"
)

type SupportAccessGrant struct {
	ID          uuid.UUID  `json:"id"`
	UserID      uuid.UUID  `json:"user_id"`
	ScopeType   string     `json:"scope_type"`
	ScopeID     uuid.UUID  `json:"scope_id"`
	Reason      string     `json:"reason"`
	RequestedBy uuid.UUID  `json:"requested_by"`
	ApprovedBy  *uuid.UUID `json:"approved_by,omitempty"`
	ApprovedAt  *time.Time `json:"approved_at,omitempty"`
	RevokedAt   *time.Time `json:"revoked_at,omitempty"`
	ExpiresAt   time.Time  `json:"expires_at"`
	CreatedAt   time.Time  `json:"created_at"`
}
