from __future__ import annotations

import hashlib
import ipaddress
import re
from urllib.parse import urlparse

POLICY_VERSION = "institutional-network-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
LOCALE_RE = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")
INSTITUTION_TYPES = {"mosque", "university", "madrasa", "publisher", "charity", "research_centre", "scholarly_council"}
SENSITIVE_CONTENT = {"quran", "hadith", "tafsir", "fiqh", "fatwa"}
REGIONS = {"uae", "gcc", "mena", "eu", "uk", "us", "apac", "global"}


def _valid_sha(value: str) -> bool:
    return bool(SHA256_RE.fullmatch(value))


def _public_https(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return False
        host = parsed.hostname.lower().rstrip(".")
        if host == "localhost" or host.endswith(".local"):
            return False
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return True
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)
    except ValueError:
        return False


def evaluate_institution_registration(*, institution_type: str, legal_name: str, country_code: str, website_url: str, verification_evidence_sha256: str, independent_verifier: bool, organisation_active: bool) -> dict[str, object]:
    reasons: list[str] = []
    if institution_type not in INSTITUTION_TYPES: reasons.append("unsupported_institution_type")
    if not 3 <= len(legal_name.strip()) <= 240: reasons.append("valid_legal_name_required")
    if not COUNTRY_RE.fullmatch(country_code): reasons.append("valid_country_code_required")
    if not _public_https(website_url): reasons.append("public_https_website_required")
    if not _valid_sha(verification_evidence_sha256): reasons.append("valid_verification_evidence_required")
    if not independent_verifier: reasons.append("independent_verifier_required")
    if not organisation_active: reasons.append("active_organisation_required")
    return {"allowed": not reasons, "status": "verified" if not reasons else "applicant", "reason_codes": reasons or ["institution_registration_allowed"], "policy_version": POLICY_VERSION}


def evaluate_accreditation(*, institution_status: str, accreditation_type: str, evidence_sha256: str, expires_in_days: int, reviewer_is_independent: bool, open_critical_findings: int, scholarly_board_approved: bool) -> dict[str, object]:
    reasons: list[str] = []
    if institution_status != "verified": reasons.append("verified_institution_required")
    if accreditation_type not in {"content_provider", "education_provider", "research_partner", "scholarly_authority"}: reasons.append("unsupported_accreditation_type")
    if not _valid_sha(evidence_sha256): reasons.append("valid_accreditation_evidence_required")
    if not 1 <= expires_in_days <= 730: reasons.append("accreditation_expiry_out_of_bounds")
    if not reviewer_is_independent: reasons.append("independent_reviewer_required")
    if open_critical_findings < 0: raise ValueError("finding counts cannot be negative")
    if open_critical_findings: reasons.append("open_critical_findings")
    if accreditation_type == "scholarly_authority" and not scholarly_board_approved: reasons.append("scholarly_board_approval_required")
    return {"allowed": not reasons, "status": "active" if not reasons else "pending", "reason_codes": reasons or ["accreditation_allowed"], "policy_version": POLICY_VERSION}


def evaluate_portal_publication(*, institution_status: str, accreditation_active: bool, locale: str, domain_url: str, content_types: set[str], evidence_only: bool, accessibility_reviewed: bool, child_safe_defaults: bool) -> dict[str, object]:
    reasons: list[str] = []
    if institution_status != "verified": reasons.append("verified_institution_required")
    if not accreditation_active: reasons.append("active_accreditation_required")
    if not LOCALE_RE.fullmatch(locale): reasons.append("valid_locale_required")
    if not _public_https(domain_url): reasons.append("public_https_domain_required")
    if not content_types: reasons.append("content_types_required")
    if content_types & SENSITIVE_CONTENT and not evidence_only: reasons.append("sensitive_content_requires_evidence_only_mode")
    if not accessibility_reviewed: reasons.append("accessibility_review_required")
    if not child_safe_defaults: reasons.append("child_safe_defaults_required")
    return {"allowed": not reasons, "reason_codes": reasons or ["portal_publication_allowed"], "policy_version": POLICY_VERSION}


