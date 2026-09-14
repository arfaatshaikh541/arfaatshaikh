import pytest
from app.services.civilization_os import *
H='a'*64

def test_lineage_manifest_deterministic():
 a=compute_lineage_manifest(lineage_slug='hadith',scholar_ids=['b','a'],institution_ids=['y','x'],evidence_sha256=[H,'b'*64])
 b=compute_lineage_manifest(lineage_slug='hadith',scholar_ids=['a','b'],institution_ids=['x','y'],evidence_sha256=['b'*64,H])
 assert a==b

def test_lineage_manifest_rejects_bad_hash():
 with pytest.raises(ValueError):compute_lineage_manifest(lineage_slug='x',scholar_ids=['a'],institution_ids=[],evidence_sha256=['bad'])

def test_lineage_requires_two_scholars():
 assert 'scholar_threshold_not_met' in evaluate_scholarly_lineage(qualified_scholars=1,independent_institutions=2,teacher_student_links_verified=True,chronology_consistent=True,evidence_coverage_percent=100,minority_traditions_preserved=True,manifest_sha256=H)['reason_codes']

def test_lineage_requires_chronology():
 assert 'lineage_chronology_invalid' in evaluate_scholarly_lineage(qualified_scholars=2,independent_institutions=2,teacher_student_links_verified=True,chronology_consistent=False,evidence_coverage_percent=100,minority_traditions_preserved=True,manifest_sha256=H)['reason_codes']

def test_lineage_passes():
 assert evaluate_scholarly_lineage(qualified_scholars=2,independent_institutions=2,teacher_student_links_verified=True,chronology_consistent=True,evidence_coverage_percent=100,minority_traditions_preserved=True,manifest_sha256=H)['allowed']

def test_translation_requires_two_language_reviewers():
 assert 'target_language_reviewer_threshold_not_met' in evaluate_translation_governance(source_language_verified=True,target_language_reviewers=1,independent_reviewers=1,terminology_glossary_versioned=True,semantic_alignment_percent=98,disputed_terms_disclosed=True,scholarly_approval=True)['reason_codes']

def test_translation_requires_dispute_disclosure():
 assert 'disputed_terms_disclosure_required' in evaluate_translation_governance(source_language_verified=True,target_language_reviewers=2,independent_reviewers=1,terminology_glossary_versioned=True,semantic_alignment_percent=98,disputed_terms_disclosed=False,scholarly_approval=True)['reason_codes']

def test_translation_passes():
 assert evaluate_translation_governance(source_language_verified=True,target_language_reviewers=2,independent_reviewers=1,terminology_glossary_versioned=True,semantic_alignment_percent=98,disputed_terms_disclosed=True,scholarly_approval=True)['allowed']

def test_credential_requires_verified_issuer():
 assert 'verified_credential_issuer_required' in evaluate_verifiable_credential(issuer_verified=False,subject_verified=True,credential_schema_versioned=True,signature_sha256=H,revocation_registry=True,expires_days=365,evidence_linked=True)['reason_codes']

def test_credential_requires_revocation():
 assert 'credential_revocation_registry_required' in evaluate_verifiable_credential(issuer_verified=True,subject_verified=True,credential_schema_versioned=True,signature_sha256=H,revocation_registry=False,expires_days=365,evidence_linked=True)['reason_codes']

def test_credential_caps_expiry():
 assert 'credential_expiry_out_of_bounds' in evaluate_verifiable_credential(issuer_verified=True,subject_verified=True,credential_schema_versioned=True,signature_sha256=H,revocation_registry=True,expires_days=3651,evidence_linked=True)['reason_codes']

def test_credential_passes():
 assert evaluate_verifiable_credential(issuer_verified=True,subject_verified=True,credential_schema_versioned=True,signature_sha256=H,revocation_registry=True,expires_days=365,evidence_linked=True)['allowed']

def test_event_requires_scholarly_program_review():
 assert 'scholarly_program_review_required' in evaluate_civilizational_event(verified_hosts=1,jurisdictions=1,scholarly_program_reviewed=False,safeguarding_plan=True,accessibility_plan=True,privacy_notice=True,emergency_plan=True,recording_consent=True)['reason_codes']

def test_event_requires_safeguarding():
 assert 'event_safeguarding_required' in evaluate_civilizational_event(verified_hosts=1,jurisdictions=1,scholarly_program_reviewed=True,safeguarding_plan=False,accessibility_plan=True,privacy_notice=True,emergency_plan=True,recording_consent=True)['reason_codes']

def test_event_passes():
 assert evaluate_civilizational_event(verified_hosts=1,jurisdictions=1,scholarly_program_reviewed=True,safeguarding_plan=True,accessibility_plan=True,privacy_notice=True,emergency_plan=True,recording_consent=True)['allowed']

