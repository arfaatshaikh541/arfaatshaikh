from __future__ import annotations
import hashlib,json,re
POLICY_VERSION='trusted-islamic-life-v1'
SHA=re.compile(r'^[0-9a-f]{64}$')
def _sha(v:str)->bool:return bool(SHA.fullmatch(v))
def _result(r:list[str],ok:str,**x)->dict:return {'allowed':not r,'reason_codes':r or [ok],'policy_version':POLICY_VERSION,**x}
def compute_time_profile_manifest(*,profile_slug:str,method_code:str,authority_ids:list[str],parameter_sha256:list[str])->str:
 if not profile_slug.strip() or not method_code.strip() or not authority_ids:raise ValueError('profile, method and authorities required')
 if not parameter_sha256 or any(not _sha(x) for x in parameter_sha256):raise ValueError('valid parameter fingerprints required')
 body=json.dumps({'profile':profile_slug.strip(),'method':method_code.strip(),'authorities':sorted(set(authority_ids)),'parameters':sorted(set(parameter_sha256))},sort_keys=True,separators=(',',':'))
 return hashlib.sha256(body.encode()).hexdigest()
def evaluate_prayer_time_governance(*,verified_authorities:int,jurisdictions:int,calculation_method_published:bool,high_latitude_rule_defined:bool,location_precision_meters:int,astronomical_validation_percent:int,manual_override_audited:bool,manifest_sha256:str)->dict:
 if min(verified_authorities,jurisdictions,location_precision_meters,astronomical_validation_percent)<0:raise ValueError('values cannot be negative')
 r=[]
 if verified_authorities<1:r.append('verified_time_authority_required')
 if jurisdictions<1:r.append('time_jurisdiction_required')
 if not calculation_method_published:r.append('published_calculation_method_required')
 if not high_latitude_rule_defined:r.append('high_latitude_rule_required')
 if location_precision_meters>1000:r.append('location_precision_above_limit')
 if astronomical_validation_percent<99:r.append('astronomical_validation_below_threshold')
 if not manual_override_audited:r.append('audited_manual_override_required')
 if not _sha(manifest_sha256):r.append('valid_time_profile_manifest_required')
 return _result(r,'prayer_time_profile_allowed')
def evaluate_hijri_calendar_release(*,authority_verified:bool,observation_method_published:bool,calculation_fallback_disclosed:bool,jurisdiction_scope_defined:bool,disagreement_disclosed:bool,release_notice_hours:int,evidence_sha256:str)->dict:
 if release_notice_hours<0:raise ValueError('notice cannot be negative')
 r=[]
 if not authority_verified:r.append('verified_calendar_authority_required')
 if not observation_method_published:r.append('published_observation_method_required')
 if not calculation_fallback_disclosed:r.append('calculation_fallback_disclosure_required')
 if not jurisdiction_scope_defined:r.append('calendar_jurisdiction_required')
 if not disagreement_disclosed:r.append('calendar_disagreement_disclosure_required')
 if release_notice_hours>72:r.append('calendar_release_notice_above_limit')
 if not _sha(evidence_sha256):r.append('valid_calendar_evidence_required')
 return _result(r,'hijri_calendar_release_allowed')
def evaluate_halal_standard(*,scholarly_board_members:int,independent_labs:int,ingredient_traceability_percent:int,supply_chain_audited:bool,cross_contamination_controls:bool,recall_process:bool,public_standard:bool)->dict:
 if min(scholarly_board_members,independent_labs,ingredient_traceability_percent)<0:raise ValueError('values cannot be negative')
 r=[]
 if scholarly_board_members<3:r.append('halal_scholarly_board_threshold_not_met')
 if independent_labs<1:r.append('independent_halal_lab_required')
 if ingredient_traceability_percent<98:r.append('ingredient_traceability_below_threshold')
 if not supply_chain_audited:r.append('halal_supply_chain_audit_required')
 if not cross_contamination_controls:r.append('cross_contamination_controls_required')
 if not recall_process:r.append('halal_recall_process_required')
 if not public_standard:r.append('public_halal_standard_required')
 return _result(r,'halal_standard_allowed')
def evaluate_halal_certification(*,certifier_verified:bool,facility_audited:bool,product_scope_defined:bool,certificate_sha256:str,expires_days:int,revocation_registry:bool,critical_findings:int)->dict:
 if min(expires_days,critical_findings)<0:raise ValueError('values cannot be negative')
 r=[]
 if not certifier_verified:r.append('verified_halal_certifier_required')
 if not facility_audited:r.append('facility_halal_audit_required')
 if not product_scope_defined:r.append('halal_product_scope_required')
 if not _sha(certificate_sha256):r.append('valid_halal_certificate_required')
 if not 1<=expires_days<=730:r.append('halal_certificate_expiry_out_of_bounds')
 if not revocation_registry:r.append('halal_revocation_registry_required')
 if critical_findings:r.append('unresolved_halal_critical_findings')
 return _result(r,'halal_certification_allowed')
