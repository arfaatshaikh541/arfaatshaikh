from __future__ import annotations
from dataclasses import dataclass

LAUNCH_POLICY_VERSION = "launch-governance-v1"
REQUIRED_APPROVALS = {"security", "privacy", "scholarly", "operations", "product", "executive"}

@dataclass(frozen=True)
class TenantLifecycleResult:
    exercise_type: str
    status: str
    evidence_sha256: str | None
    cross_tenant_access_detected: bool
    records_processed: int


def validate_tenant_lifecycle(result: TenantLifecycleResult) -> dict[str, object]:
    reasons: list[str] = []
    if result.exercise_type not in {"export", "deletion", "suspension", "reactivation", "archive", "restore"}:
        reasons.append("unsupported_lifecycle_exercise")
    if result.status != "passed":
        reasons.append("lifecycle_exercise_not_passed")
    if result.cross_tenant_access_detected:
        reasons.append("cross_tenant_access_detected")
    if result.records_processed < 0:
        reasons.append("invalid_record_count")
    if not result.evidence_sha256 or len(result.evidence_sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in result.evidence_sha256):
        reasons.append("verified_evidence_fingerprint_required")
    return {"valid": not reasons, "reason_codes": reasons or ["tenant_lifecycle_verified"], "policy_version": LAUNCH_POLICY_VERSION}


def evaluate_security_audit(*, independent_auditor: bool, tenant_isolation_tested: bool, authorization_tested: bool, evidence_integrity_tested: bool, critical_findings: int, high_findings: int, report_verified: bool) -> dict[str, object]:
    reasons: list[str] = []
    if min(critical_findings, high_findings) < 0:
        raise ValueError("finding counts cannot be negative")
    if not independent_auditor: reasons.append("independent_auditor_required")
    if not tenant_isolation_tested: reasons.append("tenant_isolation_test_required")
    if not authorization_tested: reasons.append("authorization_test_required")
    if not evidence_integrity_tested: reasons.append("evidence_integrity_test_required")
    if critical_findings: reasons.append("critical_security_findings_open")
    if high_findings: reasons.append("high_security_findings_open")
    if not report_verified: reasons.append("verified_audit_report_required")
    return {"audit_passed": not reasons, "reason_codes": reasons or ["final_security_audit_passed"], "policy_version": LAUNCH_POLICY_VERSION}


def evaluate_launch_readiness(*, approved_roles: set[str], deployment_ready: bool, resilience_ready: bool, enterprise_ready: bool, ai_release_gate_passed: bool, security_audit_passed: bool, tenant_export_verified: bool, tenant_deletion_verified: bool, rollback_verified: bool, open_sev1_or_sev2: int, unresolved_critical_or_high_findings: int) -> dict[str, object]:
    reasons: list[str] = []
    missing = sorted(REQUIRED_APPROVALS - set(approved_roles))
    if missing: reasons.append("missing_launch_approvals:" + ",".join(missing))
    if not deployment_ready: reasons.append("deployment_not_ready")
    if not resilience_ready: reasons.append("resilience_not_ready")
    if not enterprise_ready: reasons.append("enterprise_not_ready")
    if not ai_release_gate_passed: reasons.append("ai_release_gate_failed")
    if not security_audit_passed: reasons.append("security_audit_failed")
    if not tenant_export_verified: reasons.append("tenant_export_unverified")
    if not tenant_deletion_verified: reasons.append("tenant_deletion_unverified")
    if not rollback_verified: reasons.append("rollback_unverified")
    if open_sev1_or_sev2: reasons.append("severe_incidents_open")
    if unresolved_critical_or_high_findings: reasons.append("high_risk_findings_open")
    return {"launch_ready": not reasons, "reason_codes": reasons or ["production_launch_ready"], "required_approvals": sorted(REQUIRED_APPROVALS), "policy_version": LAUNCH_POLICY_VERSION}
