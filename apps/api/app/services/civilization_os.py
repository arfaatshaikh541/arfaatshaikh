from __future__ import annotations
import hashlib,json,re
POLICY_VERSION='islamic-civilization-os-v1'
SHA=re.compile(r'^[0-9a-f]{64}$')
def _sha(v:str)->bool:return bool(SHA.fullmatch(v))
def _result(r:list[str],ok:str,**x)->dict:return {'allowed':not r,'reason_codes':r or [ok],'policy_version':POLICY_VERSION,**x}
def compute_lineage_manifest(*,lineage_slug:str,scholar_ids:list[str],institution_ids:list[str],evidence_sha256:list[str])->str:
 if not lineage_slug.strip() or not scholar_ids:raise ValueError('lineage and scholars required')
 if not evidence_sha256 or any(not _sha(x) for x in evidence_sha256):raise ValueError('valid evidence fingerprints required')
 body=json.dumps({'lineage':lineage_slug.strip(),'scholars':sorted(set(scholar_ids)),'institutions':sorted(set(institution_ids)),'evidence':sorted(set(evidence_sha256))},sort_keys=True,separators=(',',':'))
 return hashlib.sha256(body.encode()).hexdigest()
def evaluate_scholarly_lineage(*,qualified_scholars:int,independent_institutions:int,teacher_student_links_verified:bool,chronology_consistent:bool,evidence_coverage_percent:int,minority_traditions_preserved:bool,manifest_sha256:str)->dict:
 if min(qualified_scholars,independent_institutions,evidence_coverage_percent)<0:raise ValueError('values cannot be negative')
 r=[]
 if qualified_scholars<2:r.append('scholar_threshold_not_met')
 if independent_institutions<2:r.append('institutional_independence_required')
 if not teacher_student_links_verified:r.append('lineage_links_unverified')
 if not chronology_consistent:r.append('lineage_chronology_invalid')
 if evidence_coverage_percent<95:r.append('lineage_evidence_below_threshold')
 if not minority_traditions_preserved:r.append('minority_traditions_preservation_required')
 if not _sha(manifest_sha256):r.append('valid_lineage_manifest_required')
 return _result(r,'scholarly_lineage_allowed')
def evaluate_translation_governance(*,source_language_verified:bool,target_language_reviewers:int,independent_reviewers:int,terminology_glossary_versioned:bool,semantic_alignment_percent:int,disputed_terms_disclosed:bool,scholarly_approval:bool)->dict:
 if min(target_language_reviewers,independent_reviewers,semantic_alignment_percent)<0:raise ValueError('values cannot be negative')
 r=[]
 if not source_language_verified:r.append('source_language_verification_required')
 if target_language_reviewers<2:r.append('target_language_reviewer_threshold_not_met')
 if independent_reviewers<1:r.append('independent_translation_review_required')
 if not terminology_glossary_versioned:r.append('versioned_glossary_required')
 if semantic_alignment_percent<95:r.append('semantic_alignment_below_threshold')
 if not disputed_terms_disclosed:r.append('disputed_terms_disclosure_required')
 if not scholarly_approval:r.append('scholarly_translation_approval_required')
 return _result(r,'translation_release_allowed')
def evaluate_verifiable_credential(*,issuer_verified:bool,subject_verified:bool,credential_schema_versioned:bool,signature_sha256:str,revocation_registry:bool,expires_days:int,evidence_linked:bool)->dict:
 if expires_days<0:raise ValueError('expiry cannot be negative')
 r=[]
 if not issuer_verified:r.append('verified_credential_issuer_required')
 if not subject_verified:r.append('verified_credential_subject_required')
 if not credential_schema_versioned:r.append('versioned_credential_schema_required')
 if not _sha(signature_sha256):r.append('valid_credential_signature_required')
 if not revocation_registry:r.append('credential_revocation_registry_required')
 if not 1<=expires_days<=3650:r.append('credential_expiry_out_of_bounds')
 if not evidence_linked:r.append('credential_evidence_required')
 return _result(r,'verifiable_credential_allowed')
def evaluate_civilizational_event(*,verified_hosts:int,jurisdictions:int,scholarly_program_reviewed:bool,safeguarding_plan:bool,accessibility_plan:bool,privacy_notice:bool,emergency_plan:bool,recording_consent:bool)->dict:
 if min(verified_hosts,jurisdictions)<0:raise ValueError('values cannot be negative')
 r=[]
 if verified_hosts<1:r.append('verified_event_host_required')
 if jurisdictions<1:r.append('event_jurisdiction_required')
 if not scholarly_program_reviewed:r.append('scholarly_program_review_required')
 if not safeguarding_plan:r.append('event_safeguarding_required')
 if not accessibility_plan:r.append('event_accessibility_required')
 if not privacy_notice:r.append('event_privacy_notice_required')
 if not emergency_plan:r.append('event_emergency_plan_required')
 if not recording_consent:r.append('recording_consent_required')
 return _result(r,'civilizational_event_allowed')
