package assurance

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/audit"
	"gridkeep/control-api/internal/platform/httpserver"
)

var (
	ErrSLONotFound                   = errors.New("slo definition not found")
	ErrSLONotActive                  = errors.New("slo definition is archived")
	ErrIncidentNotFound              = errors.New("incident not found")
	ErrIncidentNotOpen               = errors.New("incident is not open")
	ErrIncidentNotOpenOrAcknowledged = errors.New("incident is not open or acknowledged")
	ErrAlertRuleNotFound             = errors.New("alert rule not found")
)

type Service struct{}

func NewService() *Service {
	return &Service{}
}

func actorFromContext(ctx context.Context) uuid.UUID {
	if authUser, ok := httpserver.AuthUser(ctx); ok {
		return authUser.UserID
	}
	return uuid.Nil
}

// computeMetric dispatches to the one repository function that reads
// whichever existing table a metric_source names -- the single place
// SLO evaluation and alert-rule evaluation both go through, so the two
// concepts can never drift into computing the same named metric two
// different ways.
func computeMetric(ctx context.Context, tx conn, metricSource string, operatorID, tenantID *uuid.UUID, resourceID *uuid.UUID, windowStart time.Time) (float64, int, error) {
	switch metricSource {
	case "deployment_availability":
		return computeDeploymentAvailability(ctx, tx, operatorID, tenantID, resourceID, windowStart)
	case "network_reservation_provisioning":
		return computeNetworkProvisioning(ctx, tx, operatorID, tenantID, resourceID, windowStart)
	case "attestation_success_rate":
		return computeAttestationSuccessRate(ctx, tx, operatorID, tenantID, resourceID, windowStart)
	case "policy_compliance_rate":
		return computePolicyComplianceRate(ctx, tx, operatorID, tenantID, resourceID, windowStart)
	default:
		return 0, 0, fmt.Errorf("unknown metric source %q", metricSource)
	}
}

// ---------------------------------------------------------------------
// SLOs (enterprise-scoped)
// ---------------------------------------------------------------------

