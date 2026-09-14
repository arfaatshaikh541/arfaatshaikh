import pytest
from app.services.institutional_network import (
 evaluate_institution_registration,evaluate_accreditation,evaluate_portal_publication,evaluate_data_residency,evaluate_localization_release,evaluate_public_transparency,evaluate_correction_release,compute_transparency_fingerprint,evaluate_regional_rollout,evaluate_global_acceptance)
H="a"*64

def test_institution_registration_passes_verified_public_entity():
 r=evaluate_institution_registration(institution_type="university",legal_name="Global Islamic University",country_code="AE",website_url="https://example.org",verification_evidence_sha256=H,independent_verifier=True,organisation_active=True); assert r["allowed"] and r["status"]=="verified"
def test_institution_registration_blocks_private_or_unverified_entity():
 r=evaluate_institution_registration(institution_type="unknown",legal_name="x",country_code="ua",website_url="http://localhost",verification_evidence_sha256="x",independent_verifier=False,organisation_active=False); assert not r["allowed"] and len(r["reason_codes"])>=5
def test_institution_registration_rejects_private_ip():
 assert not evaluate_institution_registration(institution_type="mosque",legal_name="Central Mosque",country_code="AE",website_url="https://127.0.0.1",verification_evidence_sha256=H,independent_verifier=True,organisation_active=True)["allowed"]
def test_institution_types_are_allowlisted():
 assert "unsupported_institution_type" in evaluate_institution_registration(institution_type="casino",legal_name="Invalid Entity",country_code="AE",website_url="https://example.org",verification_evidence_sha256=H,independent_verifier=True,organisation_active=True)["reason_codes"]
def test_accreditation_requires_verified_institution():
 assert not evaluate_accreditation(institution_status="applicant",accreditation_type="research_partner",evidence_sha256=H,expires_in_days=365,reviewer_is_independent=True,open_critical_findings=0,scholarly_board_approved=True)["allowed"]
def test_scholarly_authority_requires_board():
 r=evaluate_accreditation(institution_status="verified",accreditation_type="scholarly_authority",evidence_sha256=H,expires_in_days=365,reviewer_is_independent=True,open_critical_findings=0,scholarly_board_approved=False); assert "scholarly_board_approval_required" in r["reason_codes"]
def test_accreditation_expiry_is_bounded():
 assert not evaluate_accreditation(institution_status="verified",accreditation_type="research_partner",evidence_sha256=H,expires_in_days=731,reviewer_is_independent=True,open_critical_findings=0,scholarly_board_approved=True)["allowed"]
def test_accreditation_rejects_critical_findings():
 assert not evaluate_accreditation(institution_status="verified",accreditation_type="research_partner",evidence_sha256=H,expires_in_days=365,reviewer_is_independent=True,open_critical_findings=1,scholarly_board_approved=True)["allowed"]
def test_portal_requires_evidence_mode_for_sensitive_content():
 r=evaluate_portal_publication(institution_status="verified",accreditation_active=True,locale="ar-AE",domain_url="https://portal.example.org",content_types={"quran"},evidence_only=False,accessibility_reviewed=True,child_safe_defaults=True); assert not r["allowed"]
def test_portal_passes_governed_publication():
 assert evaluate_portal_publication(institution_status="verified",accreditation_active=True,locale="en-AE",domain_url="https://portal.example.org",content_types={"course"},evidence_only=True,accessibility_reviewed=True,child_safe_defaults=True)["allowed"]
def test_portal_requires_accessibility_review():
 assert not evaluate_portal_publication(institution_status="verified",accreditation_active=True,locale="en-AE",domain_url="https://portal.example.org",content_types={"course"},evidence_only=True,accessibility_reviewed=False,child_safe_defaults=True)["allowed"]
def test_portal_requires_child_safe_defaults():
 assert not evaluate_portal_publication(institution_status="verified",accreditation_active=True,locale="en-AE",domain_url="https://portal.example.org",content_types={"course"},evidence_only=True,accessibility_reviewed=True,child_safe_defaults=False)["allowed"]
def test_residency_passes_regional_boundary():
 assert evaluate_data_residency(region="uae",storage_regions={"uae"},processing_regions={"uae"},cross_border_transfer=False,transfer_basis=None,encryption_at_rest=True,encryption_in_transit=True,personal_data_involved=True)["allowed"]
def test_residency_blocks_boundary_violation():
 r=evaluate_data_residency(region="uae",storage_regions={"eu"},processing_regions={"uae"},cross_border_transfer=False,transfer_basis=None,encryption_at_rest=True,encryption_in_transit=True,personal_data_involved=True); assert "regional_boundary_violation" in r["reason_codes"]
def test_cross_border_personal_data_requires_basis():
 assert not evaluate_data_residency(region="eu",storage_regions={"eu","uk"},processing_regions={"eu"},cross_border_transfer=True,transfer_basis=None,encryption_at_rest=True,encryption_in_transit=True,personal_data_involved=True)["allowed"]
def test_residency_requires_encryption():
 assert not evaluate_data_residency(region="uae",storage_regions={"uae"},processing_regions={"uae"},cross_border_transfer=False,transfer_basis=None,encryption_at_rest=False,encryption_in_transit=False,personal_data_involved=False)["allowed"]
