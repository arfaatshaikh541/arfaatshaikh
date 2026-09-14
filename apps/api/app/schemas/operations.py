from pydantic import BaseModel, Field

class AlertRuleRequest(BaseModel):
    metric_name: str = Field(min_length=1, max_length=160)
    severity: str = Field(pattern="^(info|warning|high|critical)$")
    threshold: int = Field(ge=0)
    evaluation_window_seconds: int = Field(ge=1, le=86400)
    runbook_uri: str = Field(min_length=1, max_length=1000)
    enabled: bool = True

class IncidentReadinessRequest(BaseModel):
    severity: str = Field(pattern="^(sev1|sev2|sev3|sev4)$")
    commander_assigned: bool
    customer_impact_documented: bool
    runbook_attached: bool
    communication_channel_ready: bool
    rollback_path_verified: bool

class ResilienceGateRequest(BaseModel):
    health_slo_passed: bool
    alert_coverage_passed: bool
    incident_drill_passed: bool
    backup_fresh: bool
    restore_rehearsal_passed: bool
    rollback_verified: bool
    open_sev1_or_sev2: int = Field(ge=0)
