package operators

import (
	"time"

	"github.com/google/uuid"
)

type Operator struct {
	ID                  uuid.UUID `json:"id"`
	LegalName           string    `json:"legal_name"`
	DisplayName         string    `json:"display_name"`
	Country             string    `json:"country"`
	Status              string    `json:"status"`
	TrustLevel          string    `json:"trust_level"`
	IsFictionalDemoData bool      `json:"is_fictional_demo_data"`
	CreatedAt           time.Time `json:"created_at"`
}

type Membership struct {
	ID         uuid.UUID `json:"id"`
	UserID     uuid.UUID `json:"user_id"`
	OperatorID uuid.UUID `json:"operator_id"`
	RoleKey    string    `json:"role_key"`
	RoleName   string    `json:"role_name"`
	Status     string    `json:"status"`
	CreatedAt  time.Time `json:"created_at"`
}