def test_localization_requires_high_alignment():
 assert not evaluate_localization_release(locale="ur",source_sha256=H,translation_sha256="b"*64,semantic_alignment_score=89,native_reviewer=True,scholarly_reviewed=True,content_type="course",machine_generated=False)["allowed"]
def test_sensitive_localization_forbids_machine_only_release():
 r=evaluate_localization_release(locale="ur",source_sha256=H,translation_sha256="b"*64,semantic_alignment_score=98,native_reviewer=True,scholarly_reviewed=True,content_type="quran",machine_generated=True); assert "machine_only_sensitive_translation_forbidden" in r["reason_codes"]
def test_sensitive_localization_requires_scholar():
 assert not evaluate_localization_release(locale="ur",source_sha256=H,translation_sha256="b"*64,semantic_alignment_score=98,native_reviewer=True,scholarly_reviewed=False,content_type="hadith",machine_generated=False)["allowed"]
def test_localization_passes_human_reviewed_release():
 assert evaluate_localization_release(locale="ur",source_sha256=H,translation_sha256="b"*64,semantic_alignment_score=98,native_reviewer=True,scholarly_reviewed=True,content_type="tafsir",machine_generated=False)["allowed"]
def test_transparency_requires_95_percent_coverage():
 assert not evaluate_public_transparency(source_coverage_percent=94,correction_sla_hours=24,public_methodology=True,public_change_log=True,public_contact=True,unresolved_high_risk_claims=0)["allowed"]
def test_transparency_passes_complete_controls():
 r=evaluate_public_transparency(source_coverage_percent=99,correction_sla_hours=24,public_methodology=True,public_change_log=True,public_contact=True,unresolved_high_risk_claims=0); assert r["allowed"] and r["trust_tier"]=="high"
def test_transparency_blocks_unresolved_high_risk_claims():
 assert not evaluate_public_transparency(source_coverage_percent=99,correction_sla_hours=24,public_methodology=True,public_change_log=True,public_contact=True,unresolved_high_risk_claims=1)["allowed"]
def test_transparency_sla_is_bounded():
 assert not evaluate_public_transparency(source_coverage_percent=99,correction_sla_hours=169,public_methodology=True,public_change_log=True,public_contact=True,unresolved_high_risk_claims=0)["allowed"]
def test_high_correction_requires_independent_review_and_notice():
 r=evaluate_correction_release(severity="high",evidence_sha256=H,affected_content_types={"research"},reviewer_is_author=True,scholarly_approval=True,user_notification_planned=False,rollback_defined=True); assert not r["allowed"]
def test_sensitive_correction_requires_scholarly_approval():
 r=evaluate_correction_release(severity="medium",evidence_sha256=H,affected_content_types={"fiqh"},reviewer_is_author=False,scholarly_approval=False,user_notification_planned=True,rollback_defined=True); assert "scholarly_approval_required" in r["reason_codes"]
def test_correction_requires_rollback():
 assert not evaluate_correction_release(severity="low",evidence_sha256=H,affected_content_types={"course"},reviewer_is_author=False,scholarly_approval=True,user_notification_planned=True,rollback_defined=False)["allowed"]
def test_transparency_fingerprint_is_deterministic():
 a=compute_transparency_fingerprint(institution_slug="uni",report_version="v1",metrics={"b":2,"a":1},evidence_sha256=H); b=compute_transparency_fingerprint(institution_slug="uni",report_version="v1",metrics={"a":1,"b":2},evidence_sha256=H); assert a==b and len(a)==64
def test_regional_rollout_distinguishes_portable_and_production():
 p=evaluate_regional_rollout(region="uae",institutions_verified=1,localization_complete=True,data_residency_passed=True,support_coverage=True,incident_drill_passed=True,live_traffic_tested=False); x=evaluate_regional_rollout(region="uae",institutions_verified=1,localization_complete=True,data_residency_passed=True,support_coverage=True,incident_drill_passed=True,live_traffic_tested=True); assert p["outcome"]=="conditional" and x["outcome"]=="passed"
def test_regional_rollout_fails_missing_controls():
 assert evaluate_regional_rollout(region="uae",institutions_verified=0,localization_complete=False,data_residency_passed=False,support_coverage=False,incident_drill_passed=False,live_traffic_tested=False)["outcome"]=="failed"
def test_global_acceptance_requires_live_regions_and_external_review():
 regional=[{"outcome":"conditional","production_ready":False}]; r=evaluate_global_acceptance(regional_reviews=regional,open_critical_incidents=0,audit_chain_verified=True,disaster_recovery_passed=True,scholarly_governance_passed=True,external_security_reviewed=False); assert r["outcome"]=="conditional" and not r["production_ready"]
def test_global_acceptance_passes_all_gates():
 regional=[{"outcome":"passed","production_ready":True}]; r=evaluate_global_acceptance(regional_reviews=regional,open_critical_incidents=0,audit_chain_verified=True,disaster_recovery_passed=True,scholarly_governance_passed=True,external_security_reviewed=True); assert r["outcome"]=="passed" and r["production_ready"]
def test_global_acceptance_fails_critical_incident():
 regional=[{"outcome":"passed","production_ready":True}]; assert evaluate_global_acceptance(regional_reviews=regional,open_critical_incidents=1,audit_chain_verified=True,disaster_recovery_passed=True,scholarly_governance_passed=True,external_security_reviewed=True)["outcome"]=="failed"
