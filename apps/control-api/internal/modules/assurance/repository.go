package assurance

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

// conn is satisfied by both *pgxpool.Pool and pgx.Tx, matching every other
// module's repository layer in this codebase.
type conn interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

// ---------------------------------------------------------------------
// SLO definitions
// ---------------------------------------------------------------------

const sloColumns = `id, operator_id, enterprise_tenant_id, name, metric_source, resource_type, resource_id,
	target_percentage, window_days, status, created_by, created_at, updated_at`

func scanSLO(row pgx.Row) (SLODefinition, error) {
	var s SLODefinition
	err := row.Scan(&s.ID, &s.OperatorID, &s.EnterpriseTenantID, &s.Name, &s.MetricSource, &s.ResourceType, &s.ResourceID,
		&s.TargetPercentage, &s.WindowDays, &s.Status, &s.CreatedBy, &s.CreatedAt, &s.UpdatedAt)
	return s, err
}

func createSLO(ctx context.Context, c conn, operatorID, tenantID *uuid.UUID, createdBy uuid.UUID, in CreateSLOInput) (SLODefinition, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO slo_definitions (operator_id, enterprise_tenant_id, name, metric_source, resource_type, resource_id, target_percentage, window_days, created_by)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		RETURNING `+sloColumns, operatorID, tenantID, in.Name, in.MetricSource, in.ResourceType, in.ResourceID, in.TargetPercentage, in.WindowDays, createdBy)
	s, err := scanSLO(row)
	if err != nil {
		return SLODefinition{}, fmt.Errorf("insert slo definition: %w", err)
	}
	return s, nil
}

func listSLOsForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]SLODefinition, error) {
	rows, err := c.Query(ctx, `SELECT `+sloColumns+` FROM slo_definitions WHERE operator_id = $1 ORDER BY created_at DESC`, operatorID)
	return scanSLOs(rows, err)
}

func listSLOsForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]SLODefinition, error) {
	rows, err := c.Query(ctx, `SELECT `+sloColumns+` FROM slo_definitions WHERE enterprise_tenant_id = $1 ORDER BY created_at DESC`, tenantID)
	return scanSLOs(rows, err)
}

func scanSLOs(rows pgx.Rows, err error) ([]SLODefinition, error) {
	if err != nil {
		return nil, fmt.Errorf("list slo definitions: %w", err)
	}
	defer rows.Close()
	out := []SLODefinition{}
	for rows.Next() {
		s, err := scanSLO(rows)
		if err != nil {
			return nil, fmt.Errorf("scan slo definition: %w", err)
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

func getSLOByIDOperator(ctx context.Context, c conn, operatorID, id uuid.UUID) (SLODefinition, bool, error) {
	return getSLOByIDScope(ctx, c, "operator_id", operatorID, id)
}

func getSLOByIDTenant(ctx context.Context, c conn, tenantID, id uuid.UUID) (SLODefinition, bool, error) {
	return getSLOByIDScope(ctx, c, "enterprise_tenant_id", tenantID, id)
}

func getSLOByIDScope(ctx context.Context, c conn, scopeCol string, scopeID, id uuid.UUID) (SLODefinition, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+sloColumns+` FROM slo_definitions WHERE id = $1 AND `+scopeCol+` = $2`, id, scopeID)
	s, err := scanSLO(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return SLODefinition{}, false, nil
		}
		return SLODefinition{}, false, fmt.Errorf("get slo definition: %w", err)
	}
	return s, true, nil
}

func archiveSLO(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `UPDATE slo_definitions SET status = 'archived', updated_at = now() WHERE id = $1 AND status = 'active'`, id)
	if err != nil {
		return false, fmt.Errorf("archive slo definition: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func insertSLOEvaluation(ctx context.Context, c conn, sloID uuid.UUID, operatorID, tenantID *uuid.UUID, actualPercentage, targetPercentage float64, sampleSize int, detail map[string]any) (SLOEvaluation, error) {
	status := "ok"
	errorBudgetRemaining := actualPercentage - (100 - targetPercentage)
	if actualPercentage < targetPercentage {
		status = "breached"
	} else if errorBudgetRemaining < (100-targetPercentage)*0.2 {
		// Less than 20% of the allowed error budget remains -- "at risk"
		// without having actually breached the target yet.
		status = "at_risk"
	}
	detailJSON, err := json.Marshal(detail)
	if err != nil {
		return SLOEvaluation{}, fmt.Errorf("encode slo evaluation detail: %w", err)
	}
	var e SLOEvaluation
	var detailRaw []byte
	row := c.QueryRow(ctx, `
		INSERT INTO slo_evaluations (slo_definition_id, operator_id, enterprise_tenant_id, actual_percentage, error_budget_remaining_percentage, status, sample_size, detail)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		RETURNING id, slo_definition_id, evaluated_at, actual_percentage, error_budget_remaining_percentage, status, sample_size, detail
	`, sloID, operatorID, tenantID, actualPercentage, errorBudgetRemaining, status, sampleSize, detailJSON)
	if err := row.Scan(&e.ID, &e.SLODefinitionID, &e.EvaluatedAt, &e.ActualPercentage, &e.ErrorBudgetRemainingPercentage, &e.Status, &e.SampleSize, &detailRaw); err != nil {
		return SLOEvaluation{}, fmt.Errorf("insert slo evaluation: %w", err)
	}
	if err := json.Unmarshal(detailRaw, &e.Detail); err != nil {
		return SLOEvaluation{}, fmt.Errorf("decode slo evaluation detail: %w", err)
	}
	return e, nil
}

func listSLOEvaluations(ctx context.Context, c conn, sloID uuid.UUID) ([]SLOEvaluation, error) {
	rows, err := c.Query(ctx, `
		SELECT id, slo_definition_id, evaluated_at, actual_percentage, error_budget_remaining_percentage, status, sample_size, detail
		FROM slo_evaluations WHERE slo_definition_id = $1 ORDER BY evaluated_at DESC LIMIT 100
	`, sloID)
	if err != nil {
		return nil, fmt.Errorf("list slo evaluations: %w", err)
	}
	defer rows.Close()
	out := []SLOEvaluation{}
	for rows.Next() {
		var e SLOEvaluation
		var detailRaw []byte
		if err := rows.Scan(&e.ID, &e.SLODefinitionID, &e.EvaluatedAt, &e.ActualPercentage, &e.ErrorBudgetRemainingPercentage, &e.Status, &e.SampleSize, &detailRaw); err != nil {
			return nil, fmt.Errorf("scan slo evaluation: %w", err)
		}
		if err := json.Unmarshal(detailRaw, &e.Detail); err != nil {
			return nil, fmt.Errorf("decode slo evaluation detail: %w", err)
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Incidents
// ---------------------------------------------------------------------

const incidentColumns = `id, operator_id, enterprise_tenant_id, title, description, severity, status, resource_type, resource_id,
	opened_by, acknowledged_by, acknowledged_at, resolved_by, resolved_at, opened_at, updated_at`

func scanIncident(row pgx.Row) (Incident, error) {
	var i Incident
	err := row.Scan(&i.ID, &i.OperatorID, &i.EnterpriseTenantID, &i.Title, &i.Description, &i.Severity, &i.Status,
		&i.ResourceType, &i.ResourceID, &i.OpenedBy, &i.AcknowledgedBy, &i.AcknowledgedAt, &i.ResolvedBy, &i.ResolvedAt,
		&i.OpenedAt, &i.UpdatedAt)
	return i, err
}

func createIncident(ctx context.Context, c conn, operatorID, tenantID *uuid.UUID, openedBy uuid.UUID, in CreateIncidentInput) (Incident, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO incidents (operator_id, enterprise_tenant_id, title, description, severity, resource_type, resource_id, opened_by)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		RETURNING `+incidentColumns, operatorID, tenantID, in.Title, in.Description, in.Severity, in.ResourceType, in.ResourceID, openedBy)
	i, err := scanIncident(row)
	if err != nil {
		return Incident{}, fmt.Errorf("insert incident: %w", err)
	}
	return i, nil
}

func listIncidentsForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]Incident, error) {
	rows, err := c.Query(ctx, `SELECT `+incidentColumns+` FROM incidents WHERE operator_id = $1 ORDER BY opened_at DESC`, operatorID)
	return scanIncidents(rows, err)
}

func listIncidentsForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]Incident, error) {
	rows, err := c.Query(ctx, `SELECT `+incidentColumns+` FROM incidents WHERE enterprise_tenant_id = $1 ORDER BY opened_at DESC`, tenantID)
	return scanIncidents(rows, err)
}

func scanIncidents(rows pgx.Rows, err error) ([]Incident, error) {
	if err != nil {
		return nil, fmt.Errorf("list incidents: %w", err)
	}
	defer rows.Close()
	out := []Incident{}
	for rows.Next() {
		i, err := scanIncident(rows)
		if err != nil {
			return nil, fmt.Errorf("scan incident: %w", err)
		}
		out = append(out, i)
	}
	return out, rows.Err()
}

func getIncidentByIDOperator(ctx context.Context, c conn, operatorID, id uuid.UUID) (Incident, bool, error) {
	return getIncidentByIDScope(ctx, c, "operator_id", operatorID, id)
}

func getIncidentByIDTenant(ctx context.Context, c conn, tenantID, id uuid.UUID) (Incident, bool, error) {
	return getIncidentByIDScope(ctx, c, "enterprise_tenant_id", tenantID, id)
}

