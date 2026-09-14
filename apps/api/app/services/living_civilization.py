from __future__ import annotations
import hashlib, json, re

POLICY_VERSION='living-civilization-v1'
SHA=re.compile(r'^[0-9a-f]{64}$')
SENSITIVE={'quran','hadith','tafsir','fiqh','fatwa'}

def _sha(v:str)->bool:return bool(SHA.fullmatch(v))
def _result(reasons:list[str], success:str, **extra)->dict:
    return {'allowed':not reasons,'reason_codes':reasons or [success],'policy_version':POLICY_VERSION,**extra}

def evaluate_scholarly_council(*,active_scholars:int,independent_institutions:int,conflict_policy_published:bool,minority_views_preserved:bool,quorum_percent:int,evidence_sha256:str)->dict:
    if min(active_scholars,independent_institutions,quorum_percent)<0:raise ValueError('values cannot be negative')
    r=[]
    if active_scholars<3:r.append('minimum_three_active_scholars_required')
    if independent_institutions<2:r.append('institutional_independence_required')
    if not 50<=quorum_percent<=100:r.append('quorum_out_of_bounds')
    if not conflict_policy_published:r.append('conflict_policy_required')
    if not minority_views_preserved:r.append('minority_view_preservation_required')
    if not _sha(evidence_sha256):r.append('valid_evidence_fingerprint_required')
    return _result(r,'scholarly_council_allowed',status='active' if not r else 'restricted')

def evaluate_scholarly_decision(*,content_type:str,reviewer_count:int,independent_reviewer_count:int,quorum_met:bool,evidence_linked:bool,dissent_recorded:bool,decision_sha256:str)->dict:
    if min(reviewer_count,independent_reviewer_count)<0:raise ValueError('counts cannot be negative')
    r=[]
    required=3 if content_type in SENSITIVE else 2
    if reviewer_count<required:r.append('reviewer_threshold_not_met')
    if independent_reviewer_count<1:r.append('independent_review_required')
    if not quorum_met:r.append('quorum_required')
    if not evidence_linked:r.append('evidence_linkage_required')
    if not dissent_recorded:r.append('dissent_record_required')
    if not _sha(decision_sha256):r.append('valid_decision_fingerprint_required')
    return _result(r,'scholarly_decision_allowed',status='approved' if not r else 'review')

def compute_provenance_lineage(*,canonical_id:str,version:str,parent_fingerprints:list[str],evidence_fingerprints:list[str],payload_sha256:str)->str:
    if not canonical_id.strip() or not version.strip():raise ValueError('canonical id and version are required')
    if not _sha(payload_sha256):raise ValueError('valid payload fingerprint required')
    fingerprints=parent_fingerprints+evidence_fingerprints
    if any(not _sha(v) for v in fingerprints):raise ValueError('invalid lineage fingerprint')
    canonical=json.dumps({'canonical_id':canonical_id.strip(),'version':version.strip(),'parents':sorted(parent_fingerprints),'evidence':sorted(evidence_fingerprints),'payload':payload_sha256},sort_keys=True,separators=(',',':'))
    return hashlib.sha256(canonical.encode()).hexdigest()

def evaluate_provenance_release(*,lineage_sha256:str,source_count:int,primary_source_count:int,unresolved_breaks:int,supersession_declared:bool,sensitive_content:bool,scholarly_approved:bool)->dict:
    if min(source_count,primary_source_count,unresolved_breaks)<0:raise ValueError('counts cannot be negative')
    r=[]
    if not _sha(lineage_sha256):r.append('valid_lineage_fingerprint_required')
    if source_count<1:r.append('source_required')
    if primary_source_count<1:r.append('primary_source_required')
    if unresolved_breaks:r.append('provenance_breaks_unresolved')
    if not supersession_declared:r.append('supersession_status_required')
    if sensitive_content and not scholarly_approved:r.append('scholarly_approval_required')
    return _result(r,'provenance_release_allowed')

def evaluate_research_project(*,institution_count:int,lead_researcher_verified:bool,methodology_published:bool,data_management_plan:bool,ethics_review_required:bool,ethics_review_passed:bool,open_conflicts:int)->dict:
    if min(institution_count,open_conflicts)<0:raise ValueError('values cannot be negative')
    r=[]
    if institution_count<2:r.append('cross_institution_collaboration_required')
    if not lead_researcher_verified:r.append('verified_lead_researcher_required')
    if not methodology_published:r.append('published_methodology_required')
    if not data_management_plan:r.append('data_management_plan_required')
    if ethics_review_required and not ethics_review_passed:r.append('ethics_review_required')
    if open_conflicts:r.append('research_conflicts_unresolved')
    return _result(r,'research_project_allowed',status='active' if not r else 'restricted')

def evaluate_curriculum_release(*,learning_objectives_covered:int,total_learning_objectives:int,evidence_coverage_percent:int,assessment_validated:bool,accessibility_reviewed:bool,child_safe:bool,scholarly_reviewed:bool)->dict:
    if min(learning_objectives_covered,total_learning_objectives,evidence_coverage_percent)<0:raise ValueError('values cannot be negative')
    if total_learning_objectives==0:raise ValueError('total learning objectives must be positive')
    r=[]
    if learning_objectives_covered!=total_learning_objectives:r.append('learning_objective_coverage_incomplete')
    if evidence_coverage_percent<95:r.append('evidence_coverage_below_threshold')
    if not assessment_validated:r.append('assessment_validation_required')
    if not accessibility_reviewed:r.append('accessibility_review_required')
    if not child_safe:r.append('child_safety_required')
    if not scholarly_reviewed:r.append('scholarly_review_required')
    return _result(r,'curriculum_release_allowed',status='published' if not r else 'review')

