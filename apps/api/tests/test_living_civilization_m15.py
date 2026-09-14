import pytest
from app.services.living_civilization import *
H='a'*64

def test_council_passes():
 assert evaluate_scholarly_council(active_scholars=5,independent_institutions=3,conflict_policy_published=True,minority_views_preserved=True,quorum_percent=60,evidence_sha256=H)['allowed']
def test_council_requires_independence():
 assert 'institutional_independence_required' in evaluate_scholarly_council(active_scholars=5,independent_institutions=1,conflict_policy_published=True,minority_views_preserved=True,quorum_percent=60,evidence_sha256=H)['reason_codes']
def test_council_preserves_minority_views():
 assert 'minority_view_preservation_required' in evaluate_scholarly_council(active_scholars=5,independent_institutions=3,conflict_policy_published=True,minority_views_preserved=False,quorum_percent=60,evidence_sha256=H)['reason_codes']
def test_sensitive_decision_needs_three_reviewers():
 assert 'reviewer_threshold_not_met' in evaluate_scholarly_decision(content_type='fiqh',reviewer_count=2,independent_reviewer_count=1,quorum_met=True,evidence_linked=True,dissent_recorded=True,decision_sha256=H)['reason_codes']
def test_decision_passes():
 assert evaluate_scholarly_decision(content_type='quran',reviewer_count=3,independent_reviewer_count=1,quorum_met=True,evidence_linked=True,dissent_recorded=True,decision_sha256=H)['allowed']
def test_lineage_deterministic():
 a=compute_provenance_lineage(canonical_id='x',version='1',parent_fingerprints=[H,'b'*64],evidence_fingerprints=['c'*64],payload_sha256=H)
 b=compute_provenance_lineage(canonical_id='x',version='1',parent_fingerprints=['b'*64,H],evidence_fingerprints=['c'*64],payload_sha256=H)
 assert a==b
def test_lineage_rejects_bad_hash():
 with pytest.raises(ValueError):compute_provenance_lineage(canonical_id='x',version='1',parent_fingerprints=['bad'],evidence_fingerprints=[],payload_sha256=H)
def test_provenance_requires_primary_source():
 assert 'primary_source_required' in evaluate_provenance_release(lineage_sha256=H,source_count=2,primary_source_count=0,unresolved_breaks=0,supersession_declared=True,sensitive_content=False,scholarly_approved=False)['reason_codes']
def test_sensitive_provenance_requires_scholar():
 assert 'scholarly_approval_required' in evaluate_provenance_release(lineage_sha256=H,source_count=2,primary_source_count=1,unresolved_breaks=0,supersession_declared=True,sensitive_content=True,scholarly_approved=False)['reason_codes']
def test_provenance_passes():
 assert evaluate_provenance_release(lineage_sha256=H,source_count=2,primary_source_count=1,unresolved_breaks=0,supersession_declared=True,sensitive_content=True,scholarly_approved=True)['allowed']
def test_research_requires_two_institutions():
 assert 'cross_institution_collaboration_required' in evaluate_research_project(institution_count=1,lead_researcher_verified=True,methodology_published=True,data_management_plan=True,ethics_review_required=False,ethics_review_passed=False,open_conflicts=0)['reason_codes']
def test_research_ethics_gate():
 assert 'ethics_review_required' in evaluate_research_project(institution_count=2,lead_researcher_verified=True,methodology_published=True,data_management_plan=True,ethics_review_required=True,ethics_review_passed=False,open_conflicts=0)['reason_codes']
def test_research_passes():
 assert evaluate_research_project(institution_count=2,lead_researcher_verified=True,methodology_published=True,data_management_plan=True,ethics_review_required=True,ethics_review_passed=True,open_conflicts=0)['allowed']
def test_curriculum_requires_full_objectives():
 assert 'learning_objective_coverage_incomplete' in evaluate_curriculum_release(learning_objectives_covered=9,total_learning_objectives=10,evidence_coverage_percent=100,assessment_validated=True,accessibility_reviewed=True,child_safe=True,scholarly_reviewed=True)['reason_codes']
def test_curriculum_requires_accessibility():
 assert 'accessibility_review_required' in evaluate_curriculum_release(learning_objectives_covered=10,total_learning_objectives=10,evidence_coverage_percent=100,assessment_validated=True,accessibility_reviewed=False,child_safe=True,scholarly_reviewed=True)['reason_codes']
def test_curriculum_passes():
 assert evaluate_curriculum_release(learning_objectives_covered=10,total_learning_objectives=10,evidence_coverage_percent=100,assessment_validated=True,accessibility_reviewed=True,child_safe=True,scholarly_reviewed=True)['allowed']
def test_certificate_requires_identity():
 assert 'identity_verification_required' in evaluate_certification_award(identity_verified=False,assessment_score=90,minimum_score=80,proctoring_required=False,proctoring_verified=False,attempt_integrity_verified=True,certificate_fingerprint=H)['reason_codes']
