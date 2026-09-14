from app.db.base import Base
import app.models  # noqa: F401
from app.services.launch_governance import TenantLifecycleResult, evaluate_launch_readiness, evaluate_security_audit, validate_tenant_lifecycle

def test_launch_governance_tables_registered():
    assert {"production_launch_approvals", "tenant_lifecycle_exercises", "final_security_audits", "milestone_acceptances"}.issubset(Base.metadata.tables)

def test_tenant_lifecycle_rejects_cross_tenant_access():
    result = validate_tenant_lifecycle(TenantLifecycleResult("export", "passed", "a" * 64, True, 10))
    assert result["valid"] is False
    assert "cross_tenant_access_detected" in result["reason_codes"]

def test_tenant_lifecycle_requires_verified_evidence():
    result = validate_tenant_lifecycle(TenantLifecycleResult("deletion", "passed", None, False, 10))
    assert result["valid"] is False
    assert "verified_evidence_fingerprint_required" in result["reason_codes"]

def test_security_audit_fails_open_findings_and_missing_scope():
    result = evaluate_security_audit(independent_auditor=False, tenant_isolation_tested=False, authorization_tested=False, evidence_integrity_tested=False, critical_findings=1, high_findings=2, report_verified=False)
    assert result["audit_passed"] is False
    assert len(result["reason_codes"]) == 7

def test_security_audit_passes_complete_evidence():
    result = evaluate_security_audit(independent_auditor=True, tenant_isolation_tested=True, authorization_tested=True, evidence_integrity_tested=True, critical_findings=0, high_findings=0, report_verified=True)
    assert result["audit_passed"] is True

def test_launch_gate_requires_every_approval():
    result = evaluate_launch_readiness(approved_roles={"security"}, deployment_ready=True, resilience_ready=True, enterprise_ready=True, ai_release_gate_passed=True, security_audit_passed=True, tenant_export_verified=True, tenant_deletion_verified=True, rollback_verified=True, open_sev1_or_sev2=0, unresolved_critical_or_high_findings=0)
    assert result["launch_ready"] is False
    assert result["reason_codes"][0].startswith("missing_launch_approvals:")

def test_launch_gate_fails_severe_incidents():
    roles = {"security", "privacy", "scholarly", "operations", "product", "executive"}
    result = evaluate_launch_readiness(approved_roles=roles, deployment_ready=True, resilience_ready=True, enterprise_ready=True, ai_release_gate_passed=True, security_audit_passed=True, tenant_export_verified=True, tenant_deletion_verified=True, rollback_verified=True, open_sev1_or_sev2=1, unresolved_critical_or_high_findings=0)
    assert result["launch_ready"] is False
    assert "severe_incidents_open" in result["reason_codes"]

def test_launch_gate_passes_complete_contract():
    roles = {"security", "privacy", "scholarly", "operations", "product", "executive"}
    result = evaluate_launch_readiness(approved_roles=roles, deployment_ready=True, resilience_ready=True, enterprise_ready=True, ai_release_gate_passed=True, security_audit_passed=True, tenant_export_verified=True, tenant_deletion_verified=True, rollback_verified=True, open_sev1_or_sev2=0, unresolved_critical_or_high_findings=0)
    assert result["launch_ready"] is True