def evaluate_certification_award(*,identity_verified:bool,assessment_score:int,minimum_score:int,proctoring_required:bool,proctoring_verified:bool,attempt_integrity_verified:bool,certificate_fingerprint:str)->dict:
    if min(assessment_score,minimum_score)<0 or max(assessment_score,minimum_score)>100:raise ValueError('scores must be between 0 and 100')
    r=[]
    if not identity_verified:r.append('identity_verification_required')
    if assessment_score<minimum_score:r.append('minimum_score_not_met')
    if proctoring_required and not proctoring_verified:r.append('proctoring_verification_required')
    if not attempt_integrity_verified:r.append('attempt_integrity_required')
    if not _sha(certificate_fingerprint):r.append('valid_certificate_fingerprint_required')
    return _result(r,'certification_award_allowed')

def evaluate_community_contribution(*,content_type:str,evidence_count:int,moderation_passed:bool,duplicate_checked:bool,privacy_safe:bool,scholarly_reviewed:bool,author_consent:bool)->dict:
    if evidence_count<0:raise ValueError('evidence count cannot be negative')
    r=[]
    if evidence_count<1:r.append('evidence_required')
    if not moderation_passed:r.append('moderation_required')
    if not duplicate_checked:r.append('duplicate_check_required')
    if not privacy_safe:r.append('privacy_review_required')
    if content_type in SENSITIVE and not scholarly_reviewed:r.append('scholarly_review_required')
    if not author_consent:r.append('author_consent_required')
    return _result(r,'community_contribution_allowed',status='publishable' if not r else 'review')

def evaluate_stewardship_transfer(*,current_steward_active:bool,new_steward_verified:bool,asset_inventory_complete:bool,credential_rotation_planned:bool,audit_handover_complete:bool,open_critical_incidents:int)->dict:
    if open_critical_incidents<0:raise ValueError('incident count cannot be negative')
    r=[]
    if not current_steward_active:r.append('active_current_steward_required')
    if not new_steward_verified:r.append('verified_new_steward_required')
    if not asset_inventory_complete:r.append('asset_inventory_required')
    if not credential_rotation_planned:r.append('credential_rotation_required')
    if not audit_handover_complete:r.append('audit_handover_required')
    if open_critical_incidents:r.append('critical_incidents_unresolved')
    return _result(r,'stewardship_transfer_allowed')

def evaluate_analytics_release(*,k_anonymity:int,minimum_group_size:int,personal_data_removed:bool,consent_basis_verified:bool,bias_reviewed:bool,metric_definitions_published:bool,export_fingerprint:str)->dict:
    if min(k_anonymity,minimum_group_size)<0:raise ValueError('values cannot be negative')
    r=[]
    if k_anonymity<5:r.append('k_anonymity_below_threshold')
    if minimum_group_size<10:r.append('minimum_group_size_below_threshold')
    if not personal_data_removed:r.append('personal_data_removal_required')
    if not consent_basis_verified:r.append('consent_basis_required')
    if not bias_reviewed:r.append('bias_review_required')
    if not metric_definitions_published:r.append('metric_definitions_required')
    if not _sha(export_fingerprint):r.append('valid_export_fingerprint_required')
    return _result(r,'analytics_release_allowed')

def evaluate_api_ecosystem(*,active_products:int,deprecated_without_successor:int,sdk_coverage_percent:int,documentation_coverage_percent:int,breaking_change_notice_days:int,security_review_passed:bool)->dict:
    if min(active_products,deprecated_without_successor,sdk_coverage_percent,documentation_coverage_percent,breaking_change_notice_days)<0:raise ValueError('values cannot be negative')
    r=[]
    if active_products<1:r.append('active_api_product_required')
    if deprecated_without_successor:r.append('deprecated_api_successor_required')
    if sdk_coverage_percent<80:r.append('sdk_coverage_below_threshold')
    if documentation_coverage_percent<95:r.append('documentation_coverage_below_threshold')
    if breaking_change_notice_days<90:r.append('breaking_change_notice_too_short')
    if not security_review_passed:r.append('security_review_required')
    return _result(r,'api_ecosystem_allowed')

def evaluate_platform_maturity(*,scholarly_governance_passed:bool,provenance_passed:bool,research_collaboration_passed:bool,curriculum_passed:bool,community_stewardship_passed:bool,analytics_passed:bool,api_ecosystem_passed:bool,live_operations_validated:bool,external_scholarly_audit:bool)->dict:
    checks={'scholarly_governance':scholarly_governance_passed,'provenance':provenance_passed,'research_collaboration':research_collaboration_passed,'curriculum':curriculum_passed,'community_stewardship':community_stewardship_passed,'analytics':analytics_passed,'api_ecosystem':api_ecosystem_passed}
    r=[f'{k}_required' for k,v in checks.items() if not v]
    portable=not r
    production=portable and live_operations_validated and external_scholarly_audit
    if portable and not live_operations_validated:r.append('live_operations_validation_required')
    if portable and not external_scholarly_audit:r.append('external_scholarly_audit_required')
    return {'allowed':portable,'portable_ready':portable,'production_ready':production,'outcome':'passed' if production else ('conditional' if portable else 'failed'),'reason_codes':r or ['platform_maturity_passed'],'policy_version':POLICY_VERSION}
