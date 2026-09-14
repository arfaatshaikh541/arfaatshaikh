from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.services.developer_platform import ALLOWED_SCOPES

DEVELOPER_ACCESS_POLICY_VERSION = "developer-access-v1"


@dataclass(frozen=True)
class AccessRequest:
    application_status: str
    credential_status: str
    granted_scopes: set[str]
    required_scope: str
    tenant_matches: bool
    credential_expired: bool
    rate_limit_remaining: int


def evaluate_api_access(value: AccessRequest) -> dict[str, object]:
    reasons: list[str] = []
    if value.application_status != "active":
        reasons.append("application_not_active")
    if value.credential_status != "active":
        reasons.append("credential_not_active")
    if value.credential_expired:
        reasons.append("credential_expired")
    if not value.tenant_matches:
        reasons.append("tenant_mismatch")
    if value.required_scope not in ALLOWED_SCOPES:
        reasons.append("unknown_required_scope")
    elif value.required_scope not in value.granted_scopes:
        reasons.append("required_scope_missing")
    if value.rate_limit_remaining <= 0:
        reasons.append("quota_exceeded")
    status = 200
    if reasons:
        status = 429 if reasons == ["quota_exceeded"] else 403
    return {
        "allowed": not reasons,
        "response_status_code": status,
        "reason_codes": reasons or ["api_access_allowed"],
        "policy_version": DEVELOPER_ACCESS_POLICY_VERSION,
    }


def evaluate_quota(*, current_count: int, limit_count: int, requested_units: int = 1) -> dict[str, object]:
    if current_count < 0 or limit_count <= 0 or requested_units <= 0:
        raise ValueError("quota values must be positive and current_count cannot be negative")
    projected = current_count + requested_units
    remaining = max(limit_count - projected, 0)
    allowed = projected <= limit_count
    return {
        "allowed": allowed,
        "projected_count": projected,
        "remaining": remaining,
        "reason_codes": ["quota_available"] if allowed else ["quota_exceeded"],
        "policy_version": DEVELOPER_ACCESS_POLICY_VERSION,
    }


def validate_usage_record(*, idempotency_key: str, request_id: str, route_template: str, billable_units: int) -> dict[str, object]:
    reasons: list[str] = []
    if not 12 <= len(idempotency_key) <= 128:
        reasons.append("invalid_idempotency_key")
    if not 8 <= len(request_id) <= 80:
        reasons.append("invalid_request_id")
    if not route_template.startswith("/") or "?" in route_template:
        reasons.append("canonical_route_template_required")
    if not 0 <= billable_units <= 10000:
        reasons.append("billable_units_out_of_bounds")
    fingerprint = hashlib.sha256(f"{idempotency_key}|{request_id}|{route_template}|{billable_units}".encode()).hexdigest()
    return {
        "valid": not reasons,
        "reason_codes": reasons or ["usage_record_valid"],
        "fingerprint": fingerprint,
        "policy_version": DEVELOPER_ACCESS_POLICY_VERSION,
    }


def validate_audit_evidence(*, evidence_sha256: str, event_type: str, summary: str) -> dict[str, object]:
    allowed_events = {"credential.used", "credential.denied", "quota.exceeded", "credential.rotated", "credential.revoked", "scope.changed"}
    reasons: list[str] = []
    if event_type not in allowed_events:
        reasons.append("unsupported_event_type")
    if len(evidence_sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in evidence_sha256):
        reasons.append("valid_evidence_fingerprint_required")
    if not summary.strip() or len(summary) > 1000:
        reasons.append("valid_summary_required")
    return {
        "valid": not reasons,
        "reason_codes": reasons or ["audit_evidence_valid"],
        "policy_version": DEVELOPER_ACCESS_POLICY_VERSION,
    }
