import pytest
from app.services.civilizational_infrastructure import *
H='a'*64

def test_archive_deposit_allows_governed_sensitive_content():
 r=evaluate_archive_deposit(content_type='quran',manifest_sha256=H,source_sha256=H,signature_verified=True,scholarly_approved=True,retention_years=100,immutable_storage=True); assert r['allowed']

def test_archive_deposit_rejects_unsigned_content():
 assert 'signature_verification_required' in evaluate_archive_deposit(content_type='research',manifest_sha256=H,source_sha256=H,signature_verified=False,scholarly_approved=False,retention_years=50,immutable_storage=True)['reason_codes']

def test_archive_manifest_is_deterministic():
 a=[{'path':'b.json','sha256':H,'size_bytes':2},{'path':'a.json','sha256':H,'size_bytes':1}]
 assert compute_archive_manifest(archive_slug='Core',version='1',objects=a)==compute_archive_manifest(archive_slug='core',version='1',objects=list(reversed(a)))

def test_archive_manifest_rejects_traversal():
 with pytest.raises(ValueError):compute_archive_manifest(archive_slug='x',version='1',objects=[{'path':'../x','sha256':H,'size_bytes':1}])

def test_replica_set_requires_diversity():
 r=evaluate_replica_set(replica_regions={'uae'},replica_count=1,independent_providers=1,air_gapped_copy=False,fixity_verified=False); assert not r['allowed']

def test_replica_set_passes():
 assert evaluate_replica_set(replica_regions={'uae','eu','apac'},replica_count=3,independent_providers=2,air_gapped_copy=True,fixity_verified=True)['allowed']

def test_fixity_detects_root_mismatch():
 assert 'archive_root_mismatch' in evaluate_fixity_check(expected_sha256=H,observed_sha256='b'*64,objects_expected=2,objects_verified=2,unreadable_objects=0)['reason_codes']

def test_fixity_passes_complete_archive():
 assert evaluate_fixity_check(expected_sha256=H,observed_sha256=H,objects_expected=2,objects_verified=2,unreadable_objects=0)['allowed']

def test_semantic_index_requires_scholarly_review():
 r=evaluate_semantic_index(content_type='tafsir',source_coverage_percent=100,evidence_linked=True,embedding_model_fingerprint=H,index_fingerprint=H,scholarly_reviewed=False); assert 'scholarly_review_required' in r['reason_codes']

def test_semantic_index_passes():
 assert evaluate_semantic_index(content_type='research',source_coverage_percent=99,evidence_linked=True,embedding_model_fingerprint=H,index_fingerprint=H,scholarly_reviewed=False)['allowed']

def test_search_release_blocks_harmful_results():
 r=evaluate_search_release(precision_at_10=95,recall_at_10=90,grounding_rate=99,harmful_result_rate=1,arabic_evaluation_passed=True,bias_reviewed=True); assert not r['allowed']

def test_search_release_passes_quality_gate():
 assert evaluate_search_release(precision_at_10=95,recall_at_10=90,grounding_rate=99,harmful_result_rate=0,arabic_evaluation_passed=True,bias_reviewed=True)['allowed']

def test_offline_package_blocks_personal_data():
 r=evaluate_offline_package(manifest_sha256=H,package_sha256=H,signature_verified=True,expires_in_days=30,max_size_mb=100,contains_personal_data=True,revocation_list_embedded=True); assert 'personal_data_forbidden_offline' in r['reason_codes']

def test_offline_package_passes():
 assert evaluate_offline_package(manifest_sha256=H,package_sha256=H,signature_verified=True,expires_in_days=30,max_size_mb=100,contains_personal_data=False,revocation_list_embedded=True)['allowed']

def test_offline_update_requires_space():
 r=evaluate_offline_update(base_version='1',target_version='2',delta_sha256=H,signature_verified=True,rollback_available=True,free_space_mb=10,required_space_mb=20); assert 'insufficient_device_space' in r['reason_codes']