def evaluate_ethical_commerce(*,price_transparency:bool,terms_plain_language:bool,no_deceptive_marketing:bool,labour_due_diligence:bool,environmental_claims_verified:bool,complaints_channel:bool,traceability_percent:int)->dict:
 if traceability_percent<0:raise ValueError('traceability cannot be negative')
 r=[]
 if not price_transparency:r.append('price_transparency_required')
 if not terms_plain_language:r.append('plain_language_terms_required')
 if not no_deceptive_marketing:r.append('deceptive_marketing_detected')
 if not labour_due_diligence:r.append('labour_due_diligence_required')
 if not environmental_claims_verified:r.append('environmental_claim_verification_required')
 if not complaints_channel:r.append('commerce_complaints_channel_required')
 if traceability_percent<90:r.append('commerce_traceability_below_threshold')
 return _result(r,'ethical_commerce_allowed')
def evaluate_islamic_finance_product(*,shariah_board_members:int,independent_reviewers:int,contract_structure_disclosed:bool,fees_fully_disclosed:bool,asset_or_service_linked:bool,late_payment_treatment_disclosed:bool,annual_shariah_audit:bool,critical_findings:int)->dict:
 if min(shariah_board_members,independent_reviewers,critical_findings)<0:raise ValueError('values cannot be negative')
 r=[]
 if shariah_board_members<3:r.append('shariah_board_threshold_not_met')
 if independent_reviewers<1:r.append('independent_shariah_review_required')
 if not contract_structure_disclosed:r.append('contract_structure_disclosure_required')
 if not fees_fully_disclosed:r.append('full_fee_disclosure_required')
 if not asset_or_service_linked:r.append('underlying_asset_or_service_required')
 if not late_payment_treatment_disclosed:r.append('late_payment_treatment_disclosure_required')
 if not annual_shariah_audit:r.append('annual_shariah_audit_required')
 if critical_findings:r.append('unresolved_shariah_critical_findings')
 return _result(r,'islamic_finance_product_allowed')
def evaluate_family_service(*,qualified_practitioners:int,safeguarding_policy:bool,privacy_controls:bool,informed_consent:bool,domestic_abuse_escalation:bool,child_protection_path:bool,legal_scope_disclosed:bool,scholarly_scope_disclosed:bool)->dict:
 if qualified_practitioners<0:raise ValueError('practitioners cannot be negative')
 r=[]
 if qualified_practitioners<1:r.append('qualified_family_practitioner_required')
 if not safeguarding_policy:r.append('family_safeguarding_required')
 if not privacy_controls:r.append('family_privacy_controls_required')
 if not informed_consent:r.append('family_informed_consent_required')
 if not domestic_abuse_escalation:r.append('domestic_abuse_escalation_required')
 if not child_protection_path:r.append('child_protection_path_required')
 if not legal_scope_disclosed:r.append('family_legal_scope_disclosure_required')
 if not scholarly_scope_disclosed:r.append('family_scholarly_scope_disclosure_required')
 return _result(r,'family_service_allowed')
def evaluate_heritage_stewardship(*,ownership_verified:bool,significance_documented:bool,conservation_plan:bool,digital_twin_or_archive:bool,community_consultation:bool,conflict_risk_assessed:bool,public_access_policy:bool,evidence_sha256:str)->dict:
 r=[]
 if not ownership_verified:r.append('heritage_ownership_verification_required')
 if not significance_documented:r.append('heritage_significance_documentation_required')
 if not conservation_plan:r.append('heritage_conservation_plan_required')
 if not digital_twin_or_archive:r.append('heritage_digital_preservation_required')
 if not community_consultation:r.append('heritage_community_consultation_required')
 if not conflict_risk_assessed:r.append('heritage_conflict_risk_assessment_required')
 if not public_access_policy:r.append('heritage_public_access_policy_required')
 if not _sha(evidence_sha256):r.append('valid_heritage_evidence_required')
 return _result(r,'heritage_stewardship_allowed')
def evaluate_islamic_life_acceptance(*,timekeeping_passed:bool,calendar_passed:bool,halal_passed:bool,commerce_passed:bool,finance_passed:bool,family_passed:bool,heritage_passed:bool,live_authority_validation:bool,external_shariah_audit:bool,live_traceability_exercise:bool)->dict:
 controls=[timekeeping_passed,calendar_passed,halal_passed,commerce_passed,finance_passed,family_passed,heritage_passed]
 if not all(controls):return _result(['deterministic_control_failure'],'',outcome='failed',portable_ready=False,production_ready=False)
 prod=live_authority_validation and external_shariah_audit and live_traceability_exercise
 reasons=[] if prod else [x for x,v in [('live_authority_validation_unverified',live_authority_validation),('external_shariah_audit_required',external_shariah_audit),('live_traceability_exercise_required',live_traceability_exercise)] if not v]
 return {'allowed':prod,'reason_codes':reasons or ['trusted_islamic_life_accepted'],'policy_version':POLICY_VERSION,'outcome':'passed' if prod else 'conditional','portable_ready':True,'production_ready':prod}
