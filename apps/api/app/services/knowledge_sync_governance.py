from __future__ import annotations

import re

GOVERNANCE_POLICY_VERSION = "knowledge-sync-governance-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SENSITIVE_TYPES = {"quran", "hadith", "tafsir", "fiqh"}
SEVERITIES = {"low", "medium", "high", "critical"}


def evaluate_peer_attestation(*, node_status: str, evidence_sha256: str, independent_reviewer: bool, expires_in_days: int, organisation_active: bool) -> dict[str, object]:
    reasons: list[str] = []
    if node_status != "trusted": reasons.append("trusted_node_required")
    if not organisation_active: reasons.append("active_organisation_required")
    if not SHA256_RE.fullmatch(evidence_sha256): reasons.append("invalid_attestation_evidence")
    if not independent_reviewer: reasons.append("independent_reviewer_required")
    if not 1 <= expires_in_days <= 365: reasons.append("attestation_expiry_out_of_bounds")
    return {"allowed": not reasons, "reason_codes": reasons or ["peer_attestation_allowed"], "policy_version": GOVERNANCE_POLICY_VERSION}


def evaluate_policy_change(*, content_types: set[str], expands_access: bool, requestor_is_approver: bool, change_ticket: str, evidence_sha256: str, rollback_defined: bool) -> dict[str, object]:
    reasons: list[str] = []
    if not content_types: reasons.append("content_types_required")
    if not change_ticket.strip() or len(change_ticket) > 120: reasons.append("valid_change_ticket_required")
    if not SHA256_RE.fullmatch(evidence_sha256): reasons.append("invalid_change_evidence")
    if not rollback_defined: reasons.append("rollback_plan_required")
    sensitive_expansion = expands_access and bool(content_types & SENSITIVE_TYPES)
    if sensitive_expansion and requestor_is_approver: reasons.append("independent_approval_required")
    risk_level = "critical" if sensitive_expansion else "high" if expands_access else "medium"
    return {"allowed": not reasons, "risk_level": risk_level, "reason_codes": reasons or ["policy_change_allowed"], "policy_version": GOVERNANCE_POLICY_VERSION}


def evaluate_security_incident(*, severity: str, status: str, evidence_sha256: str, node_suspended: bool, credentials_revoked: bool, transfers_cancelled: bool) -> dict[str, object]:
    if severity not in SEVERITIES: raise ValueError("invalid severity")
    reasons: list[str] = []
    if status not in {"open", "contained", "resolved", "dismissed"}: reasons.append("invalid_incident_status")
    if not SHA256_RE.fullmatch(evidence_sha256): reasons.append("invalid_incident_evidence")
    if severity in {"high", "critical"} and status in {"open", "contained"}:
        if not node_suspended: reasons.append("node_suspension_required")
        if not credentials_revoked: reasons.append("credential_revocation_required")
        if not transfers_cancelled: reasons.append("transfer_cancellation_required")
    if severity == "critical" and status == "dismissed": reasons.append("critical_incident_cannot_be_dismissed")
    action = "quarantine" if severity in {"high", "critical"} else "monitor"
    return {"contained": not reasons, "required_action": action, "reason_codes": reasons or ["incident_controls_satisfied"], "policy_version": GOVERNANCE_POLICY_VERSION}


def evaluate_quarantine_release(*, incident_status: str, release_evidence_sha256: str, integrity_verification_passed: bool, credentials_rotated: bool, independent_approval: bool, unresolved_drift: int) -> dict[str, object]:
    reasons: list[str] = []
    if incident_status != "resolved": reasons.append("resolved_incident_required")
    if not SHA256_RE.fullmatch(release_evidence_sha256): reasons.append("valid_release_evidence_required")
    if not integrity_verification_passed: reasons.append("integrity_verification_required")
    if not credentials_rotated: reasons.append("credential_rotation_required")
    if not independent_approval: reasons.append("independent_release_approval_required")
    if unresolved_drift != 0: reasons.append("unresolved_drift_blocks_release")
    return {"allowed": not reasons, "reason_codes": reasons or ["quarantine_release_allowed"], "policy_version": GOVERNANCE_POLICY_VERSION}


def evaluate_federation_acceptance(*, open_high_incidents: int, open_critical_incidents: int, integrity_gate_passed: bool, replay_protection_tested: bool, recovery_rehearsal_passed: bool, audit_chain_verified: bool, scholarly_governance_verified: bool, live_network_tested: bool) -> dict[str, object]:
    values = [open_high_incidents, open_critical_incidents]
    if any(value < 0 for value in values): raise ValueError("incident counts cannot be negative")
    reasons: list[str] = []
    if open_high_incidents: reasons.append("open_high_incidents")
    if open_critical_incidents: reasons.append("open_critical_incidents")
    if not integrity_gate_passed: reasons.append("integrity_gate_required")
    if not replay_protection_tested: reasons.append("replay_protection_test_required")
    if not recovery_rehearsal_passed: reasons.append("recovery_rehearsal_required")
    if not audit_chain_verified: reasons.append("audit_chain_verification_required")
    if not scholarly_governance_verified: reasons.append("scholarly_governance_required")
    portable_ready = not reasons
    production_ready = portable_ready and live_network_tested
    if portable_ready and not live_network_tested: reasons = ["live_network_validation_pending"]
    outcome = "passed" if production_ready else "conditional" if portable_ready else "failed"
    return {"outcome": outcome, "portable_ready": portable_ready, "production_ready": production_ready, "reason_codes": reasons or ["federation_acceptance_passed"], "policy_version": GOVERNANCE_POLICY_VERSION}
