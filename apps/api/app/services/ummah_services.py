from __future__ import annotations
import hashlib, json, re

POLICY_VERSION='ummah-services-v1'
SHA=re.compile(r'^[0-9a-f]{64}$')


def _sha(value:str)->bool:return bool(SHA.fullmatch(value))
def _result(reasons:list[str],success:str,**extra)->dict:
    return {'allowed':not reasons,'reason_codes':reasons or [success],'policy_version':POLICY_VERSION,**extra}

def evaluate_zakat_fund(*,scholarly_policy_approved:bool,independent_trustees:int,segregated_accounts:bool,audit_frequency_days:int,beneficiary_categories_configured:bool,administrative_cost_percent:int,evidence_sha256:str)->dict:
    if min(independent_trustees,audit_frequency_days,administrative_cost_percent)<0:raise ValueError('values cannot be negative')
    r=[]
    if not scholarly_policy_approved:r.append('scholarly_policy_approval_required')
    if independent_trustees<2:r.append('independent_trustee_threshold_not_met')
    if not segregated_accounts:r.append('segregated_accounts_required')
    if not 1<=audit_frequency_days<=365:r.append('audit_frequency_out_of_bounds')
    if not beneficiary_categories_configured:r.append('eligible_beneficiary_categories_required')
    if administrative_cost_percent>12:r.append('administrative_cost_above_policy_limit')
    if not _sha(evidence_sha256):r.append('valid_evidence_fingerprint_required')
    return _result(r,'zakat_fund_allowed',status='active' if not r else 'restricted')

def evaluate_zakat_distribution(*,eligibility_verified:bool,duplicate_checked:bool,conflict_screened:bool,amount_minor:int,currency:str,available_minor:int,restricted_purpose_respected:bool,approval_count:int)->dict:
    if min(amount_minor,available_minor,approval_count)<0:raise ValueError('values cannot be negative')
    r=[]
    if not eligibility_verified:r.append('beneficiary_eligibility_required')
    if not duplicate_checked:r.append('duplicate_assistance_check_required')
    if not conflict_screened:r.append('conflict_screening_required')
    if amount_minor<=0:r.append('positive_distribution_amount_required')
    if amount_minor>available_minor:r.append('insufficient_restricted_balance')
    if not re.fullmatch(r'[A-Z]{3}',currency):r.append('iso_currency_required')
    if not restricted_purpose_respected:r.append('restricted_purpose_violation')
    if approval_count<2:r.append('dual_approval_required')
    return _result(r,'zakat_distribution_allowed')

def evaluate_waqf_asset(*,ownership_verified:bool,perpetual_purpose_declared:bool,valuation_current:bool,maintenance_plan:bool,conflict_of_interest_cleared:bool,asset_sha256:str)->dict:
    r=[]
    if not ownership_verified:r.append('ownership_verification_required')
    if not perpetual_purpose_declared:r.append('perpetual_purpose_required')
    if not valuation_current:r.append('current_valuation_required')
    if not maintenance_plan:r.append('maintenance_plan_required')
    if not conflict_of_interest_cleared:r.append('conflict_clearance_required')
    if not _sha(asset_sha256):r.append('valid_asset_fingerprint_required')
    return _result(r,'waqf_asset_allowed',status='governed' if not r else 'review')

def compute_aid_case_fingerprint(*,case_reference:str,need_categories:list[str],region_code:str,evidence_fingerprints:list[str])->str:
    if not case_reference.strip():raise ValueError('case reference is required')
    if not re.fullmatch(r'[A-Z]{2}',region_code):raise ValueError('ISO region code required')
    if not need_categories:raise ValueError('at least one need category is required')
    if any(not _sha(v) for v in evidence_fingerprints):raise ValueError('invalid evidence fingerprint')
    canonical=json.dumps({'case_reference':case_reference.strip(),'needs':sorted(set(need_categories)),'region':region_code,'evidence':sorted(set(evidence_fingerprints))},sort_keys=True,separators=(',',':'))
    return hashlib.sha256(canonical.encode()).hexdigest()

def evaluate_beneficiary_case(*,identity_minimized:bool,consent_or_lawful_basis:bool,need_assessment_complete:bool,safeguarding_screened:bool,duplicate_risk_percent:int,case_fingerprint:str,retention_days:int)->dict:
    if min(duplicate_risk_percent,retention_days)<0:raise ValueError('values cannot be negative')
    r=[]
    if not identity_minimized:r.append('identity_minimization_required')
    if not consent_or_lawful_basis:r.append('lawful_processing_basis_required')
    if not need_assessment_complete:r.append('needs_assessment_required')
    if not safeguarding_screened:r.append('safeguarding_screening_required')
    if duplicate_risk_percent>20:r.append('duplicate_assistance_risk_too_high')
    if not _sha(case_fingerprint):r.append('valid_case_fingerprint_required')
    if not 1<=retention_days<=2555:r.append('retention_period_out_of_bounds')
    return _result(r,'beneficiary_case_allowed',status='eligible' if not r else 'review')

def evaluate_aid_program(*,verified_partner_count:int,restricted_funds_segregated:bool,monitoring_plan:bool,complaints_channel:bool,anti_exploitation_controls:bool,open_critical_findings:int,programme_evidence_sha256:str)->dict:
    if min(verified_partner_count,open_critical_findings)<0:raise ValueError('values cannot be negative')
    r=[]
    if verified_partner_count<1:r.append('verified_delivery_partner_required')
    if not restricted_funds_segregated:r.append('restricted_fund_segregation_required')
    if not monitoring_plan:r.append('monitoring_plan_required')
    if not complaints_channel:r.append('beneficiary_complaints_channel_required')
    if not anti_exploitation_controls:r.append('anti_exploitation_controls_required')
    if open_critical_findings:r.append('critical_findings_unresolved')
    if not _sha(programme_evidence_sha256):r.append('valid_programme_evidence_required')
    return _result(r,'aid_program_allowed')