func (s *Service) CreateSLO(ctx context.Context, in CreateSLOInput) (SLODefinition, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	slo, err := createSLO(ctx, scopedTx.Tx, nil, scope.TenantID, actor, in)
	if err != nil {
		return SLODefinition{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "slos.created", TargetType: "slo_definition", TargetID: &slo.ID,
		Evidence: map[string]any{"metric_source": in.MetricSource, "target_percentage": in.TargetPercentage},
	}); err != nil {
		return SLODefinition{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return SLODefinition{}, err
	}
	return slo, nil
}

func (s *Service) ListSLOs(ctx context.Context) ([]SLODefinition, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listSLOsForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) ArchiveSLO(ctx context.Context, id uuid.UUID) error {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	_, exists, err := getSLOByIDTenant(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return err
	}
	if !exists {
		return ErrSLONotFound
	}
	ok, err := archiveSLO(ctx, scopedTx.Tx, id)
	if err != nil {
		return err
	}
	if !ok {
		return ErrSLONotActive
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "slos.archived", TargetType: "slo_definition", TargetID: &id,
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

// EvaluateSLO runs computeMetric over this SLO's own window_days and
// metric_source, persists the result as an immutable slo_evaluations row,
// and returns it -- there is no live scheduler in this codebase, so this
// is invoked on demand (a dashboard refresh, an explicit "evaluate now"
// action) rather than on a fixed cadence.
func (s *Service) EvaluateSLO(ctx context.Context, id uuid.UUID) (SLOEvaluation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	slo, exists, err := getSLOByIDTenant(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return SLOEvaluation{}, err
	}
	if !exists {
		return SLOEvaluation{}, ErrSLONotFound
	}
	if slo.Status != "active" {
		return SLOEvaluation{}, ErrSLONotActive
	}
	windowStart := time.Now().AddDate(0, 0, -slo.WindowDays)
	pct, sampleSize, err := computeMetric(ctx, scopedTx.Tx, slo.MetricSource, slo.OperatorID, slo.EnterpriseTenantID, slo.ResourceID, windowStart)
	if err != nil {
		return SLOEvaluation{}, err
	}
	eval, err := insertSLOEvaluation(ctx, scopedTx.Tx, id, slo.OperatorID, slo.EnterpriseTenantID, pct, slo.TargetPercentage, sampleSize,
		map[string]any{"metric_source": slo.MetricSource, "window_days": slo.WindowDays})
	if err != nil {
		return SLOEvaluation{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return SLOEvaluation{}, err
	}
	return eval, nil
}

func (s *Service) ListSLOEvaluations(ctx context.Context, id uuid.UUID) ([]SLOEvaluation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	if _, exists, err := getSLOByIDTenant(ctx, scopedTx.Tx, *scope.TenantID, id); err != nil {
		return nil, err
	} else if !exists {
		return nil, ErrSLONotFound
	}
	return listSLOEvaluations(ctx, scopedTx.Tx, id)
}

// ---------------------------------------------------------------------
// SLOs (operator-scoped)
// ---------------------------------------------------------------------

func (s *Service) CreateOperatorSLO(ctx context.Context, in CreateSLOInput) (SLODefinition, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	slo, err := createSLO(ctx, scopedTx.Tx, scope.OperatorID, nil, actor, in)
	if err != nil {
		return SLODefinition{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "slos.created", TargetType: "slo_definition", TargetID: &slo.ID,
		Evidence: map[string]any{"metric_source": in.MetricSource, "target_percentage": in.TargetPercentage},
	}); err != nil {
		return SLODefinition{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return SLODefinition{}, err
	}
	return slo, nil
}

func (s *Service) ListOperatorSLOs(ctx context.Context) ([]SLODefinition, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listSLOsForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) ArchiveOperatorSLO(ctx context.Context, id uuid.UUID) error {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	_, exists, err := getSLOByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return err
	}
	if !exists {
		return ErrSLONotFound
	}
	ok, err := archiveSLO(ctx, scopedTx.Tx, id)
	if err != nil {
		return err
	}
	if !ok {
		return ErrSLONotActive
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "slos.archived", TargetType: "slo_definition", TargetID: &id,
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

func (s *Service) EvaluateOperatorSLO(ctx context.Context, id uuid.UUID) (SLOEvaluation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	slo, exists, err := getSLOByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return SLOEvaluation{}, err
	}
	if !exists {
		return SLOEvaluation{}, ErrSLONotFound
	}
	if slo.Status != "active" {
		return SLOEvaluation{}, ErrSLONotActive
	}
	windowStart := time.Now().AddDate(0, 0, -slo.WindowDays)
	pct, sampleSize, err := computeMetric(ctx, scopedTx.Tx, slo.MetricSource, slo.OperatorID, slo.EnterpriseTenantID, slo.ResourceID, windowStart)
	if err != nil {
		return SLOEvaluation{}, err
	}
	eval, err := insertSLOEvaluation(ctx, scopedTx.Tx, id, slo.OperatorID, slo.EnterpriseTenantID, pct, slo.TargetPercentage, sampleSize,
		map[string]any{"metric_source": slo.MetricSource, "window_days": slo.WindowDays})
	if err != nil {
		return SLOEvaluation{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return SLOEvaluation{}, err
	}
	return eval, nil
}

func (s *Service) ListOperatorSLOEvaluations(ctx context.Context, id uuid.UUID) ([]SLOEvaluation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	if _, exists, err := getSLOByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id); err != nil {
		return nil, err
	} else if !exists {
		return nil, ErrSLONotFound
	}
	return listSLOEvaluations(ctx, scopedTx.Tx, id)
}

// ---------------------------------------------------------------------
// Incidents (enterprise-scoped)
// ---------------------------------------------------------------------

func (s *Service) CreateIncident(ctx context.Context, in CreateIncidentInput) (Incident, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	inc, err := createIncident(ctx, scopedTx.Tx, nil, scope.TenantID, actor, in)
	if err != nil {
		return Incident{}, err
	}
	if _, err := insertIncidentEvent(ctx, scopedTx.Tx, inc.ID, nil, scope.TenantID, "opened",
		map[string]any{"severity": in.Severity, "title": in.Title}, &actor); err != nil {
		return Incident{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "incidents.opened", TargetType: "incident", TargetID: &inc.ID,
		Evidence: map[string]any{"severity": in.Severity},
	}); err != nil {
		return Incident{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Incident{}, err
	}
	return inc, nil
}

func (s *Service) ListIncidents(ctx context.Context) ([]Incident, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listIncidentsForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) AcknowledgeIncident(ctx context.Context, id uuid.UUID) (Incident, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getIncidentByIDTenant(ctx, scopedTx.Tx, *scope.TenantID, id); err != nil {
		return Incident{}, err
	} else if !exists {
		return Incident{}, ErrIncidentNotFound
	}
	ok, err := acknowledgeIncident(ctx, scopedTx.Tx, id, actor)
	if err != nil {
		return Incident{}, err
	}
	if !ok {
		return Incident{}, ErrIncidentNotOpen
	}
	if _, err := insertIncidentEvent(ctx, scopedTx.Tx, id, nil, scope.TenantID, "acknowledged", map[string]any{}, &actor); err != nil {
		return Incident{}, err
	}
	updated, exists, err := getIncidentByIDTenant(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return Incident{}, err
	}
	if !exists {
		return Incident{}, ErrIncidentNotFound
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Incident{}, err
	}
	return updated, nil
}

func (s *Service) ResolveIncident(ctx context.Context, id uuid.UUID) (Incident, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getIncidentByIDTenant(ctx, scopedTx.Tx, *scope.TenantID, id); err != nil {
		return Incident{}, err
	} else if !exists {
		return Incident{}, ErrIncidentNotFound
	}
	ok, err := resolveIncident(ctx, scopedTx.Tx, id, actor)
	if err != nil {
		return Incident{}, err
	}
	if !ok {
		return Incident{}, ErrIncidentNotOpenOrAcknowledged
	}
	if _, err := insertIncidentEvent(ctx, scopedTx.Tx, id, nil, scope.TenantID, "resolved", map[string]any{}, &actor); err != nil {
		return Incident{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "incidents.resolved", TargetType: "incident", TargetID: &id,
	}); err != nil {
		return Incident{}, err
	}
	updated, exists, err := getIncidentByIDTenant(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return Incident{}, err
	}
	if !exists {
		return Incident{}, ErrIncidentNotFound
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Incident{}, err
	}
	return updated, nil
}

func (s *Service) ListIncidentEvents(ctx context.Context, id uuid.UUID) ([]IncidentEvent, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	if _, exists, err := getIncidentByIDTenant(ctx, scopedTx.Tx, *scope.TenantID, id); err != nil {
		return nil, err
	} else if !exists {
		return nil, ErrIncidentNotFound
	}
	return listIncidentEvents(ctx, scopedTx.Tx, id)
}

// ---------------------------------------------------------------------
// Incidents (operator-scoped)
// ---------------------------------------------------------------------

func (s *Service) CreateOperatorIncident(ctx context.Context, in CreateIncidentInput) (Incident, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	inc, err := createIncident(ctx, scopedTx.Tx, scope.OperatorID, nil, actor, in)
	if err != nil {
		return Incident{}, err
	}
	if _, err := insertIncidentEvent(ctx, scopedTx.Tx, inc.ID, scope.OperatorID, nil, "opened",
		map[string]any{"severity": in.Severity, "title": in.Title}, &actor); err != nil {
		return Incident{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "incidents.opened", TargetType: "incident", TargetID: &inc.ID,
		Evidence: map[string]any{"severity": in.Severity},
	}); err != nil {
		return Incident{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Incident{}, err
	}
	return inc, nil
}

func (s *Service) ListOperatorIncidents(ctx context.Context) ([]Incident, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listIncidentsForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) AcknowledgeOperatorIncident(ctx context.Context, id uuid.UUID) (Incident, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getIncidentByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id); err != nil {
		return Incident{}, err
	} else if !exists {
		return Incident{}, ErrIncidentNotFound
	}
	ok, err := acknowledgeIncident(ctx, scopedTx.Tx, id, actor)
	if err != nil {
		return Incident{}, err
	}
	if !ok {
		return Incident{}, ErrIncidentNotOpen
	}
	if _, err := insertIncidentEvent(ctx, scopedTx.Tx, id, scope.OperatorID, nil, "acknowledged", map[string]any{}, &actor); err != nil {
		return Incident{}, err
	}
	updated, exists, err := getIncidentByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return Incident{}, err
	}
	if !exists {
		return Incident{}, ErrIncidentNotFound
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Incident{}, err
	}
	return updated, nil
}

func (s *Service) ResolveOperatorIncident(ctx context.Context, id uuid.UUID) (Incident, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getIncidentByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id); err != nil {
		return Incident{}, err
	} else if !exists {
		return Incident{}, ErrIncidentNotFound
	}
	ok, err := resolveIncident(ctx, scopedTx.Tx, id, actor)
	if err != nil {
		return Incident{}, err
	}
	if !ok {
		return Incident{}, ErrIncidentNotOpenOrAcknowledged
	}
	if _, err := insertIncidentEvent(ctx, scopedTx.Tx, id, scope.OperatorID, nil, "resolved", map[string]any{}, &actor); err != nil {
		return Incident{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "incidents.resolved", TargetType: "incident", TargetID: &id,
	}); err != nil {
		return Incident{}, err
	}
	updated, exists, err := getIncidentByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return Incident{}, err
	}
	if !exists {
		return Incident{}, ErrIncidentNotFound
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Incident{}, err
	}
	return updated, nil
}

func (s *Service) ListOperatorIncidentEvents(ctx context.Context, id uuid.UUID) ([]IncidentEvent, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	if _, exists, err := getIncidentByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id); err != nil {
		return nil, err
	} else if !exists {
		return nil, ErrIncidentNotFound
	}
	return listIncidentEvents(ctx, scopedTx.Tx, id)
}

// ---------------------------------------------------------------------
// Alert rules and alerts (enterprise-scoped)
// ---------------------------------------------------------------------

func (s *Service) CreateAlertRule(ctx context.Context, in CreateAlertRuleInput) (AlertRule, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	rule, err := createAlertRule(ctx, scopedTx.Tx, nil, scope.TenantID, actor, in)
	if err != nil {
		return AlertRule{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "alert_rules.created", TargetType: "alert_rule", TargetID: &rule.ID,
		Evidence: map[string]any{"metric_source": in.MetricSource, "comparison": in.Comparison, "threshold": in.Threshold},
	}); err != nil {
		return AlertRule{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return AlertRule{}, err
	}
	return rule, nil
}

func (s *Service) ListAlertRules(ctx context.Context) ([]AlertRule, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listAlertRulesForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) SetAlertRuleStatus(ctx context.Context, id uuid.UUID, status string) error {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	if _, exists, err := getAlertRuleByIDTenant(ctx, scopedTx.Tx, *scope.TenantID, id); err != nil {
		return err
	} else if !exists {
		return ErrAlertRuleNotFound
	}
	if _, err := setAlertRuleStatus(ctx, scopedTx.Tx, id, status); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

// EvaluateAlertRule computes the rule's metric over a fixed 24-hour window,
// compares it against the threshold, and fires a new alert (if none is
// already firing for this rule -- idempotent, never duplicate-fires) or
// resolves the currently-firing one if the condition no longer holds.
func (s *Service) EvaluateAlertRule(ctx context.Context, id uuid.UUID) (*Alert, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	rule, exists, err := getAlertRuleByIDTenant(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return nil, err
	}
	if !exists {
		return nil, ErrAlertRuleNotFound
	}
	if rule.Status != "active" {
		return nil, nil
	}
	alert, err := evaluateAlertRule(ctx, scopedTx.Tx, rule)
	if err != nil {
		return nil, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return nil, err
	}
	return alert, nil
}

func (s *Service) ListAlerts(ctx context.Context) ([]Alert, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listAlertsForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

// ---------------------------------------------------------------------
// Alert rules and alerts (operator-scoped)
// ---------------------------------------------------------------------

func (s *Service) CreateOperatorAlertRule(ctx context.Context, in CreateAlertRuleInput) (AlertRule, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	rule, err := createAlertRule(ctx, scopedTx.Tx, scope.OperatorID, nil, actor, in)
	if err != nil {
		return AlertRule{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "alert_rules.created", TargetType: "alert_rule", TargetID: &rule.ID,
		Evidence: map[string]any{"metric_source": in.MetricSource, "comparison": in.Comparison, "threshold": in.Threshold},
	}); err != nil {
		return AlertRule{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return AlertRule{}, err
	}
	return rule, nil
}

func (s *Service) ListOperatorAlertRules(ctx context.Context) ([]AlertRule, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listAlertRulesForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) SetOperatorAlertRuleStatus(ctx context.Context, id uuid.UUID, status string) error {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	if _, exists, err := getAlertRuleByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id); err != nil {
		return err
	} else if !exists {
		return ErrAlertRuleNotFound
	}
	if _, err := setAlertRuleStatus(ctx, scopedTx.Tx, id, status); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

func (s *Service) EvaluateOperatorAlertRule(ctx context.Context, id uuid.UUID) (*Alert, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	rule, exists, err := getAlertRuleByIDOperator(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return nil, err
	}
	if !exists {
		return nil, ErrAlertRuleNotFound
	}
	if rule.Status != "active" {
		return nil, nil
	}
	alert, err := evaluateAlertRule(ctx, scopedTx.Tx, rule)
	if err != nil {
		return nil, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return nil, err
	}
	return alert, nil
}

func (s *Service) ListOperatorAlerts(ctx context.Context) ([]Alert, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listAlertsForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

// evaluateAlertRule is the scope-agnostic core EvaluateAlertRule and
// EvaluateOperatorAlertRule both call: compute the metric (or, for
// slo_burn_rate, read the referenced SLO's latest evaluation instead of
// recomputing it independently -- an alert about an SLO's burn rate must
// track that exact SLO's own evaluation history, not a second, possibly
// different, ad-hoc computation), compare against the threshold, fire or
// resolve idempotently.
func evaluateAlertRule(ctx context.Context, tx conn, rule AlertRule) (*Alert, error) {
	var value float64
	switch rule.MetricSource {
	case "slo_burn_rate":
		if rule.ResourceID == nil {
			return nil, fmt.Errorf("slo_burn_rate alert rule %s has no resource_id (slo_definition id)", rule.ID)
		}
		evals, err := listSLOEvaluations(ctx, tx, *rule.ResourceID)
		if err != nil {
			return nil, err
		}
		if len(evals) == 0 {
			value = 0
		} else {
			value = 100 - evals[0].ActualPercentage
		}
	case "budget_utilization":
		if rule.ResourceID == nil {
			return nil, fmt.Errorf("budget_utilization alert rule %s has no resource_id (budget id)", rule.ID)
		}
		pct, err := computeBudgetUtilization(ctx, tx, *rule.ResourceID)
		if err != nil {
			return nil, err
		}
		value = pct
	default:
		windowStart := time.Now().Add(-24 * time.Hour)
		pct, _, err := computeMetric(ctx, tx, rule.MetricSource, rule.OperatorID, rule.EnterpriseTenantID, rule.ResourceID, windowStart)
		if err != nil {
			return nil, err
		}
		value = pct
	}

	breached := (rule.Comparison == "lt" && value < rule.Threshold) || (rule.Comparison == "gt" && value > rule.Threshold)

	existing, firing, err := getFiringAlertForRule(ctx, tx, rule.ID)
	if err != nil {
		return nil, err
	}
	if breached {
		if firing {
			return &existing, nil
		}
		alert, err := fireAlert(ctx, tx, rule.ID, rule.OperatorID, rule.EnterpriseTenantID, value,
			map[string]any{"metric_source": rule.MetricSource, "comparison": rule.Comparison, "threshold": rule.Threshold})
		if err != nil {
			return nil, err
		}
		return &alert, nil
	}
	if firing {
		if err := resolveAlert(ctx, tx, existing.ID); err != nil {
			return nil, err
		}
	}
	return nil, nil
}

// ---------------------------------------------------------------------
// Correlated health (enterprise + operator)
// ---------------------------------------------------------------------

func (s *Service) GetCorrelatedHealth(ctx context.Context) (CorrelatedHealth, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return getCorrelatedHealth(ctx, scopedTx.Tx, nil, scope.TenantID)
}

func (s *Service) GetOperatorCorrelatedHealth(ctx context.Context) (CorrelatedHealth, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return getCorrelatedHealth(ctx, scopedTx.Tx, scope.OperatorID, nil)
}

// ---------------------------------------------------------------------
// Audit correlation -- reuses audit.view/operator.audit.view (Milestone 1)
// rather than assurance.view, since this exposes audit evidence directly,
// the same disclosure auditlog's own routes already gate.
// ---------------------------------------------------------------------

func (s *Service) ListCorrelatedAuditEvents(ctx context.Context, resourceType string, resourceID uuid.UUID) ([]CorrelatedAuditEvent, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listAuditEventsForResource(ctx, scopedTx.Tx, resourceType, resourceID)
}
