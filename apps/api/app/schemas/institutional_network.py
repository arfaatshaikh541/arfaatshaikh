from __future__ import annotations
from pydantic import BaseModel, Field

class InstitutionRegistrationRequest(BaseModel):
    institution_type: str
    legal_name: str
    country_code: str
    website_url: str
    verification_evidence_sha256: str
    independent_verifier: bool
    organisation_active: bool

class AccreditationRequest(BaseModel):
    institution_status: str
    accreditation_type: str
    evidence_sha256: str
    expires_in_days: int
    reviewer_is_independent: bool
    open_critical_findings: int = Field(ge=0)
    scholarly_board_approved: bool

class PortalPublicationRequest(BaseModel):
    institution_status: str
    accreditation_active: bool
    locale: str
    domain_url: str
    content_types: set[str]
    evidence_only: bool
    accessibility_reviewed: bool
    child_safe_defaults: bool

class DataResidencyRequest(BaseModel):
    region: str
    storage_regions: set[str]
    processing_regions: set[str]
    cross_border_transfer: bool
    transfer_basis: str | None = None
    encryption_at_rest: bool
    encryption_in_transit: bool
    personal_data_involved: bool

class LocalizationReleaseRequest(BaseModel):
    locale: str
    source_sha256: str
    translation_sha256: str
    semantic_alignment_score: int = Field(ge=0, le=100)
    native_reviewer: bool
    scholarly_reviewed: bool
    content_type: str
    machine_generated: bool

class PublicTransparencyRequest(BaseModel):
    source_coverage_percent: int = Field(ge=0, le=100)
    correction_sla_hours: int
    public_methodology: bool
    public_change_log: bool
    public_contact: bool
    unresolved_high_risk_claims: int = Field(ge=0)

class CorrectionReleaseRequest(BaseModel):
    severity: str
    evidence_sha256: str
    affected_content_types: set[str]
    reviewer_is_author: bool
    scholarly_approval: bool
    user_notification_planned: bool
    rollback_defined: bool

class TransparencyFingerprintRequest(BaseModel):
    institution_slug: str
    report_version: str
    metrics: dict[str, int]
    evidence_sha256: str

class RegionalRolloutRequest(BaseModel):
    region: str
    institutions_verified: int = Field(ge=0)
    localization_complete: bool
    data_residency_passed: bool
    support_coverage: bool
    incident_drill_passed: bool
    live_traffic_tested: bool

class GlobalAcceptanceRequest(BaseModel):
    regional_reviews: list[dict[str, object]]
    open_critical_incidents: int = Field(ge=0)
    audit_chain_verified: bool
    disaster_recovery_passed: bool
    scholarly_governance_passed: bool
    external_security_reviewed: bool
