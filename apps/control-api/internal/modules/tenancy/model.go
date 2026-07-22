package tenancy

import (
	"time"

	"github.com/google/uuid"
)

type EnterpriseTenant struct {
	ID                  uuid.UUID `json:"id"`
	LegalName           string    `json:"legal_name"`
	DisplayName         string    `json:"display_name"`
	Country             string    `json:"country"`
	Status              string    `json:"status"`
	IsFictionalDemoData bool      `json:"is_fictional_demo_data"`
	CreatedAt           time.Time `json:"created_at"`
}

type Membership struct {
	ID        uuid.UUID `json:"id"`
	UserID    uuid.UUID `json:"user_id"`
	TenantID  uuid.UUID `json:"enterprise_tenant_id"`
	RoleKey   string    `json:"role_key"`
	RoleName  string    `json:"role_name"`
	Status    string    `json:"status"`
	CreatedAt time.Time `json:"created_at"`
}

type Invitation struct {
	ID        uuid.UUID `json:"id"`
	TenantID  uuid.UUID `json:"enterprise_tenant_id"`
	Email     string    `json:"email"`
	RoleKey   string    `json:"role_key"`
	Status    string    `json:"status"`
	ExpiresAt time.Time `json:"expires_at"`
	CreatedAt time.Time `json:"created_at"`
}