def test_certificate_requires_proctoring_when_configured():
 assert 'proctoring_verification_required' in evaluate_certification_award(identity_verified=True,assessment_score=90,minimum_score=80,proctoring_required=True,proctoring_verified=False,attempt_integrity_verified=True,certificate_fingerprint=H)['reason_codes']
def test_certificate_passes():
 assert evaluate_certification_award(identity_verified=True,assessment_score=90,minimum_score=80,proctoring_required=True,proctoring_verified=True,attempt_integrity_verified=True,certificate_fingerprint=H)['allowed']
def test_sensitive_contribution_requires_scholar():
 assert 'scholarly_review_required' in evaluate_community_contribution(content_type='hadith',evidence_count=1,moderation_passed=True,duplicate_checked=True,privacy_safe=True,scholarly_reviewed=False,author_consent=True)['reason_codes']
def test_contribution_requires_evidence():
 assert 'evidence_required' in evaluate_community_contribution(content_type='research',evidence_count=0,moderation_passed=True,duplicate_checked=True,privacy_safe=True,scholarly_reviewed=False,author_consent=True)['reason_codes']
def test_contribution_passes():
 assert evaluate_community_contribution(content_type='research',evidence_count=1,moderation_passed=True,duplicate_checked=True,privacy_safe=True,scholarly_reviewed=False,author_consent=True)['allowed']
def test_stewardship_blocks_critical_incident():
 assert 'critical_incidents_unresolved' in evaluate_stewardship_transfer(current_steward_active=True,new_steward_verified=True,asset_inventory_complete=True,credential_rotation_planned=True,audit_handover_complete=True,open_critical_incidents=1)['reason_codes']
def test_stewardship_passes():
 assert evaluate_stewardship_transfer(current_steward_active=True,new_steward_verified=True,asset_inventory_complete=True,credential_rotation_planned=True,audit_handover_complete=True,open_critical_incidents=0)['allowed']
def test_analytics_requires_k_anonymity():
 assert 'k_anonymity_below_threshold' in evaluate_analytics_release(k_anonymity=4,minimum_group_size=10,personal_data_removed=True,consent_basis_verified=True,bias_reviewed=True,metric_definitions_published=True,export_fingerprint=H)['reason_codes']
def test_analytics_requires_personal_data_removal():
 assert 'personal_data_removal_required' in evaluate_analytics_release(k_anonymity=5,minimum_group_size=10,personal_data_removed=False,consent_basis_verified=True,bias_reviewed=True,metric_definitions_published=True,export_fingerprint=H)['reason_codes']
def test_analytics_passes():
 assert evaluate_analytics_release(k_anonymity=5,minimum_group_size=10,personal_data_removed=True,consent_basis_verified=True,bias_reviewed=True,metric_definitions_published=True,export_fingerprint=H)['allowed']
def test_api_ecosystem_requires_successor():
 assert 'deprecated_api_successor_required' in evaluate_api_ecosystem(active_products=1,deprecated_without_successor=1,sdk_coverage_percent=100,documentation_coverage_percent=100,breaking_change_notice_days=90,security_review_passed=True)['reason_codes']
def test_api_ecosystem_requires_notice():
 assert 'breaking_change_notice_too_short' in evaluate_api_ecosystem(active_products=1,deprecated_without_successor=0,sdk_coverage_percent=100,documentation_coverage_percent=100,breaking_change_notice_days=30,security_review_passed=True)['reason_codes']
def test_api_ecosystem_passes():
 assert evaluate_api_ecosystem(active_products=1,deprecated_without_successor=0,sdk_coverage_percent=90,documentation_coverage_percent=100,breaking_change_notice_days=90,security_review_passed=True)['allowed']
def test_acceptance_fails_missing_control():
 r=evaluate_platform_maturity(scholarly_governance_passed=False,provenance_passed=True,research_collaboration_passed=True,curriculum_passed=True,community_stewardship_passed=True,analytics_passed=True,api_ecosystem_passed=True,live_operations_validated=False,external_scholarly_audit=False); assert r['outcome']=='failed'
def test_acceptance_conditional_without_live_validation():
 r=evaluate_platform_maturity(scholarly_governance_passed=True,provenance_passed=True,research_collaboration_passed=True,curriculum_passed=True,community_stewardship_passed=True,analytics_passed=True,api_ecosystem_passed=True,live_operations_validated=False,external_scholarly_audit=False); assert r['outcome']=='conditional' and r['portable_ready'] and not r['production_ready']
def test_acceptance_passes_production_gate():
 r=evaluate_platform_maturity(scholarly_governance_passed=True,provenance_passed=True,research_collaboration_passed=True,curriculum_passed=True,community_stewardship_passed=True,analytics_passed=True,api_ecosystem_passed=True,live_operations_validated=True,external_scholarly_audit=True); assert r['outcome']=='passed' and r['production_ready']
