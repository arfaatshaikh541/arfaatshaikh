import app.models  # noqa: F401
from app.db.base import Base
from app.services.developer_partners import evaluate_certification, evaluate_integration_listing, evaluate_partner_application, evaluate_partner_incident, evaluate_security_review


def test_partner_governance_tables_registered():
    assert {"developer_partners", "integration_listings", "integration_security_reviews", "integration_certifications", "partner_security_incidents"}.issubset(Base.metadata.tables)


def test_partner_application_requires_public_site_contact_and_terms():
    good = evaluate_partner_application(website_url="https://partner.example.com", privacy_contact="privacy@example.com", terms_accepted=True, organisation_active=True)
    bad = evaluate_partner_application(website_url="http://localhost", privacy_contact="bad", terms_accepted=False, organisation_active=False)
    assert good["verified"] is True
    assert bad["verified"] is False


def test_listing_requires_verified_partner_active_application_and_governed_scope():
    good = evaluate_integration_listing(slug="trusted-reader", partner_status="verified", application_status="active", requested_scopes={"quran.read"}, support_url="https://support.example.com", security_review_passed=True, certification_active=True)
    bad = evaluate_integration_listing(slug="Bad Slug", partner_status="applicant", application_status="draft", requested_scopes={"unknown"}, support_url="http://localhost", security_review_passed=False, certification_active=False)
    assert good["publishable"] is True
    assert bad["publishable"] is False


def test_listing_blocks_assistant_scope_without_separate_approval():
    result = evaluate_integration_listing(slug="assistant-tool", partner_status="verified", application_status="active", requested_scopes={"assistant.request"}, support_url="https://support.example.com", security_review_passed=True, certification_active=True)
    assert result["publishable"] is False
    assert "assistant_scope_requires_separate_approval" in result["reason_codes"]


def test_security_review_requires_independence_privacy_and_zero_high_risk_findings():
    good = evaluate_security_review(evidence_sha256="a"*64, critical_findings=0, high_findings=0, data_minimisation_verified=True, deletion_verified=True, independent_reviewer=True)
    bad = evaluate_security_review(evidence_sha256="bad", critical_findings=1, high_findings=2, data_minimisation_verified=False, deletion_verified=False, independent_reviewer=False)
    assert good["passed"] is True
    assert bad["passed"] is False


def test_certification_is_bounded_and_evidence_backed():
    good = evaluate_certification(certificate_version="cert-v1", certification_sha256="b"*64, security_review_passed=True, expires_in_days=365, partner_status="verified")
    bad = evaluate_certification(certificate_version="v1", certification_sha256="bad", security_review_passed=False, expires_in_days=500, partner_status="suspended")
    assert good["certifiable"] is True
    assert bad["certifiable"] is False


def test_high_open_incident_requires_credential_revocation():
    result = evaluate_partner_incident(severity="high", status="open", credentials_revoked=False, listing_suspended=False, evidence_sha256="c"*64)
    assert result["contained"] is False
    assert "credential_revocation_required" in result["reason_codes"]


def test_critical_unresolved_incident_requires_listing_suspension():
    result = evaluate_partner_incident(severity="critical", status="contained", credentials_revoked=True, listing_suspended=False, evidence_sha256="d"*64)
    assert result["contained"] is False
    assert "listing_suspension_required" in result["reason_codes"]
