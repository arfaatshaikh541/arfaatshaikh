from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlparse

OPERATIONS_POLICY_VERSION = "operations-v1"
ALLOWED_METRICS = {
    "http_5xx_rate", "request_latency_p95_ms", "readiness_failure_count",
    "queue_depth", "worker_failure_count", "database_connection_saturation_pct",
    "ai_grounding_block_rate", "backup_age_hours",
}

@dataclass(frozen=True)
class AlertRuleInput:
    metric_name: str
    severity: str
    threshold: int
    evaluation_window_seconds: int
    runbook_uri: str
    enabled: bool = True

def validate_alert_rule(rule: AlertRuleInput) -> dict[str, object]:
    reasons: list[str] = []
    if rule.metric_name not in ALLOWED_METRICS:
        reasons.append("metric_not_emitted")
    if rule.severity not in {"info", "warning", "high", "critical"}:
        reasons.append("invalid_severity")
    if rule.threshold < 0:
        reasons.append("negative_threshold")
    if rule.evaluation_window_seconds < 60:
        reasons.append("evaluation_window_too_short")
    parsed = urlparse(rule.runbook_uri)
    if parsed.scheme not in {"https", "runbook"} or not (parsed.netloc or parsed.path):
        reasons.append("invalid_runbook_uri")
    if rule.enabled and rule.severity in {"high", "critical"} and not rule.runbook_uri.strip():
        reasons.append("runbook_required")
    return {"valid": not reasons, "reason_codes": reasons or ["alert_rule_valid"], "policy_version": OPERATIONS_POLICY_VERSION}

def evaluate_incident_readiness(*, severity: str, commander_assigned: bool, customer_impact_documented: bool, runbook_attached: bool, communication_channel_ready: bool, rollback_path_verified: bool) -> dict[str, object]:
    if severity not in {"sev1", "sev2", "sev3", "sev4"}:
        raise ValueError("unsupported incident severity")
    reasons: list[str] = []
    if severity in {"sev1", "sev2"} and not commander_assigned:
        reasons.append("incident_commander_required")
    if not customer_impact_documented:
        reasons.append("customer_impact_required")
    if not runbook_attached:
        reasons.append("runbook_required")
    if severity in {"sev1", "sev2"} and not communication_channel_ready:
        reasons.append("communication_channel_required")
    if severity == "sev1" and not rollback_path_verified:
        reasons.append("verified_rollback_required")
    return {"response_ready": not reasons, "reason_codes": reasons or ["incident_response_ready"], "policy_version": OPERATIONS_POLICY_VERSION}

def evaluate_resilience_gate(*, health_slo_passed: bool, alert_coverage_passed: bool, incident_drill_passed: bool, backup_fresh: bool, restore_rehearsal_passed: bool, rollback_verified: bool, open_sev1_or_sev2: int) -> dict[str, object]:
    reasons: list[str] = []
    checks = {
        "health_slo_failed": health_slo_passed,
        "alert_coverage_failed": alert_coverage_passed,
        "incident_drill_failed": incident_drill_passed,
        "backup_stale": backup_fresh,
        "restore_rehearsal_failed": restore_rehearsal_passed,
        "rollback_unverified": rollback_verified,
    }
    reasons.extend(code for code, passed in checks.items() if not passed)
    if open_sev1_or_sev2 > 0:
        reasons.append("open_high_severity_incidents")
    return {"production_resilient": not reasons, "reason_codes": reasons or ["resilience_gate_passed"], "policy_version": OPERATIONS_POLICY_VERSION}
