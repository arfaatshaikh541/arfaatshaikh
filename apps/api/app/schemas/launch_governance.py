from pydantic import BaseModel, Field

class TenantLifecycleValidationRequest(BaseModel):
    exercise_type: str
    status: str
    evidence_sha256: str | None = None
    cross_tenant_access_detected: bool = False
    records_processed: int = 0

class SecurityAuditEvaluationRequest(BaseModel):
    independent_auditor: bool
    tenant_isolation_tested: bool
    authorization_tested: bool
    evidence_integrity_tested: bool
    critical_findings: int = Field(ge=0)
    high_findings: int = Field(ge=0)
    report_verified: bool

class LaunchReadinessRequest(BaseModel):
    approved_roles: set[str]
    deployment_ready: bool
    resilience_ready: bool
    enterprise_ready: bool
    ai_release_gate_passed: bool
    security_audit_passed: bool
    tenant_export_verified: bool
    tenant_deletion_verified: bool
    rollback_verified: bool
    open_sev1_or_sev2: int = Field(ge=0)
    unresolved_critical_or_high_findings: int = Field(ge=0)
