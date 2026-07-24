package tenancy

import (
	"time"

	"github.com/google/uuid"
)

// SustainabilityRankingMode/MaxCarbonIntensityGPerKWh are Milestone 14's
// energy/carbon preferences: the ranking mode is a single tenant-configurable
// knob covering both "energy preferences" and "cost and energy trade-offs"
// (internal/modules/placement.EvaluatePlacement's ranking comparator reads
// it), while the carbon ceiling is a hard constraint, not just a ranking
// nudge -- an offer whose region exceeds it is excluded from eligibility
// entirely, never merely ranked lower.
type EnterpriseTenant struct {
	ID                        uuid.UUID `json:"id"`
	LegalName                 string    `json:"legal_name"`
	DisplayName               string    `json:"display_name"`
	Country                   string    `json:"country"`
	Status                    string    `json:"status"`
	IsFictionalDemoData       bool      `json:"is_fictional_demo_data"`
	SustainabilityRankingMode string    `json:"sustainability_ranking_mode"`
	MaxCarbonIntensityGPerKWh *float64  `json:"max_carbon_intensity_g_per_kwh,omitempty"`
	CreatedAt                 time.Time `json:"created_at"`
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
