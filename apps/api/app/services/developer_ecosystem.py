from __future__ import annotations

import re
from urllib.parse import urlparse

from app.services.developer_platform import ALLOWED_SCOPES

DEVELOPER_ECOSYSTEM_POLICY_VERSION = "developer-ecosystem-v1"
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$")
API_VERSION_RE = re.compile(r"^v[1-9]\d*$")


def _https_public_uri(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None and parsed.password is None and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}


def evaluate_api_version(*, version: str, lifecycle_status: str, specification_sha256: str, breaking_changes: list[str], sunset_notice_days: int, successor_version: str | None) -> dict[str, object]:
    reasons: list[str] = []
    if not API_VERSION_RE.fullmatch(version): reasons.append("invalid_api_version")
    if lifecycle_status not in {"preview", "current", "deprecated", "retired"}: reasons.append("invalid_lifecycle_status")
    if not SHA256_RE.fullmatch(specification_sha256): reasons.append("invalid_specification_fingerprint")
    if sunset_notice_days < 0: reasons.append("invalid_sunset_notice")
    if lifecycle_status in {"deprecated", "retired"} and sunset_notice_days < 90: reasons.append("minimum_sunset_notice_required")
    if breaking_changes and lifecycle_status == "current": reasons.append("breaking_changes_require_new_version")
    if lifecycle_status in {"deprecated", "retired"} and (not successor_version or not API_VERSION_RE.fullmatch(successor_version)): reasons.append("successor_version_required")
    return {"valid": not reasons, "reason_codes": reasons or ["api_version_valid"], "policy_version": DEVELOPER_ECOSYSTEM_POLICY_VERSION}


def validate_documentation_artifact(*, artifact_type: str, locale: str, content_uri: str, content_sha256: str, verified: bool) -> dict[str, object]:
    reasons: list[str] = []
    if artifact_type not in {"openapi", "guide", "example", "changelog"}: reasons.append("unsupported_artifact_type")
    if not re.fullmatch(r"[a-z]{2}(?:-[A-Z]{2})?", locale): reasons.append("invalid_locale")
    if not _https_public_uri(content_uri): reasons.append("public_https_content_uri_required")
    if not SHA256_RE.fullmatch(content_sha256): reasons.append("invalid_content_fingerprint")
    if not verified: reasons.append("documentation_verification_required")
    return {"valid": not reasons, "reason_codes": reasons or ["documentation_artifact_valid"], "policy_version": DEVELOPER_ECOSYSTEM_POLICY_VERSION}


def evaluate_sdk_release(*, language: str, version: str, package_uri: str, package_sha256: str, tests_passed: bool, provenance_verified: bool, api_version_status: str) -> dict[str, object]:
    reasons: list[str] = []
    if language not in {"python", "typescript", "java", "dotnet"}: reasons.append("unsupported_sdk_language")
    if not SEMVER_RE.fullmatch(version): reasons.append("invalid_sdk_semver")
    if not _https_public_uri(package_uri): reasons.append("public_https_package_uri_required")
    if not SHA256_RE.fullmatch(package_sha256): reasons.append("invalid_package_fingerprint")
    if not tests_passed: reasons.append("sdk_tests_required")
    if not provenance_verified: reasons.append("sdk_provenance_required")
    if api_version_status not in {"preview", "current"}: reasons.append("api_version_not_publishable")
    return {"publishable": not reasons, "reason_codes": reasons or ["sdk_release_publishable"], "policy_version": DEVELOPER_ECOSYSTEM_POLICY_VERSION}


def evaluate_sandbox_session(*, application_status: str, requested_scopes: set[str], request_limit: int, used_requests: int, expired: bool) -> dict[str, object]:
    reasons: list[str] = []
    if application_status not in {"draft", "active"}: reasons.append("application_not_sandbox_eligible")
    unknown = sorted(requested_scopes - ALLOWED_SCOPES)
    if unknown: reasons.append("unknown_scope_requested")
    if "assistant.request" in requested_scopes: reasons.append("assistant_scope_not_available_in_sandbox")
    if not 1 <= request_limit <= 1000: reasons.append("sandbox_limit_out_of_bounds")
    if used_requests < 0 or used_requests >= request_limit: reasons.append("sandbox_quota_exhausted")
    if expired: reasons.append("sandbox_expired")
    return {"allowed": not reasons, "remaining": max(request_limit - max(used_requests, 0), 0), "reason_codes": reasons or ["sandbox_session_allowed"], "policy_version": DEVELOPER_ECOSYSTEM_POLICY_VERSION}
