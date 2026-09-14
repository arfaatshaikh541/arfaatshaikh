import pytest
from app.services.ummah_services import *
H='a'*64

def test_zakat_fund_passes():
 assert evaluate_zakat_fund(scholarly_policy_approved=True,independent_trustees=3,segregated_accounts=True,audit_frequency_days=90,beneficiary_categories_configured=True,administrative_cost_percent=8,evidence_sha256=H)['allowed']
def test_zakat_fund_requires_scholarly_policy():
 assert 'scholarly_policy_approval_required' in evaluate_zakat_fund(scholarly_policy_approved=False,independent_trustees=3,segregated_accounts=True,audit_frequency_days=90,beneficiary_categories_configured=True,administrative_cost_percent=8,evidence_sha256=H)['reason_codes']
def test_zakat_fund_caps_admin_cost():
 assert 'administrative_cost_above_policy_limit' in evaluate_zakat_fund(scholarly_policy_approved=True,independent_trustees=3,segregated_accounts=True,audit_frequency_days=90,beneficiary_categories_configured=True,administrative_cost_percent=13,evidence_sha256=H)['reason_codes']
def test_distribution_requires_dual_approval():
 assert 'dual_approval_required' in evaluate_zakat_distribution(eligibility_verified=True,duplicate_checked=True,conflict_screened=True,amount_minor=1000,currency='AED',available_minor=2000,restricted_purpose_respected=True,approval_count=1)['reason_codes']
def test_distribution_blocks_overspend():
 assert 'insufficient_restricted_balance' in evaluate_zakat_distribution(eligibility_verified=True,duplicate_checked=True,conflict_screened=True,amount_minor=3000,currency='AED',available_minor=2000,restricted_purpose_respected=True,approval_count=2)['reason_codes']
def test_distribution_passes():
 assert evaluate_zakat_distribution(eligibility_verified=True,duplicate_checked=True,conflict_screened=True,amount_minor=1000,currency='AED',available_minor=2000,restricted_purpose_respected=True,approval_count=2)['allowed']
def test_waqf_requires_perpetual_purpose():
 assert 'perpetual_purpose_required' in evaluate_waqf_asset(ownership_verified=True,perpetual_purpose_declared=False,valuation_current=True,maintenance_plan=True,conflict_of_interest_cleared=True,asset_sha256=H)['reason_codes']
def test_waqf_passes():
 assert evaluate_waqf_asset(ownership_verified=True,perpetual_purpose_declared=True,valuation_current=True,maintenance_plan=True,conflict_of_interest_cleared=True,asset_sha256=H)['allowed']
def test_aid_fingerprint_is_deterministic():
 a=compute_aid_case_fingerprint(case_reference='A-1',need_categories=['food','shelter'],region_code='AE',evidence_fingerprints=[H,'b'*64])
 b=compute_aid_case_fingerprint(case_reference='A-1',need_categories=['shelter','food'],region_code='AE',evidence_fingerprints=['b'*64,H])
 assert a==b
def test_aid_fingerprint_rejects_bad_region():
 with pytest.raises(ValueError):compute_aid_case_fingerprint(case_reference='A-1',need_categories=['food'],region_code='UAE',evidence_fingerprints=[H])
def test_beneficiary_case_requires_minimization():
 assert 'identity_minimization_required' in evaluate_beneficiary_case(identity_minimized=False,consent_or_lawful_basis=True,need_assessment_complete=True,safeguarding_screened=True,duplicate_risk_percent=5,case_fingerprint=H,retention_days=365)['reason_codes']
def test_beneficiary_case_blocks_high_duplicate_risk():
 assert 'duplicate_assistance_risk_too_high' in evaluate_beneficiary_case(identity_minimized=True,consent_or_lawful_basis=True,need_assessment_complete=True,safeguarding_screened=True,duplicate_risk_percent=30,case_fingerprint=H,retention_days=365)['reason_codes']
def test_beneficiary_case_passes():
 assert evaluate_beneficiary_case(identity_minimized=True,consent_or_lawful_basis=True,need_assessment_complete=True,safeguarding_screened=True,duplicate_risk_percent=5,case_fingerprint=H,retention_days=365)['allowed']
def test_aid_program_requires_complaints_channel():
 assert 'beneficiary_complaints_channel_required' in evaluate_aid_program(verified_partner_count=1,restricted_funds_segregated=True,monitoring_plan=True,complaints_channel=False,anti_exploitation_controls=True,open_critical_findings=0,programme_evidence_sha256=H)['reason_codes']
def test_aid_program_blocks_critical_findings():
 assert 'critical_findings_unresolved' in evaluate_aid_program(verified_partner_count=1,restricted_funds_segregated=True,monitoring_plan=True,complaints_channel=True,anti_exploitation_controls=True,open_critical_findings=1,programme_evidence_sha256=H)['reason_codes']
def test_aid_program_passes():
 assert evaluate_aid_program(verified_partner_count=1,restricted_funds_segregated=True,monitoring_plan=True,complaints_channel=True,anti_exploitation_controls=True,open_critical_findings=0,programme_evidence_sha256=H)['allowed']
def test_mosque_service_requires_verified_institution():
 assert 'verified_institution_required' in evaluate_mosque_service(verified_institution=False,service_type='education',qualified_lead=True,accessibility_supported=True,child_safeguarding_required=True,child_safeguarding_passed=True,privacy_notice_published=True,complaints_process=True)['reason_codes']