def test_policy_requires_consultation():
 assert 'policy_consultation_required' in evaluate_policy_lifecycle(policy_owner_assigned=True,consultation_complete=False,scholarly_review_complete=True,legal_review_complete=True,versioned=True,supersession_defined=True,review_interval_days=365,impact_assessment=True)['reason_codes']

def test_policy_review_interval_bounds():
 assert 'policy_review_interval_out_of_bounds' in evaluate_policy_lifecycle(policy_owner_assigned=True,consultation_complete=True,scholarly_review_complete=True,legal_review_complete=True,versioned=True,supersession_defined=True,review_interval_days=10,impact_assessment=True)['reason_codes']

def test_policy_passes():
 assert evaluate_policy_lifecycle(policy_owner_assigned=True,consultation_complete=True,scholarly_review_complete=True,legal_review_complete=True,versioned=True,supersession_defined=True,review_interval_days=365,impact_assessment=True)['allowed']

def test_operations_requires_metrics_coverage():
 assert 'metrics_coverage_below_threshold' in evaluate_operational_intelligence(metrics_coverage_percent=94,trace_coverage_percent=90,log_integrity=True,sensitive_data_redacted=True,forecast_accuracy_percent=85,alert_routes_tested=True,human_override_available=True)['reason_codes']

def test_operations_requires_redaction():
 assert 'sensitive_data_redaction_required' in evaluate_operational_intelligence(metrics_coverage_percent=95,trace_coverage_percent=90,log_integrity=True,sensitive_data_redacted=False,forecast_accuracy_percent=85,alert_routes_tested=True,human_override_available=True)['reason_codes']

def test_operations_requires_human_override():
 assert 'human_override_required' in evaluate_operational_intelligence(metrics_coverage_percent=95,trace_coverage_percent=90,log_integrity=True,sensitive_data_redacted=True,forecast_accuracy_percent=85,alert_routes_tested=True,human_override_available=False)['reason_codes']

def test_operations_passes():
 assert evaluate_operational_intelligence(metrics_coverage_percent=95,trace_coverage_percent=90,log_integrity=True,sensitive_data_redacted=True,forecast_accuracy_percent=85,alert_routes_tested=True,human_override_available=True)['allowed']

def test_continuity_requires_two_successors():
 assert 'successor_steward_threshold_not_met' in evaluate_continuity_plan(successor_stewards=1,independent_archive_copies=3,credential_escrow_verified=True,annual_restore_test=True,knowledge_handover_complete=True,rpo_minutes=60,rto_hours=24,external_custodian=True)['reason_codes']

def test_continuity_requires_three_copies():
 assert 'independent_archive_copies_required' in evaluate_continuity_plan(successor_stewards=2,independent_archive_copies=2,credential_escrow_verified=True,annual_restore_test=True,knowledge_handover_complete=True,rpo_minutes=60,rto_hours=24,external_custodian=True)['reason_codes']

def test_continuity_caps_rpo():
 assert 'continuity_rpo_above_limit' in evaluate_continuity_plan(successor_stewards=2,independent_archive_copies=3,credential_escrow_verified=True,annual_restore_test=True,knowledge_handover_complete=True,rpo_minutes=61,rto_hours=24,external_custodian=True)['reason_codes']

def test_continuity_passes():
 assert evaluate_continuity_plan(successor_stewards=2,independent_archive_copies=3,credential_escrow_verified=True,annual_restore_test=True,knowledge_handover_complete=True,rpo_minutes=60,rto_hours=24,external_custodian=True)['allowed']

def test_acceptance_fails_control_gap():
 r=evaluate_icos_acceptance(lineage_passed=False,translation_passed=True,credentials_passed=True,events_passed=True,policy_passed=True,operations_passed=True,continuity_passed=True,live_institutional_validation=False,external_scholarly_audit=False,live_continuity_exercise=False)
 assert r['outcome']=='failed'

def test_acceptance_is_conditional_without_live_evidence():
 r=evaluate_icos_acceptance(lineage_passed=True,translation_passed=True,credentials_passed=True,events_passed=True,policy_passed=True,operations_passed=True,continuity_passed=True,live_institutional_validation=False,external_scholarly_audit=False,live_continuity_exercise=False)
 assert r['outcome']=='conditional' and r['portable_ready'] and not r['production_ready']

def test_acceptance_passes_production_gate():
 r=evaluate_icos_acceptance(lineage_passed=True,translation_passed=True,credentials_passed=True,events_passed=True,policy_passed=True,operations_passed=True,continuity_passed=True,live_institutional_validation=True,external_scholarly_audit=True,live_continuity_exercise=True)
 assert r['outcome']=='passed' and r['production_ready']