def evaluate_data_residency(*, region: str, storage_regions: set[str], processing_regions: set[str], cross_border_transfer: bool, transfer_basis: str | None, encryption_at_rest: bool, encryption_in_transit: bool, personal_data_involved: bool) -> dict[str, object]:
    reasons: list[str] = []
    if region not in REGIONS: reasons.append("unsupported_region")
    if not storage_regions: reasons.append("storage_region_required")
    if not processing_regions: reasons.append("processing_region_required")
    if not encryption_at_rest: reasons.append("encryption_at_rest_required")
    if not encryption_in_transit: reasons.append("encryption_in_transit_required")
    if personal_data_involved and cross_border_transfer and transfer_basis not in {"adequacy", "contractual_clauses", "explicit_consent", "legal_obligation"}: reasons.append("valid_transfer_basis_required")
    if not cross_border_transfer and region != "global" and (storage_regions - {region} or processing_regions - {region}): reasons.append("regional_boundary_violation")
    return {"allowed": not reasons, "reason_codes": reasons or ["data_residency_policy_allowed"], "policy_version": POLICY_VERSION}


def evaluate_localization_release(*, locale: str, source_sha256: str, translation_sha256: str, semantic_alignment_score: int, native_reviewer: bool, scholarly_reviewed: bool, content_type: str, machine_generated: bool) -> dict[str, object]:
    reasons: list[str] = []
    if not LOCALE_RE.fullmatch(locale): reasons.append("valid_locale_required")
    if not _valid_sha(source_sha256) or not _valid_sha(translation_sha256): reasons.append("valid_translation_fingerprints_required")
    if not 0 <= semantic_alignment_score <= 100: raise ValueError("alignment score must be between 0 and 100")
    if semantic_alignment_score < 90: reasons.append("semantic_alignment_below_threshold")
    if not native_reviewer: reasons.append("native_reviewer_required")
    if content_type in SENSITIVE_CONTENT and not scholarly_reviewed: reasons.append("scholarly_review_required")
    if content_type in SENSITIVE_CONTENT and machine_generated: reasons.append("machine_only_sensitive_translation_forbidden")
    return {"allowed": not reasons, "reason_codes": reasons or ["localization_release_allowed"], "policy_version": POLICY_VERSION}


def evaluate_public_transparency(*, source_coverage_percent: int, correction_sla_hours: int, public_methodology: bool, public_change_log: bool, public_contact: bool, unresolved_high_risk_claims: int) -> dict[str, object]:
    if not 0 <= source_coverage_percent <= 100: raise ValueError("source coverage must be between 0 and 100")
    reasons: list[str] = []
    if source_coverage_percent < 95: reasons.append("source_coverage_below_threshold")
    if not 1 <= correction_sla_hours <= 168: reasons.append("correction_sla_out_of_bounds")
    if not public_methodology: reasons.append("public_methodology_required")
    if not public_change_log: reasons.append("public_change_log_required")
    if not public_contact: reasons.append("public_contact_required")
    if unresolved_high_risk_claims < 0: raise ValueError("claim counts cannot be negative")
    if unresolved_high_risk_claims: reasons.append("unresolved_high_risk_claims")
    return {"allowed": not reasons, "trust_tier": "high" if not reasons else "restricted", "reason_codes": reasons or ["public_transparency_gate_passed"], "policy_version": POLICY_VERSION}