def test_mosque_service_requires_child_safeguarding():
 assert 'child_safeguarding_required' in evaluate_mosque_service(verified_institution=True,service_type='education',qualified_lead=True,accessibility_supported=True,child_safeguarding_required=True,child_safeguarding_passed=False,privacy_notice_published=True,complaints_process=True)['reason_codes']
def test_mosque_service_passes():
 assert evaluate_mosque_service(verified_institution=True,service_type='education',qualified_lead=True,accessibility_supported=True,child_safeguarding_required=True,child_safeguarding_passed=True,privacy_notice_published=True,complaints_process=True)['allowed']
def test_volunteer_requires_background_check_when_needed():
 assert 'background_check_required' in evaluate_volunteer_assignment(identity_verified=True,role_training_complete=True,background_check_required=True,background_check_passed=False,conflict_disclosed=True,maximum_weekly_hours=10,safeguarding_code_accepted=True)['reason_codes']
def test_volunteer_caps_hours():
 assert 'volunteer_hours_out_of_bounds' in evaluate_volunteer_assignment(identity_verified=True,role_training_complete=True,background_check_required=False,background_check_passed=False,conflict_disclosed=True,maximum_weekly_hours=60,safeguarding_code_accepted=True)['reason_codes']
def test_volunteer_passes():
 assert evaluate_volunteer_assignment(identity_verified=True,role_training_complete=True,background_check_required=True,background_check_passed=True,conflict_disclosed=True,maximum_weekly_hours=10,safeguarding_code_accepted=True)['allowed']
def test_referral_requires_consent():
 assert 'referral_consent_required' in evaluate_service_referral(consent_captured=False,minimum_data_shared=True,receiving_provider_verified=True,urgent_risk=False,urgent_escalation_available=False,referral_evidence_sha256=H)['reason_codes']
def test_urgent_referral_requires_escalation_path():
 assert 'urgent_escalation_path_required' in evaluate_service_referral(consent_captured=True,minimum_data_shared=True,receiving_provider_verified=True,urgent_risk=True,urgent_escalation_available=False,referral_evidence_sha256=H)['reason_codes']
def test_referral_passes():
 assert evaluate_service_referral(consent_captured=True,minimum_data_shared=True,receiving_provider_verified=True,urgent_risk=True,urgent_escalation_available=True,referral_evidence_sha256=H)['allowed']
def test_crisis_requires_incident_command():
 assert 'incident_command_required' in evaluate_crisis_response(incident_command_assigned=False,verified_partner_count=1,beneficiary_safeguarding=True,stock_or_capacity_verified=True,communications_verified=True,financial_controls_active=True,open_critical_blockers=0)['reason_codes']
def test_crisis_blocks_critical_blockers():
 assert 'critical_blockers_unresolved' in evaluate_crisis_response(incident_command_assigned=True,verified_partner_count=1,beneficiary_safeguarding=True,stock_or_capacity_verified=True,communications_verified=True,financial_controls_active=True,open_critical_blockers=1)['reason_codes']
def test_crisis_passes():
 assert evaluate_crisis_response(incident_command_assigned=True,verified_partner_count=1,beneficiary_safeguarding=True,stock_or_capacity_verified=True,communications_verified=True,financial_controls_active=True,open_critical_blockers=0)['allowed']
def test_analytics_requires_location_reduction():
 assert 'location_precision_reduction_required' in evaluate_public_service_analytics(k_anonymity=5,minimum_group_size=20,location_precision_reduced=False,personal_data_removed=True,beneficiary_consent_or_basis=True,bias_reviewed=True,publication_sha256=H)['reason_codes']
def test_analytics_passes():
 assert evaluate_public_service_analytics(k_anonymity=5,minimum_group_size=20,location_precision_reduced=True,personal_data_removed=True,beneficiary_consent_or_basis=True,bias_reviewed=True,publication_sha256=H)['allowed']
def test_acceptance_fails_missing_control():
 r=evaluate_ummah_services_acceptance(zakat_waqf_governance_passed=False,humanitarian_safeguarding_passed=True,mosque_services_passed=True,crisis_readiness_passed=True,privacy_analytics_passed=True,live_disbursement_validated=False,external_fiduciary_audit=False,live_crisis_exercise=False); assert r['outcome']=='failed'
def test_acceptance_conditional_without_live_validation():
 r=evaluate_ummah_services_acceptance(zakat_waqf_governance_passed=True,humanitarian_safeguarding_passed=True,mosque_services_passed=True,crisis_readiness_passed=True,privacy_analytics_passed=True,live_disbursement_validated=False,external_fiduciary_audit=False,live_crisis_exercise=False); assert r['outcome']=='conditional' and r['portable_ready'] and not r['production_ready']
def test_acceptance_passes_production_gate():
 r=evaluate_ummah_services_acceptance(zakat_waqf_governance_passed=True,humanitarian_safeguarding_passed=True,mosque_services_passed=True,crisis_readiness_passed=True,privacy_analytics_passed=True,live_disbursement_validated=True,external_fiduciary_audit=True,live_crisis_exercise=True); assert r['outcome']=='passed' and r['production_ready']