def test_offline_update_passes():
 assert evaluate_offline_update(base_version='1',target_version='2',delta_sha256=H,signature_verified=True,rollback_available=True,free_space_mb=20,required_space_mb=20)['allowed']

def test_failover_requires_two_regions():
 r=evaluate_failover(healthy_regions=1,replication_lag_seconds=10,rpo_seconds=60,rto_seconds=300,last_drill_days=10,data_loss_detected=False); assert 'multi_region_health_required' in r['reason_codes']

def test_failover_rejects_stale_drill():
 assert 'disaster_recovery_drill_stale' in evaluate_failover(healthy_regions=2,replication_lag_seconds=10,rpo_seconds=60,rto_seconds=300,last_drill_days=91,data_loss_detected=False)['reason_codes']

def test_failover_passes():
 assert evaluate_failover(healthy_regions=2,replication_lag_seconds=10,rpo_seconds=60,rto_seconds=300,last_drill_days=30,data_loss_detected=False)['allowed']

def test_observability_requires_redaction():
 r=evaluate_observability(metrics_coverage=100,trace_coverage=100,log_integrity_verified=True,sensitive_data_redacted=False,alert_routes_tested=True,slo_burn_alerts=True); assert 'sensitive_data_redaction_required' in r['reason_codes']

def test_observability_passes():
 assert evaluate_observability(metrics_coverage=100,trace_coverage=95,log_integrity_verified=True,sensitive_data_redacted=True,alert_routes_tested=True,slo_burn_alerts=True)['allowed']

def test_capacity_requires_headroom():
 r=evaluate_capacity(peak_rps=100,tested_rps=100,p95_latency_ms=300,error_rate_basis_points=1,search_corpus_millions=1,headroom_percent=20); assert 'capacity_headroom_below_threshold' in r['reason_codes']

def test_capacity_blocks_high_latency():
 assert 'p95_latency_above_limit' in evaluate_capacity(peak_rps=100,tested_rps=130,p95_latency_ms=501,error_rate_basis_points=1,search_corpus_millions=1,headroom_percent=30)['reason_codes']

def test_capacity_passes():
 assert evaluate_capacity(peak_rps=100,tested_rps=130,p95_latency_ms=300,error_rate_basis_points=1,search_corpus_millions=1,headroom_percent=30)['allowed']

def test_acceptance_fails_missing_control():
 r=evaluate_milestone_acceptance(archive_preservation_passed=False,search_quality_passed=True,offline_distribution_passed=True,failover_passed=True,observability_passed=True,capacity_passed=True,live_multi_region_validated=False,external_preservation_audit=False); assert r['outcome']=='failed'

def test_acceptance_is_conditional_without_live_validation():
 r=evaluate_milestone_acceptance(archive_preservation_passed=True,search_quality_passed=True,offline_distribution_passed=True,failover_passed=True,observability_passed=True,capacity_passed=True,live_multi_region_validated=False,external_preservation_audit=False); assert r['outcome']=='conditional' and r['portable_ready'] and not r['production_ready']

def test_acceptance_passes_production_gate():
 r=evaluate_milestone_acceptance(archive_preservation_passed=True,search_quality_passed=True,offline_distribution_passed=True,failover_passed=True,observability_passed=True,capacity_passed=True,live_multi_region_validated=True,external_preservation_audit=True); assert r['outcome']=='passed' and r['production_ready']

@pytest.mark.parametrize('content_type',['quran','hadith','tafsir','fiqh','fatwa'])
def test_every_sensitive_archive_requires_scholarly_approval(content_type):
 r=evaluate_archive_deposit(content_type=content_type,manifest_sha256=H,source_sha256=H,signature_verified=True,scholarly_approved=False,retention_years=100,immutable_storage=True); assert 'scholarly_approval_required' in r['reason_codes']
