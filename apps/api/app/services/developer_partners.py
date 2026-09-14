from __future__ import annotations

import re
from urllib.parse import urlparse

from app.services.developer_platform import ALLOWED_SCOPES

PARTNER_POLICY_VERSION = "developer-partner-governance-v1"
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CERT_VERSION_RE = re.compile(r"^cert-v[1-9]\d*$")


def _public_https(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None and parsed.password is None and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}


def evaluate_partner_application(*, website_url: str, privacy_contact: str, terms_accepted: bool, organisation_active: bool) -> dict[str, object]:
    reasons: list[str] = []
    if not organisation_active: reasons.append("active_organisation_required")
    if not _public_https(website_url): reasons.append("public_https_website_required")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", privacy_contact): reasons.append("valid_privacy_contact_required")
    if not terms_accepted: reasons.append("partner_terms_acceptance_required")
    return {"verified": not reasons, "reason_codes": reasons or ["partner_application_verified"], "policy_version": PARTNER_POLICY_VERSION}


def evaluate_integration_listing(*, slug: str, partner_status: str, application_status: str, requested_scopes: set[str], support_url: str, security_review_passed: bool, certification_active: bool) -> dict[str, object]:
    reasons: list[str] = []
    if not SLUG_RE.fullmatch(slug): reasons.append("invalid_listing_slug")
    if partner_status != "verified": reasons.append("verified_partner_required")
    if application_status != "active": reasons.append("active_application_required")
    if not requested_scopes: reasons.append("at_least_one_scope_required")
    if requested_scopes - ALLOWED_SCOPES: reasons.append("unknown_scope_requested")
    if "assistant.request" in requested_scopes: reasons.append("assistant_scope_requires_separate_approval")
    if not _public_https(support_url): reasons.append("public_https_support_url_required")
    if not security_review_passed: reasons.append("passed_security_review_required")
    if not certification_active: reasons.append("active_certification_required")
    return {"publishable": not reasons, "reason_codes": reasons or ["integration_listing_publishable"], "policy_version": PARTNER_POLICY_VERSION}


def evaluate_security_review(*, evidence_sha256: str, critical_findings: int, high_findings: int, data_minimisation_verified: bool, deletion_verified: bool, independent_reviewer: bool) -> dict[str, object]:
    if min(critical_findings, high_findings) < 0:
        raise ValueError("finding counts cannot be negative")
    reasons: list[str] = []
    if not SHA256_RE.fullmatch(evidence_sha256): reasons.append("verified_evidence_fingerprint_required")
    if critical_findings: reasons.append("critical_findings_open")
    if high_findings: reasons.append("high_findings_open")
    if not data_minimisation_verified: reasons.append("data_minimisation_verification_required")
    if not deletion_verified: reasons.append("deletion_verification_required")
    if not independent_reviewer: reasons.append("independent_reviewer_required")
    return {"passed": not reasons, "reason_codes": reasons or ["integration_security_review_passed"], "policy_version": PARTNER_POLICY_VERSION}


def evaluate_certification(*, certificate_version: str, certification_sha256: str, security_review_passed: bool, expires_in_days: int, partner_status: str) -> dict[str, object]:
    reasons: list[str] = []
    if not CERT_VERSION_RE.fullmatch(certificate_version): reasons.append("invalid_certificate_version")
    if not SHA256_RE.fullmatch(certification_sha256): reasons.append("invalid_certification_fingerprint")
    if not security_review_passed: reasons.append("security_review_required")
    if not 1 <= expires_in_days <= 365: reasons.append("certification_expiry_out_of_bounds")
    if partner_status != "verified": reasons.append("verified_partner_required")
    return {"certifiable": not reasons, "reason_codes": reasons or ["integration_certifiable"], "policy_version": PARTNER_POLICY_VERSION}


def evaluate_partner_incident(*, severity: str, status: str, credentials_revoked: bool, listing_suspended: bool, evidence_sha256: str) -> dict[str, object]:
    reasons: list[str] = []
    if severity not in {"low", "medium", "high", "critical"}: reasons.append("invalid_incident_severity")
    if status not in {"open", "contained", "resolved"}: reasons.append("invalid_incident_status")
    if not SHA256_RE.fullmatch(evidence_sha256): reasons.append("incident_evidence_required")
    if severity in {"high", "critical"} and status == "open" and not credentials_revoked: reasons.append("credential_revocation_required")
    if severity == "critical" and status != "resolved" and not listing_suspended: reasons.append("listing_suspension_required")
    return {"contained": not reasons, "reason_codes": reasons or ["partner_incident_controls_satisfied"], "policy_version": PARTNER_POLICY_VERSION}