def evaluate_mosque_service(*,verified_institution:bool,service_type:str,qualified_lead:bool,accessibility_supported:bool,child_safeguarding_required:bool,child_safeguarding_passed:bool,privacy_notice_published:bool,complaints_process:bool)->dict:
    r=[]
    if not verified_institution:r.append('verified_institution_required')
    if service_type not in {'prayer','education','counselling','funeral','marriage','family_support','food_aid','community_event'}:r.append('unsupported_service_type')
    if not qualified_lead:r.append('qualified_service_lead_required')
    if not accessibility_supported:r.append('accessibility_support_required')
    if child_safeguarding_required and not child_safeguarding_passed:r.append('child_safeguarding_required')
    if not privacy_notice_published:r.append('privacy_notice_required')
    if not complaints_process:r.append('complaints_process_required')
    return _result(r,'mosque_service_allowed',status='publishable' if not r else 'restricted')

def evaluate_volunteer_assignment(*,identity_verified:bool,role_training_complete:bool,background_check_required:bool,background_check_passed:bool,conflict_disclosed:bool,maximum_weekly_hours:int,safeguarding_code_accepted:bool)->dict:
    if maximum_weekly_hours<0:raise ValueError('hours cannot be negative')
    r=[]
    if not identity_verified:r.append('volunteer_identity_required')
    if not role_training_complete:r.append('role_training_required')
    if background_check_required and not background_check_passed:r.append('background_check_required')
    if not conflict_disclosed:r.append('conflict_disclosure_required')
    if not 1<=maximum_weekly_hours<=48:r.append('volunteer_hours_out_of_bounds')
    if not safeguarding_code_accepted:r.append('safeguarding_code_required')
    return _result(r,'volunteer_assignment_allowed')

def evaluate_service_referral(*,consent_captured:bool,minimum_data_shared:bool,receiving_provider_verified:bool,urgent_risk:bool,urgent_escalation_available:bool,referral_evidence_sha256:str)->dict:
    r=[]
    if not consent_captured:r.append('referral_consent_required')
    if not minimum_data_shared:r.append('data_minimization_required')
    if not receiving_provider_verified:r.append('verified_receiving_provider_required')
    if urgent_risk and not urgent_escalation_available:r.append('urgent_escalation_path_required')
    if not _sha(referral_evidence_sha256):r.append('valid_referral_evidence_required')
    return _result(r,'service_referral_allowed')

def evaluate_crisis_response(*,incident_command_assigned:bool,verified_partner_count:int,beneficiary_safeguarding:bool,stock_or_capacity_verified:bool,communications_verified:bool,financial_controls_active:bool,open_critical_blockers:int)->dict:
    if min(verified_partner_count,open_critical_blockers)<0:raise ValueError('values cannot be negative')
    r=[]
    if not incident_command_assigned:r.append('incident_command_required')
    if verified_partner_count<1:r.append('verified_response_partner_required')
    if not beneficiary_safeguarding:r.append('beneficiary_safeguarding_required')
    if not stock_or_capacity_verified:r.append('capacity_verification_required')
    if not communications_verified:r.append('communications_verification_required')
    if not financial_controls_active:r.append('financial_controls_required')
    if open_critical_blockers:r.append('critical_blockers_unresolved')
    return _result(r,'crisis_response_allowed',status='ready' if not r else 'blocked')

def evaluate_public_service_analytics(*,k_anonymity:int,minimum_group_size:int,location_precision_reduced:bool,personal_data_removed:bool,beneficiary_consent_or_basis:bool,bias_reviewed:bool,publication_sha256:str)->dict:
    if min(k_anonymity,minimum_group_size)<0:raise ValueError('values cannot be negative')
    r=[]
    if k_anonymity<5:r.append('k_anonymity_below_threshold')
    if minimum_group_size<20:r.append('minimum_group_size_below_threshold')
    if not location_precision_reduced:r.append('location_precision_reduction_required')
    if not personal_data_removed:r.append('personal_data_removal_required')
    if not beneficiary_consent_or_basis:r.append('lawful_processing_basis_required')
    if not bias_reviewed:r.append('bias_review_required')
    if not _sha(publication_sha256):r.append('valid_publication_fingerprint_required')
    return _result(r,'public_service_analytics_allowed')

def evaluate_ummah_services_acceptance(*,zakat_waqf_governance_passed:bool,humanitarian_safeguarding_passed:bool,mosque_services_passed:bool,crisis_readiness_passed:bool,privacy_analytics_passed:bool,live_disbursement_validated:bool,external_fiduciary_audit:bool,live_crisis_exercise:bool)->dict:
    controls={'zakat_waqf_governance':zakat_waqf_governance_passed,'humanitarian_safeguarding':humanitarian_safeguarding_passed,'mosque_services':mosque_services_passed,'crisis_readiness':crisis_readiness_passed,'privacy_analytics':privacy_analytics_passed}
    failed=[k for k,v in controls.items() if not v]
    if failed:return _result(failed,'',outcome='failed',portable_ready=False,production_ready=False)
    production=live_disbursement_validated and external_fiduciary_audit and live_crisis_exercise
    reasons=[]
    if not live_disbursement_validated:reasons.append('live_disbursement_validation_required')
    if not external_fiduciary_audit:reasons.append('external_fiduciary_audit_required')
    if not live_crisis_exercise:reasons.append('live_crisis_exercise_required')
    return {'allowed':production,'reason_codes':reasons or ['ummah_services_production_ready'],'policy_version':POLICY_VERSION,'outcome':'passed' if production else 'conditional','portable_ready':True,'production_ready':production}
