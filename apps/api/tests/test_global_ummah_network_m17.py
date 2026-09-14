import pytest
from app.services.global_ummah_network import *
H='a'*64

def test_manifest_deterministic():
 a=compute_federation_manifest(network_slug='global',member_ids=['b','a'],trust_policy_sha256=H,capabilities=['search','identity'])
 b=compute_federation_manifest(network_slug='global',member_ids=['a','b'],trust_policy_sha256=H,capabilities=['identity','search'])
 assert a==b

def test_manifest_rejects_bad_hash():
 with pytest.raises(ValueError):compute_federation_manifest(network_slug='global',member_ids=['a'],trust_policy_sha256='bad',capabilities=[])

def test_federation_requires_three_members():
 assert 'verified_institution_threshold_not_met' in evaluate_institution_federation(verified_institutions=2,independent_jurisdictions=2,trust_policy_published=True,governance_council_active=True,member_exit_process=True,manifest_sha256=H)['reason_codes']

def test_federation_requires_two_jurisdictions():
 assert 'jurisdiction_diversity_required' in evaluate_institution_federation(verified_institutions=3,independent_jurisdictions=1,trust_policy_published=True,governance_council_active=True,member_exit_process=True,manifest_sha256=H)['reason_codes']

def test_federation_passes():
 assert evaluate_institution_federation(verified_institutions=3,independent_jurisdictions=2,trust_policy_published=True,governance_council_active=True,member_exit_process=True,manifest_sha256=H)['allowed']

def test_identity_requires_verified_issuer():
 assert 'verified_issuer_required' in evaluate_trusted_identity(institution_verified=False,identity_assurance_level=2,mfa_enforced=True,credential_rotation_days=90,revocation_supported=True,proof_sha256=H)['reason_codes']

def test_identity_requires_mfa():
 assert 'mfa_required' in evaluate_trusted_identity(institution_verified=True,identity_assurance_level=2,mfa_enforced=False,credential_rotation_days=90,revocation_supported=True,proof_sha256=H)['reason_codes']

def test_identity_passes():
 assert evaluate_trusted_identity(institution_verified=True,identity_assurance_level=2,mfa_enforced=True,credential_rotation_days=90,revocation_supported=True,proof_sha256=H)['allowed']

def test_interop_requires_open_standard():
 assert 'open_standard_required' in evaluate_interoperability_profile(open_standard_used=False,schema_versioned=True,backward_compatible=True,conformance_tests_passed=True,security_review_passed=True,data_minimization=True)['reason_codes']

def test_interop_requires_conformance():
 assert 'conformance_tests_required' in evaluate_interoperability_profile(open_standard_used=True,schema_versioned=True,backward_compatible=True,conformance_tests_passed=False,security_review_passed=True,data_minimization=True)['reason_codes']

def test_interop_passes():
 assert evaluate_interoperability_profile(open_standard_used=True,schema_versioned=True,backward_compatible=True,conformance_tests_passed=True,security_review_passed=True,data_minimization=True)['allowed']

def test_search_requires_multiple_nodes():
 assert 'multiple_search_nodes_required' in evaluate_federated_search(participating_nodes=1,evidence_grounding_percent=99,source_attribution_percent=100,query_privacy_protected=True,harmful_result_rate_basis_points=0,timeout_ms=1000)['reason_codes']

def test_search_blocks_harmful_results():
 assert 'harmful_results_detected' in evaluate_federated_search(participating_nodes=3,evidence_grounding_percent=99,source_attribution_percent=100,query_privacy_protected=True,harmful_result_rate_basis_points=1,timeout_ms=1000)['reason_codes']

def test_search_passes():
 assert evaluate_federated_search(participating_nodes=3,evidence_grounding_percent=99,source_attribution_percent=100,query_privacy_protected=True,harmful_result_rate_basis_points=0,timeout_ms=1000)['allowed']

def test_sharing_requires_purpose_limitation():
 assert 'purpose_limitation_required' in evaluate_data_sharing_agreement(purpose_limited=False,consent_or_lawful_basis=True,minimum_fields_only=True,retention_days=365,cross_border_assessment=True,deletion_supported=True,audit_logging=True)['reason_codes']

def test_sharing_caps_retention():
 assert 'retention_out_of_bounds' in evaluate_data_sharing_agreement(purpose_limited=True,consent_or_lawful_basis=True,minimum_fields_only=True,retention_days=3000,cross_border_assessment=True,deletion_supported=True,audit_logging=True)['reason_codes']

def test_sharing_passes():
 assert evaluate_data_sharing_agreement(purpose_limited=True,consent_or_lawful_basis=True,minimum_fields_only=True,retention_days=365,cross_border_assessment=True,deletion_supported=True,audit_logging=True)['allowed']