def evaluate_policy_lifecycle(*,policy_owner_assigned:bool,consultation_complete:bool,scholarly_review_complete:bool,legal_review_complete:bool,versioned:bool,supersession_defined:bool,review_interval_days:int,impact_assessment:bool)->dict:
 if review_interval_days<0:raise ValueError('interval cannot be negative')
 r=[]
 if not policy_owner_assigned:r.append('policy_owner_required')
 if not consultation_complete:r.append('policy_consultation_required')
 if not scholarly_review_complete:r.append('scholarly_policy_review_required')
 if not legal_review_complete:r.append('legal_policy_review_required')
 if not versioned:r.append('policy_versioning_required')
 if not supersession_defined:r.append('policy_supersession_required')
 if not 30<=review_interval_days<=1095:r.append('policy_review_interval_out_of_bounds')
 if not impact_assessment:r.append('policy_impact_assessment_required')
 return _result(r,'policy_lifecycle_allowed')
def evaluate_operational_intelligence(*,metrics_coverage_percent:int,trace_coverage_percent:int,log_integrity:bool,sensitive_data_redacted:bool,forecast_accuracy_percent:int,alert_routes_tested:bool,human_override_available:bool)->dict:
 if min(metrics_coverage_percent,trace_coverage_percent,forecast_accuracy_percent)<0:raise ValueError('values cannot be negative')
 r=[]
 if metrics_coverage_percent<95:r.append('metrics_coverage_below_threshold')
 if trace_coverage_percent<90:r.append('trace_coverage_below_threshold')
 if not log_integrity:r.append('log_integrity_required')
 if not sensitive_data_redacted:r.append('sensitive_data_redaction_required')
 if forecast_accuracy_percent<80:r.append('forecast_accuracy_below_threshold')
 if not alert_routes_tested:r.append('alert_route_test_required')
 if not human_override_available:r.append('human_override_required')
 return _result(r,'operational_intelligence_allowed')
def evaluate_continuity_plan(*,successor_stewards:int,independent_archive_copies:int,credential_escrow_verified:bool,annual_restore_test:bool,knowledge_handover_complete:bool,rpo_minutes:int,rto_hours:int,external_custodian:bool)->dict:
 if min(successor_stewards,independent_archive_copies,rpo_minutes,rto_hours)<0:raise ValueError('values cannot be negative')
 r=[]
 if successor_stewards<2:r.append('successor_steward_threshold_not_met')
 if independent_archive_copies<3:r.append('independent_archive_copies_required')
 if not credential_escrow_verified:r.append('credential_escrow_required')
 if not annual_restore_test:r.append('annual_restore_test_required')
 if not knowledge_handover_complete:r.append('knowledge_handover_required')
 if rpo_minutes>60:r.append('continuity_rpo_above_limit')
 if rto_hours>24:r.append('continuity_rto_above_limit')
 if not external_custodian:r.append('external_continuity_custodian_required')
 return _result(r,'continuity_plan_allowed')
def evaluate_icos_acceptance(*,lineage_passed:bool,translation_passed:bool,credentials_passed:bool,events_passed:bool,policy_passed:bool,operations_passed:bool,continuity_passed:bool,live_institutional_validation:bool,external_scholarly_audit:bool,live_continuity_exercise:bool)->dict:
 controls=[lineage_passed,translation_passed,credentials_passed,events_passed,policy_passed,operations_passed,continuity_passed]
 if not all(controls):return _result(['deterministic_control_failure'],'',outcome='failed',portable_ready=False,production_ready=False)
 prod=live_institutional_validation and external_scholarly_audit and live_continuity_exercise
 reasons=[] if prod else [x for x,v in [('live_institutional_validation_unverified',live_institutional_validation),('external_scholarly_audit_required',external_scholarly_audit),('live_continuity_exercise_required',live_continuity_exercise)] if not v]
 return {'allowed':prod,'reason_codes':reasons or ['islamic_civilization_os_accepted'],'policy_version':POLICY_VERSION,'outcome':'passed' if prod else 'conditional','portable_ready':True,'production_ready':prod}