func getIncidentByIDScope(ctx context.Context, c conn, scopeCol string, scopeID, id uuid.UUID) (Incident, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+incidentColumns+` FROM incidents WHERE id = $1 AND `+scopeCol+` = $2`, id, scopeID)
	i, err := scanIncident(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Incident{}, false, nil
		}
		return Incident{}, false, fmt.Errorf("get incident: %w", err)
	}
	return i, true, nil
}

func acknowledgeIncident(ctx context.Context, c conn, id, actor uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE incidents SET status = 'acknowledged', acknowledged_by = $2, acknowledged_at = now(), updated_at = now()
		WHERE id = $1 AND status = 'open'
	`, id, actor)
	if err != nil {
		return false, fmt.Errorf("acknowledge incident: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func resolveIncident(ctx context.Context, c conn, id, actor uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE incidents SET status = 'resolved', resolved_by = $2, resolved_at = now(), updated_at = now()
		WHERE id = $1 AND status IN ('open', 'acknowledged')
	`, id, actor)
	if err != nil {
		return false, fmt.Errorf("resolve incident: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func insertIncidentEvent(ctx context.Context, c conn, incidentID uuid.UUID, operatorID, tenantID *uuid.UUID, eventType string, detail map[string]any, createdBy *uuid.UUID) (IncidentEvent, error) {
	detailJSON, err := json.Marshal(detail)
	if err != nil {
		return IncidentEvent{}, fmt.Errorf("encode incident event detail: %w", err)
	}
	var e IncidentEvent
	var detailRaw []byte
	row := c.QueryRow(ctx, `
		INSERT INTO incident_events (incident_id, operator_id, enterprise_tenant_id, event_type, detail, created_by)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, incident_id, event_type, detail, created_by, created_at
	`, incidentID, operatorID, tenantID, eventType, detailJSON, createdBy)
	if err := row.Scan(&e.ID, &e.IncidentID, &e.EventType, &detailRaw, &e.CreatedBy, &e.CreatedAt); err != nil {
		return IncidentEvent{}, fmt.Errorf("insert incident event: %w", err)
	}
	if err := json.Unmarshal(detailRaw, &e.Detail); err != nil {
		return IncidentEvent{}, fmt.Errorf("decode incident event detail: %w", err)
	}
	return e, nil
}

func listIncidentEvents(ctx context.Context, c conn, incidentID uuid.UUID) ([]IncidentEvent, error) {
	rows, err := c.Query(ctx, `
		SELECT id, incident_id, event_type, detail, created_by, created_at
		FROM incident_events WHERE incident_id = $1 ORDER BY created_at
	`, incidentID)
	if err != nil {
		return nil, fmt.Errorf("list incident events: %w", err)
	}
	defer rows.Close()
	out := []IncidentEvent{}
	for rows.Next() {
		var e IncidentEvent
		var detailRaw []byte
		if err := rows.Scan(&e.ID, &e.IncidentID, &e.EventType, &detailRaw, &e.CreatedBy, &e.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan incident event: %w", err)
		}
		if err := json.Unmarshal(detailRaw, &e.Detail); err != nil {
			return nil, fmt.Errorf("decode incident event detail: %w", err)
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Alert rules and alerts
// ---------------------------------------------------------------------

const alertRuleColumns = `id, operator_id, enterprise_tenant_id, name, metric_source, resource_type, resource_id,
	comparison, threshold, severity, status, created_by, created_at, updated_at`

func scanAlertRule(row pgx.Row) (AlertRule, error) {
	var r AlertRule
	err := row.Scan(&r.ID, &r.OperatorID, &r.EnterpriseTenantID, &r.Name, &r.MetricSource, &r.ResourceType, &r.ResourceID,
		&r.Comparison, &r.Threshold, &r.Severity, &r.Status, &r.CreatedBy, &r.CreatedAt, &r.UpdatedAt)
	return r, err
}

func createAlertRule(ctx context.Context, c conn, operatorID, tenantID *uuid.UUID, createdBy uuid.UUID, in CreateAlertRuleInput) (AlertRule, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO alert_rules (operator_id, enterprise_tenant_id, name, metric_source, resource_type, resource_id, comparison, threshold, severity, created_by)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		RETURNING `+alertRuleColumns, operatorID, tenantID, in.Name, in.MetricSource, in.ResourceType, in.ResourceID, in.Comparison, in.Threshold, in.Severity, createdBy)
	r, err := scanAlertRule(row)
	if err != nil {
		return AlertRule{}, fmt.Errorf("insert alert rule: %w", err)
	}
	return r, nil
}

func listAlertRulesForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]AlertRule, error) {
	rows, err := c.Query(ctx, `SELECT `+alertRuleColumns+` FROM alert_rules WHERE operator_id = $1 ORDER BY created_at DESC`, operatorID)
	return scanAlertRules(rows, err)
}

func listAlertRulesForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]AlertRule, error) {
	rows, err := c.Query(ctx, `SELECT `+alertRuleColumns+` FROM alert_rules WHERE enterprise_tenant_id = $1 ORDER BY created_at DESC`, tenantID)
	return scanAlertRules(rows, err)
}

func scanAlertRules(rows pgx.Rows, err error) ([]AlertRule, error) {
	if err != nil {
		return nil, fmt.Errorf("list alert rules: %w", err)
	}
	defer rows.Close()
	out := []AlertRule{}
	for rows.Next() {
		r, err := scanAlertRule(rows)
		if err != nil {
			return nil, fmt.Errorf("scan alert rule: %w", err)
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func getAlertRuleByIDOperator(ctx context.Context, c conn, operatorID, id uuid.UUID) (AlertRule, bool, error) {
	return getAlertRuleByIDScope(ctx, c, "operator_id", operatorID, id)
}

func getAlertRuleByIDTenant(ctx context.Context, c conn, tenantID, id uuid.UUID) (AlertRule, bool, error) {
	return getAlertRuleByIDScope(ctx, c, "enterprise_tenant_id", tenantID, id)
}

func getAlertRuleByIDScope(ctx context.Context, c conn, scopeCol string, scopeID, id uuid.UUID) (AlertRule, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+alertRuleColumns+` FROM alert_rules WHERE id = $1 AND `+scopeCol+` = $2`, id, scopeID)
	r, err := scanAlertRule(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return AlertRule{}, false, nil
		}
		return AlertRule{}, false, fmt.Errorf("get alert rule: %w", err)
	}
	return r, true, nil
}

func setAlertRuleStatus(ctx context.Context, c conn, id uuid.UUID, status string) (bool, error) {
	tag, err := c.Exec(ctx, `UPDATE alert_rules SET status = $2, updated_at = now() WHERE id = $1`, id, status)
	if err != nil {
		return false, fmt.Errorf("update alert rule status: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func scanAlert(row pgx.Row) (Alert, error) {
	var a Alert
	var detailRaw []byte
	err := row.Scan(&a.ID, &a.AlertRuleID, &a.Status, &a.ValueAtFire, &detailRaw, &a.FiredAt, &a.ResolvedAt)
	if err != nil {
		return Alert{}, err
	}
	if err := json.Unmarshal(detailRaw, &a.Detail); err != nil {
		return Alert{}, fmt.Errorf("decode alert detail: %w", err)
	}
	return a, nil
}

const alertColumns = `id, alert_rule_id, status, value_at_fire, detail, fired_at, resolved_at`

func getFiringAlertForRule(ctx context.Context, c conn, ruleID uuid.UUID) (Alert, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+alertColumns+` FROM alerts WHERE alert_rule_id = $1 AND status = 'firing' ORDER BY fired_at DESC LIMIT 1`, ruleID)
	a, err := scanAlert(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Alert{}, false, nil
		}
		return Alert{}, false, fmt.Errorf("get firing alert: %w", err)
	}
	return a, true, nil
}

func fireAlert(ctx context.Context, c conn, ruleID uuid.UUID, operatorID, tenantID *uuid.UUID, valueAtFire float64, detail map[string]any) (Alert, error) {
	detailJSON, err := json.Marshal(detail)
	if err != nil {
		return Alert{}, fmt.Errorf("encode alert detail: %w", err)
	}
	row := c.QueryRow(ctx, `
		INSERT INTO alerts (alert_rule_id, operator_id, enterprise_tenant_id, value_at_fire, detail)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING `+alertColumns, ruleID, operatorID, tenantID, valueAtFire, detailJSON)
	a, err := scanAlert(row)
	if err != nil {
		return Alert{}, fmt.Errorf("insert alert: %w", err)
	}
	return a, nil
}

func resolveAlert(ctx context.Context, c conn, id uuid.UUID) error {
	_, err := c.Exec(ctx, `UPDATE alerts SET status = 'resolved', resolved_at = now() WHERE id = $1`, id)
	if err != nil {
		return fmt.Errorf("resolve alert: %w", err)
	}
	return nil
}

func listAlertsForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]Alert, error) {
	rows, err := c.Query(ctx, `SELECT `+alertColumns+` FROM alerts WHERE operator_id = $1 ORDER BY fired_at DESC LIMIT 200`, operatorID)
	return scanAlerts(rows, err)
}

func listAlertsForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]Alert, error) {
	rows, err := c.Query(ctx, `SELECT `+alertColumns+` FROM alerts WHERE enterprise_tenant_id = $1 ORDER BY fired_at DESC LIMIT 200`, tenantID)
	return scanAlerts(rows, err)
}

func countFiringAlertsForOperator(ctx context.Context, c conn, operatorID uuid.UUID) (int, error) {
	var n int
	err := c.QueryRow(ctx, `SELECT count(*) FROM alerts WHERE operator_id = $1 AND status = 'firing'`, operatorID).Scan(&n)
	if err != nil {
		return 0, fmt.Errorf("count firing alerts: %w", err)
	}
	return n, nil
}

func countFiringAlertsForTenant(ctx context.Context, c conn, tenantID uuid.UUID) (int, error) {
	var n int
	err := c.QueryRow(ctx, `SELECT count(*) FROM alerts WHERE enterprise_tenant_id = $1 AND status = 'firing'`, tenantID).Scan(&n)
	if err != nil {
		return 0, fmt.Errorf("count firing alerts: %w", err)
	}
	return n, nil
}

func scanAlerts(rows pgx.Rows, err error) ([]Alert, error) {
	if err != nil {
		return nil, fmt.Errorf("list alerts: %w", err)
	}
	defer rows.Close()
	out := []Alert{}
	for rows.Next() {
		a, err := scanAlert(rows)
		if err != nil {
			return nil, fmt.Errorf("scan alert: %w", err)
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

func countOpenIncidentsForOperator(ctx context.Context, c conn, operatorID uuid.UUID) (int, error) {
	var n int
	err := c.QueryRow(ctx, `SELECT count(*) FROM incidents WHERE operator_id = $1 AND status != 'resolved'`, operatorID).Scan(&n)
	if err != nil {
		return 0, fmt.Errorf("count open incidents: %w", err)
	}
	return n, nil
}

func countOpenIncidentsForTenant(ctx context.Context, c conn, tenantID uuid.UUID) (int, error) {
	var n int
	err := c.QueryRow(ctx, `SELECT count(*) FROM incidents WHERE enterprise_tenant_id = $1 AND status != 'resolved'`, tenantID).Scan(&n)
	if err != nil {
		return 0, fmt.Errorf("count open incidents: %w", err)
	}
	return n, nil
}

// ---------------------------------------------------------------------
// Metric computation -- shared by SLO evaluation, alert evaluation, and
// correlated health. Each function reads one already-existing table this
// codebase populates for an entirely different reason (deployment
// execution, network provisioning, attestation, sovereignty policy), never
// writing anything -- "correlation" is a read, not a new fact.
//
// A metric with zero samples in the window returns 100.0 (nothing failed,
// because nothing happened) rather than an error or a punitive 0 -- an SLO
// or alert rule with no relevant activity yet should not immediately read
// as breached. This is a deliberate simplification, not a true
// time-weighted uptime calculation (which would require a live metrics
// store this codebase does not have); see docs/project-status.md's Known
// Limitations for Milestone 10.
// ---------------------------------------------------------------------

const defaultMetricPercentage = 100.0

func computeDeploymentAvailability(ctx context.Context, c conn, operatorID, tenantID *uuid.UUID, resourceID *uuid.UUID, windowStart time.Time) (float64, int, error) {
	query := `
		SELECT count(*) FILTER (WHERE (detail->>'success')::boolean = true), count(*)
		FROM deployment_events
		WHERE event_type LIKE 'command_result:%' AND created_at >= $1
	`
	args := []any{windowStart}
	query, args = appendOwnerFilter(query, args, "operator_id", "enterprise_tenant_id", operatorID, tenantID)
	if resourceID != nil {
		args = append(args, *resourceID)
		query += fmt.Sprintf(" AND deployment_id = $%d", len(args))
	}
	return scanRatio(ctx, c, query, args)
}

func computeNetworkProvisioning(ctx context.Context, c conn, operatorID, tenantID *uuid.UUID, resourceID *uuid.UUID, windowStart time.Time) (float64, int, error) {
	query := `
		SELECT count(*) FILTER (WHERE provisioning_status = 'provisioned'), count(*)
		FROM network_reservations
		WHERE committed_at >= $1
	`
	args := []any{windowStart}
	query, args = appendOwnerFilter(query, args, "operator_id", "enterprise_tenant_id", operatorID, tenantID)
	if resourceID != nil {
		args = append(args, *resourceID)
		query += fmt.Sprintf(" AND network_service_offer_id = $%d", len(args))
	}
	return scanRatio(ctx, c, query, args)
}

func computeAttestationSuccessRate(ctx context.Context, c conn, operatorID, tenantID *uuid.UUID, resourceID *uuid.UUID, windowStart time.Time) (float64, int, error) {
	query := `
		SELECT count(*) FILTER (WHERE decision = 'pass'), count(*)
		FROM attestation_results
		WHERE evaluated_at >= $1
	`
	args := []any{windowStart}
	query, args = appendOwnerFilter(query, args, "operator_id", "enterprise_tenant_id", operatorID, tenantID)
	if resourceID != nil {
		args = append(args, *resourceID)
		query += fmt.Sprintf(" AND deployment_id = $%d", len(args))
	}
	return scanRatio(ctx, c, query, args)
}

// computePolicyComplianceRate has no operator dimension --
// policy_evaluation_records is an enterprise-only concept (a tenant's own
// sovereignty policy evaluated against placement candidates); an
// operator-scoped SLO/alert against this metric source has nothing to
// measure and returns the neutral default.
func computePolicyComplianceRate(ctx context.Context, c conn, operatorID, tenantID *uuid.UUID, resourceID *uuid.UUID, windowStart time.Time) (float64, int, error) {
	if tenantID == nil {
		return defaultMetricPercentage, 0, nil
	}
	query := `
		SELECT count(*) FILTER (WHERE decision = 'allow'), count(*)
		FROM policy_evaluation_records
		WHERE evaluated_at >= $1 AND enterprise_tenant_id = $2
	`
	args := []any{windowStart, *tenantID}
	if resourceID != nil {
		args = append(args, *resourceID)
		query += fmt.Sprintf(" AND sovereignty_policy_id = $%d", len(args))
	}
	return scanRatio(ctx, c, query, args)
}

// appendOwnerFilter adds "AND <operatorCol> = $n" or "AND <tenantCol> = $n"
// to query depending on which of operatorID/tenantID is set -- exactly one
// is, by every caller's own CHECK-constraint-enforced invariant.
func appendOwnerFilter(query string, args []any, operatorCol, tenantCol string, operatorID, tenantID *uuid.UUID) (string, []any) {
	if operatorID != nil {
		args = append(args, *operatorID)
		return query + fmt.Sprintf(" AND %s = $%d", operatorCol, len(args)), args
	}
	args = append(args, *tenantID)
	return query + fmt.Sprintf(" AND %s = $%d", tenantCol, len(args)), args
}

func scanRatio(ctx context.Context, c conn, query string, args []any) (float64, int, error) {
	var successCount, total int
	if err := c.QueryRow(ctx, query, args...).Scan(&successCount, &total); err != nil {
		return 0, 0, fmt.Errorf("compute metric ratio: %w", err)
	}
	if total == 0 {
		return defaultMetricPercentage, 0, nil
	}
	return float64(successCount) / float64(total) * 100, total, nil
}

// getCorrelatedHealth computes every metric over a fixed 24-hour window for
// one scope (operator xor tenant), plus current open-incident/firing-alert
// counts -- the read-time join the approved architecture's "Correlate: ..."
// requirement asks for.
func getCorrelatedHealth(ctx context.Context, c conn, operatorID, tenantID *uuid.UUID) (CorrelatedHealth, error) {
	windowStart := time.Now().Add(-24 * time.Hour)
	var h CorrelatedHealth
	var err error
	h.DeploymentAvailabilityPercentage, h.DeploymentSampleSize, err = computeDeploymentAvailability(ctx, c, operatorID, tenantID, nil, windowStart)
	if err != nil {
		return CorrelatedHealth{}, err
	}
	h.NetworkProvisioningPercentage, h.NetworkSampleSize, err = computeNetworkProvisioning(ctx, c, operatorID, tenantID, nil, windowStart)
	if err != nil {
		return CorrelatedHealth{}, err
	}
	h.AttestationSuccessPercentage, h.AttestationSampleSize, err = computeAttestationSuccessRate(ctx, c, operatorID, tenantID, nil, windowStart)
	if err != nil {
		return CorrelatedHealth{}, err
	}
	h.PolicyComplianceRatePercentage, h.PolicySampleSize, err = computePolicyComplianceRate(ctx, c, operatorID, tenantID, nil, windowStart)
	if err != nil {
		return CorrelatedHealth{}, err
	}
	if operatorID != nil {
		h.OpenIncidentCount, err = countOpenIncidentsForOperator(ctx, c, *operatorID)
		if err != nil {
			return CorrelatedHealth{}, err
		}
		h.FiringAlertCount, err = countFiringAlertsForOperator(ctx, c, *operatorID)
		if err != nil {
			return CorrelatedHealth{}, err
		}
		return h, nil
	}
	h.OpenIncidentCount, err = countOpenIncidentsForTenant(ctx, c, *tenantID)
	if err != nil {
		return CorrelatedHealth{}, err
	}
	h.FiringAlertCount, err = countFiringAlertsForTenant(ctx, c, *tenantID)
	if err != nil {
		return CorrelatedHealth{}, err
	}
	return h, nil
}

// ---------------------------------------------------------------------
// Audit correlation -- "audit correlation" in the approved scope is a
// read against Milestone 1's existing audit_events by target, not a new
// table; RLS on audit_events already scopes visibility correctly.
// ---------------------------------------------------------------------

type CorrelatedAuditEvent struct {
	ID         uuid.UUID      `json:"id"`
	OccurredAt time.Time      `json:"occurred_at"`
	Action     string         `json:"action"`
	TargetType *string        `json:"target_type,omitempty"`
	TargetID   *uuid.UUID     `json:"target_id,omitempty"`
	Evidence   map[string]any `json:"evidence"`
}

func listAuditEventsForResource(ctx context.Context, c conn, resourceType string, resourceID uuid.UUID) ([]CorrelatedAuditEvent, error) {
	rows, err := c.Query(ctx, `
		SELECT id, occurred_at, action, target_type, target_id, evidence
		FROM audit_events WHERE target_type = $1 AND target_id = $2 ORDER BY occurred_at DESC LIMIT 100
	`, resourceType, resourceID)
	if err != nil {
		return nil, fmt.Errorf("list correlated audit events: %w", err)
	}
	defer rows.Close()
	out := []CorrelatedAuditEvent{}
	for rows.Next() {
		var e CorrelatedAuditEvent
		var evidenceRaw []byte
		if err := rows.Scan(&e.ID, &e.OccurredAt, &e.Action, &e.TargetType, &e.TargetID, &evidenceRaw); err != nil {
			return nil, fmt.Errorf("scan correlated audit event: %w", err)
		}
		if err := json.Unmarshal(evidenceRaw, &e.Evidence); err != nil {
			return nil, fmt.Errorf("decode audit evidence: %w", err)
		}
		out = append(out, e)
	}
	return out, rows.Err()
}
