package subscriptions

import "github.com/google/uuid"

type Plan struct {
	ID        uuid.UUID
	Key       string
	Name      string
	ScopeType string
}

type Entitlements struct {
	PlanKey  string         `json:"plan_key"`
	PlanName string         `json:"plan_name"`
	Status   string         `json:"status"`
	Features map[string]any `json:"features"`
}
