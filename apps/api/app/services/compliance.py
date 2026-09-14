from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlparse

COMPLIANCE_POLICY_VERSION = "compliance-v1"
SUPPORTED_FRAMEWORKS = {"ISO27001", "SOC2", "GDPR", "UAE_PDPL", "NIST_CSF"}

@dataclass(frozen=True)
class EvidenceInput:
    uri: str
    sha256: str
    classification: str
    retention_days: int
    verified: bool

def validate_evidence(value: EvidenceInput) -> dict[str, object]:
    reasons: list[str] = []
    parsed = urlparse(value.uri)
    if parsed.scheme not in {"https", "s3", "gs", "azure"} or not (parsed.netloc or parsed.path):
        reasons.append("unsafe_evidence_uri")
    if len(value.sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value.sha256):
        reasons.append("invalid_evidence_fingerprint")
    if value.classification not in {"public", "internal", "confidential", "restricted"}:
        reasons.append("invalid_classification")
    if not 1 <= value.retention_days <= 3650:
        reasons.append("invalid_retention_period")
    return {"valid": not reasons, "reason_codes": reasons or ["evidence_valid"], "policy_version": COMPLIANCE_POLICY_VERSION}

def evaluate_control(*, framework_code: str, implemented: bool, independently_tested: bool, evidence_verified: bool, owner_assigned: bool, exception_approved: bool = False) -> dict[str, object]:
    reasons: list[str] = []
    if framework_code not in SUPPORTED_FRAMEWORKS:
        reasons.append("unsupported_framework")
    if not owner_assigned:
        reasons.append("control_owner_required")
    if not implemented and not exception_approved:
        reasons.append("control_not_implemented")
    if implemented and not independently_tested:
        reasons.append("independent_test_required")
    if implemented and not evidence_verified:
        reasons.append("verified_evidence_required")
    return {"control_effective": not reasons, "reason_codes": reasons or ["control_effective"], "policy_version": COMPLIANCE_POLICY_VERSION}

def evaluate_risk(*, likelihood: int, impact: int, treatment_plan_present: bool, owner_assigned: bool, accepted_by_authority: bool) -> dict[str, object]:
    if likelihood not in range(1, 6) or impact not in range(1, 6):
        raise ValueError("likelihood and impact must be between 1 and 5")
    score = likelihood * impact
    reasons: list[str] = []
    if not owner_assigned:
        reasons.append("risk_owner_required")
    if score >= 12 and not treatment_plan_present and not accepted_by_authority:
        reasons.append("high_risk_treatment_required")
    if score >= 20 and accepted_by_authority:
        reasons.append("critical_risk_cannot_be_silently_accepted")
    return {"acceptable": not reasons, "score": score, "reason_codes": reasons or ["risk_governed"], "policy_version": COMPLIANCE_POLICY_VERSION}

def evaluate_disaster_recovery(*, rpo_minutes: int, rto_minutes: int, encrypted_backups: bool, restore_test_passed: bool, rollback_test_passed: bool, evidence_verified: bool, multi_region_required: bool, multi_region_ready: bool) -> dict[str, object]:
    reasons: list[str] = []
    if rpo_minutes < 0 or rto_minutes <= 0:
        reasons.append("invalid_recovery_objectives")
    if not encrypted_backups:
        reasons.append("encrypted_backups_required")
    if not restore_test_passed:
        reasons.append("restore_test_required")
    if not rollback_test_passed:
        reasons.append("rollback_test_required")
    if not evidence_verified:
        reasons.append("verified_recovery_evidence_required")
    if multi_region_required and not multi_region_ready:
        reasons.append("multi_region_readiness_required")
    return {"recovery_ready": not reasons, "reason_codes": reasons or ["disaster_recovery_ready"], "policy_version": COMPLIANCE_POLICY_VERSION}

def evaluate_enterprise_readiness(*, control_failures: int, open_high_risks: int, overdue_evidence: int, disaster_recovery_ready: bool, data_export_tested: bool, data_deletion_tested: bool, key_rotation_verified: bool, secret_rotation_verified: bool) -> dict[str, object]:
    reasons: list[str] = []
    if control_failures: reasons.append("control_failures_open")
    if open_high_risks: reasons.append("high_risks_open")
    if overdue_evidence: reasons.append("compliance_evidence_overdue")
    if not disaster_recovery_ready: reasons.append("disaster_recovery_not_ready")
    if not data_export_tested: reasons.append("data_export_unverified")
    if not data_deletion_tested: reasons.append("data_deletion_unverified")
    if not key_rotation_verified: reasons.append("key_rotation_unverified")
    if not secret_rotation_verified: reasons.append("secret_rotation_unverified")
    return {"enterprise_ready": not reasons, "reason_codes": reasons or ["enterprise_readiness_passed"], "policy_version": COMPLIANCE_POLICY_VERSION}
