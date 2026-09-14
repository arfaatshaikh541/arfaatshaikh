from app.db.base import Base
import app.models  # noqa: F401
from app.services.operations import AlertRuleInput, evaluate_incident_readiness, evaluate_resilience_gate, validate_alert_rule

def test_operations_tables_registered():
    assert {"operational_alert_rules", "operational_alert_events", "operational_incidents", "runbook_executions"}.issubset(Base.metadata.tables)

def test_alert_rejects_metrics_application_does_not_emit():
    result = validate_alert_rule(AlertRuleInput("imaginary_metric", "critical", 1, 300, "https://runbooks.example/critical"))
    assert result["valid"] is False
    assert "metric_not_emitted" in result["reason_codes"]

def test_alert_requires_sane_window_and_runbook():
    result = validate_alert_rule(AlertRuleInput("http_5xx_rate", "high", 1, 10, "ftp://unsafe"))
    assert result["valid"] is False
    assert {"evaluation_window_too_short", "invalid_runbook_uri"}.issubset(result["reason_codes"])

def test_sev1_response_fails_closed_without_command_communications_and_rollback():
    result = evaluate_incident_readiness(severity="sev1", commander_assigned=False, customer_impact_documented=True, runbook_attached=True, communication_channel_ready=False, rollback_path_verified=False)
    assert result["response_ready"] is False
    assert {"incident_commander_required", "communication_channel_required", "verified_rollback_required"}.issubset(result["reason_codes"])

def test_resilience_gate_blocks_open_high_severity_incident():
    result = evaluate_resilience_gate(health_slo_passed=True, alert_coverage_passed=True, incident_drill_passed=True, backup_fresh=True, restore_rehearsal_passed=True, rollback_verified=True, open_sev1_or_sev2=1)
    assert result["production_resilient"] is False
    assert "open_high_severity_incidents" in result["reason_codes"]

def test_resilience_gate_passes_with_all_operational_evidence():
    result = evaluate_resilience_gate(health_slo_passed=True, alert_coverage_passed=True, incident_drill_passed=True, backup_fresh=True, restore_rehearsal_passed=True, rollback_verified=True, open_sev1_or_sev2=0)
    assert result["production_resilient"] is True
