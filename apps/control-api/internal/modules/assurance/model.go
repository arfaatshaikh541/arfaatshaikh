// Package assurance implements Milestone 10's Service Assurance and
// Observability scope. The approved architecture's "Correlate: workload
// health, cluster/node/GPU health, model availability, network latency,
// policy compliance, attestation, capacity, operator incidents" requirement
// is deliberately NOT built as a new table duplicating data this codebase
// already produces -- deployment_events (Milestone 7), network_health_events
// (Milestone 9), attestation_results (Milestone 8), and
// policy_evaluation_records (Milestone 3/5) already are that data. This
// package's CorrelatedHealth read joins across those existing tables at
// query time; SLO/alert-rule evaluation reuses the same joins to compute
// their metrics, so "correlation" and "SLO/alert measurement" are the same
// underlying queries serving two different callers.
//
// What genuinely does not exist anywhere else, and this package owns: SLOs
// (a target either an operator commits to for its own infrastructure or an
// enterprise sets for its own workload/deployment -- evaluated on demand,
// there is no live scheduler in this codebase, the same "reclaimExpired
// runs at the top of every call" precedent Milestone 5 established),
// Incidents (a human-tracked record, dual-scope like
// deployments/network_reservations since an operator-infra incident can
// visibly affect a specific tenant), and Alerts (a rule an operator or
// enterprise defines against the same correlated signals, evaluated on
// demand and fired/resolved idempotently).
package assurance

import (
	"time"

	"github.com/google/uuid"
)

// ---------------------------------------------------------------------
// SLOs
// ---------------------------------------------------------------------

type SLODefinition struct {
	ID                 uuid.UUID  `json:"id"`
	OperatorID         *uuid.UUID `json:"operator_id,omitempty"`
	EnterpriseTenantID *uuid.UUID `json:"enterprise_tenant_id,omitempty"`
	Name               string     `json:"name"`
	MetricSource       string     `json:"metric_source"`
	ResourceType       *string    `json:"resource_type,omitempty"`
	ResourceID         *uuid.UUID `json:"resource_id,omitempty"`
	TargetPercentage   float64    `json:"target_percentage"`
	WindowDays         int        `json:"window_days"`
	Status             string     `json:"status"`
	CreatedBy          uuid.UUID  `json:"created_by"`
	CreatedAt          time.Time  `json:"created_at"`
	UpdatedAt          time.Time  `json:"updated_at"`
}

type CreateSLOInput struct {
	Name             string
	MetricSource     string
	ResourceType     *string
	ResourceID       *uuid.UUID
	TargetPercentage float64
	WindowDays       int
}

type SLOEvaluation struct {
	ID                             uuid.UUID      `json:"id"`
	SLODefinitionID                uuid.UUID      `json:"slo_definition_id"`
	EvaluatedAt                    time.Time      `json:"evaluated_at"`
	ActualPercentage               float64        `json:"actual_percentage"`
	ErrorBudgetRemainingPercentage float64        `json:"error_budget_remaining_percentage"`
	Status                         string         `json:"status"`
	SampleSize                     int            `json:"sample_size"`
	Detail                         map[string]any `json:"detail"`
}

// ---------------------------------------------------------------------
// Incidents
// ---------------------------------------------------------------------

type Incident struct {
	ID                 uuid.UUID  `json:"id"`
	OperatorID         *uuid.UUID `json:"operator_id,omitempty"`
	EnterpriseTenantID *uuid.UUID `json:"enterprise_tenant_id,omitempty"`
	Title              string     `json:"title"`
	Description        string     `json:"description"`
	Severity           string     `json:"severity"`
	Status             string     `json:"status"`
	ResourceType       *string    `json:"resource_type,omitempty"`
	ResourceID         *uuid.UUID `json:"resource_id,omitempty"`
	OpenedBy           uuid.UUID  `json:"opened_by"`
	AcknowledgedBy     *uuid.UUID `json:"acknowledged_by,omitempty"`
	AcknowledgedAt     *time.Time `json:"acknowledged_at,omitempty"`
	ResolvedBy         *uuid.UUID `json:"resolved_by,omitempty"`
	ResolvedAt         *time.Time `json:"resolved_at,omitempty"`
	OpenedAt           time.Time  `json:"opened_at"`
	UpdatedAt          time.Time  `json:"updated_at"`
}

type CreateIncidentInput struct {
	Title        string
	Description  string
	Severity     string
	ResourceType *string
	ResourceID   *uuid.UUID
}

type IncidentEvent struct {
	ID         uuid.UUID      `json:"id"`
	IncidentID uuid.UUID      `json:"incident_id"`
	EventType  string         `json:"event_type"`
	Detail     map[string]any `json:"detail"`
	CreatedBy  *uuid.UUID     `json:"created_by,omitempty"`
	CreatedAt  time.Time      `json:"created_at"`
}

// ---------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------

type AlertRule struct {
	ID                 uuid.UUID  `json:"id"`
	OperatorID         *uuid.UUID `json:"operator_id,omitempty"`
	EnterpriseTenantID *uuid.UUID `json:"enterprise_tenant_id,omitempty"`
	Name               string     `json:"name"`
	MetricSource       string     `json:"metric_source"`
	ResourceType       *string    `json:"resource_type,omitempty"`
	ResourceID         *uuid.UUID `json:"resource_id,omitempty"`
	Comparison         string     `json:"comparison"`
	Threshold          float64    `json:"threshold"`
	Severity           string     `json:"severity"`
	Status             string     `json:"status"`
	CreatedBy          uuid.UUID  `json:"created_by"`
	CreatedAt          time.Time  `json:"created_at"`
	UpdatedAt          time.Time  `json:"updated_at"`
}

type CreateAlertRuleInput struct {
	Name         string
	MetricSource string
	ResourceType *string
	ResourceID   *uuid.UUID
	Comparison   string
	Threshold    float64
	Severity     string
}

type Alert struct {
	ID          uuid.UUID      `json:"id"`
	AlertRuleID uuid.UUID      `json:"alert_rule_id"`
	Status      string         `json:"status"`
	ValueAtFire float64        `json:"value_at_fire"`
	Detail      map[string]any `json:"detail"`
	FiredAt     time.Time      `json:"fired_at"`
	ResolvedAt  *time.Time     `json:"resolved_at,omitempty"`
}

// ---------------------------------------------------------------------
// Correlated health and audit correlation (read-only, no backing table --
// see package doc)
// ---------------------------------------------------------------------

// CorrelatedHealth is one scope's (a tenant's or an operator's) point-in-time
// snapshot across every signal this codebase already records -- the
// "Correlate: workload/cluster/GPU/network/model health, policy compliance,
// attestation, incidents" requirement, computed at query time.
type CorrelatedHealth struct {
	DeploymentAvailabilityPercentage float64 `json:"deployment_availability_percentage"`
	DeploymentSampleSize             int     `json:"deployment_sample_size"`
	NetworkProvisioningPercentage    float64 `json:"network_provisioning_percentage"`
	NetworkSampleSize                int     `json:"network_sample_size"`
	AttestationSuccessPercentage     float64 `json:"attestation_success_percentage"`
	AttestationSampleSize            int     `json:"attestation_sample_size"`
	PolicyComplianceRatePercentage   float64 `json:"policy_compliance_rate_percentage"`
	PolicySampleSize                 int     `json:"policy_sample_size"`
	OpenIncidentCount                int     `json:"open_incident_count"`
	FiringAlertCount                 int     `json:"firing_alert_count"`
}