def evaluate_correction_release(*, severity: str, evidence_sha256: str, affected_content_types: set[str], reviewer_is_author: bool, scholarly_approval: bool, user_notification_planned: bool, rollback_defined: bool) -> dict[str, object]:
    reasons: list[str] = []
    if severity not in {"low", "medium", "high", "critical"}: reasons.append("invalid_severity")
    if not _valid_sha(evidence_sha256): reasons.append("valid_correction_evidence_required")
    if not affected_content_types: reasons.append("affected_content_required")
    if severity in {"high", "critical"} and reviewer_is_author: reasons.append("independent_review_required")
    if affected_content_types & SENSITIVE_CONTENT and not scholarly_approval: reasons.append("scholarly_approval_required")
    if severity in {"high", "critical"} and not user_notification_planned: reasons.append("user_notification_required")
    if not rollback_defined: reasons.append("rollback_plan_required")
    return {"allowed": not reasons, "reason_codes": reasons or ["correction_release_allowed"], "policy_version": POLICY_VERSION}


def compute_transparency_fingerprint(*, institution_slug: str, report_version: str, metrics: dict[str, int], evidence_sha256: str) -> str:
    if not institution_slug.strip() or not report_version.strip(): raise ValueError("institution slug and report version are required")
    if not _valid_sha(evidence_sha256): raise ValueError("invalid evidence fingerprint")
    canonical = "|".join([institution_slug.strip().lower(), report_version.strip(), evidence_sha256] + [f"{key}:{metrics[key]}" for key in sorted(metrics)])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evaluate_regional_rollout(*, region: str, institutions_verified: int, localization_complete: bool, data_residency_passed: bool, support_coverage: bool, incident_drill_passed: bool, live_traffic_tested: bool) -> dict[str, object]:
    if institutions_verified < 0: raise ValueError("institution count cannot be negative")
    reasons: list[str] = []
    if region not in REGIONS - {"global"}: reasons.append("specific_supported_region_required")
    if institutions_verified < 1: reasons.append("verified_institution_required")
    if not localization_complete: reasons.append("localization_required")
    if not data_residency_passed: reasons.append("data_residency_gate_required")
    if not support_coverage: reasons.append("regional_support_required")
    if not incident_drill_passed: reasons.append("incident_drill_required")
    portable_ready = not reasons
    production_ready = portable_ready and live_traffic_tested
    outcome = "passed" if production_ready else "conditional" if portable_ready else "failed"
    if portable_ready and not live_traffic_tested: reasons = ["live_traffic_validation_pending"]
    return {"outcome": outcome, "portable_ready": portable_ready, "production_ready": production_ready, "reason_codes": reasons or ["regional_rollout_allowed"], "policy_version": POLICY_VERSION}


def evaluate_global_acceptance(*, regional_reviews: list[dict[str, object]], open_critical_incidents: int, audit_chain_verified: bool, disaster_recovery_passed: bool, scholarly_governance_passed: bool, external_security_reviewed: bool) -> dict[str, object]:
    if open_critical_incidents < 0: raise ValueError("incident count cannot be negative")
    reasons: list[str] = []
    if not regional_reviews: reasons.append("regional_reviews_required")
    failed = [r for r in regional_reviews if r.get("outcome") == "failed"]
    non_production = [r for r in regional_reviews if not r.get("production_ready")]
    if failed: reasons.append("failed_regional_review")
    if open_critical_incidents: reasons.append("open_critical_incidents")
    if not audit_chain_verified: reasons.append("audit_chain_verification_required")
    if not disaster_recovery_passed: reasons.append("disaster_recovery_required")
    if not scholarly_governance_passed: reasons.append("scholarly_governance_required")
    portable_ready = not reasons
    production_ready = portable_ready and not non_production and external_security_reviewed
    if portable_ready and non_production: reasons.append("regional_live_validation_pending")
    if portable_ready and not external_security_reviewed: reasons.append("external_security_review_pending")
    outcome = "passed" if production_ready else "conditional" if portable_ready else "failed"
    return {"outcome": outcome, "portable_ready": portable_ready, "production_ready": production_ready, "reason_codes": reasons or ["global_acceptance_passed"], "policy_version": POLICY_VERSION}