def test_scholarship_requires_institutions():
 assert 'cross_institution_participation_required' in evaluate_cross_border_scholarship(institutions=1,qualified_scholars=3,methodology_published=True,conflicts_disclosed=True,minority_views_preserved=True,translation_reviewed=True,evidence_sha256=H)['reason_codes']

def test_scholarship_preserves_minority_views():
 assert 'minority_views_preservation_required' in evaluate_cross_border_scholarship(institutions=2,qualified_scholars=3,methodology_published=True,conflicts_disclosed=True,minority_views_preserved=False,translation_reviewed=True,evidence_sha256=H)['reason_codes']

def test_scholarship_passes():
 assert evaluate_cross_border_scholarship(institutions=2,qualified_scholars=3,methodology_published=True,conflicts_disclosed=True,minority_views_preserved=True,translation_reviewed=True,evidence_sha256=H)['allowed']

def test_consent_requires_withdrawal():
 assert 'withdrawal_support_required' in evaluate_consent_receipt(subject_controlled=True,granular_purposes=True,withdrawal_supported=False,receipt_sha256=H,expires_days=365)['reason_codes']

def test_consent_caps_expiry():
 assert 'consent_expiry_out_of_bounds' in evaluate_consent_receipt(subject_controlled=True,granular_purposes=True,withdrawal_supported=True,receipt_sha256=H,expires_days=731)['reason_codes']

def test_consent_passes():
 assert evaluate_consent_receipt(subject_controlled=True,granular_purposes=True,withdrawal_supported=True,receipt_sha256=H,expires_days=365)['allowed']

def test_resilience_requires_node_quorum():
 assert 'federation_node_quorum_required' in evaluate_network_resilience(healthy_regions=2,healthy_federation_nodes=2,replication_lag_seconds=10,rpo_seconds=300,rto_minutes=30,exercise_within_days=30,partition_recovery_verified=True)['reason_codes']

def test_resilience_blocks_stale_exercise():
 assert 'resilience_exercise_stale' in evaluate_network_resilience(healthy_regions=2,healthy_federation_nodes=3,replication_lag_seconds=10,rpo_seconds=300,rto_minutes=30,exercise_within_days=91,partition_recovery_verified=True)['reason_codes']

def test_resilience_passes():
 assert evaluate_network_resilience(healthy_regions=2,healthy_federation_nodes=3,replication_lag_seconds=10,rpo_seconds=300,rto_minutes=30,exercise_within_days=30,partition_recovery_verified=True)['allowed']

def test_transparency_requires_correction_channel():
 assert 'public_correction_channel_required' in evaluate_public_trust_report(metrics_defined=True,correction_channel=False,incident_disclosure=True,independent_review=True,publication_sha256=H,reporting_delay_days=30)['reason_codes']

def test_transparency_passes():
 assert evaluate_public_trust_report(metrics_defined=True,correction_channel=True,incident_disclosure=True,independent_review=True,publication_sha256=H,reporting_delay_days=30)['allowed']

def test_audit_requires_coverage():
 assert 'member_audit_coverage_below_threshold' in evaluate_federation_audit(member_coverage_percent=90,critical_findings=0,evidence_integrity=True,remediation_owners_assigned=True,follow_up_days=30)['reason_codes']

def test_audit_blocks_critical_findings():
 assert 'critical_findings_unresolved' in evaluate_federation_audit(member_coverage_percent=100,critical_findings=1,evidence_integrity=True,remediation_owners_assigned=True,follow_up_days=30)['reason_codes']

def test_audit_passes():
 assert evaluate_federation_audit(member_coverage_percent=100,critical_findings=0,evidence_integrity=True,remediation_owners_assigned=True,follow_up_days=30)['allowed']

def test_acceptance_fails_control_gap():
 r=evaluate_global_ummah_acceptance(federation_passed=False,identity_passed=True,interoperability_passed=True,search_passed=True,privacy_passed=True,resilience_passed=True,transparency_passed=True,live_partner_interop_validated=False,external_security_audit=False,live_partition_exercise=False);assert r['outcome']=='failed'

def test_acceptance_conditional_without_live_validation():
 r=evaluate_global_ummah_acceptance(federation_passed=True,identity_passed=True,interoperability_passed=True,search_passed=True,privacy_passed=True,resilience_passed=True,transparency_passed=True,live_partner_interop_validated=False,external_security_audit=False,live_partition_exercise=False);assert r['outcome']=='conditional' and r['portable_ready'] and not r['production_ready']

def test_acceptance_passes_production_gate():
 r=evaluate_global_ummah_acceptance(federation_passed=True,identity_passed=True,interoperability_passed=True,search_passed=True,privacy_passed=True,resilience_passed=True,transparency_passed=True,live_partner_interop_validated=True,external_security_audit=True,live_partition_exercise=True);assert r['outcome']=='passed' and r['production_ready']
