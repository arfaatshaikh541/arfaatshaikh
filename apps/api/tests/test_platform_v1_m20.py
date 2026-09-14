import pytest
from app.services.platform_v1 import *
from app.models.platform_v1 import *
H='a'*64

def test_manifest_deterministic():
 a=compute_release_manifest(release_version='1.0.0',component_ids=['b','a'],migration_head='0081',artifact_sha256=['b'*64,H])
 b=compute_release_manifest(release_version='1.0.0',component_ids=['a','b'],migration_head='0081',artifact_sha256=[H,'b'*64])
 assert a==b and len(a)==64

def test_manifest_rejects_bad_hash():
 with pytest.raises(ValueError):compute_release_manifest(release_version='1',component_ids=['a'],migration_head='x',artifact_sha256=['bad'])

def test_integration_passes():assert evaluate_cross_domain_integration(registered_domains=20,required_domains=20,contract_coverage_percent=95,cross_domain_foreign_keys_verified=True,tenant_isolation_verified=True,event_contracts_versioned=True,idempotency_coverage_percent=90,critical_integration_failures=0)['allowed']
@pytest.mark.parametrize('field,code,value',[
('registered_domains','required_domains_not_integrated',19),('contract_coverage_percent','integration_contract_coverage_below_threshold',94),('cross_domain_foreign_keys_verified','cross_domain_foreign_keys_unverified',False),('tenant_isolation_verified','cross_domain_tenant_isolation_unverified',False),('event_contracts_versioned','event_contract_versioning_required',False),('idempotency_coverage_percent','idempotency_coverage_below_threshold',89),('critical_integration_failures','critical_integration_failures_present',1)])
def test_integration_failures(field,code,value):
 d=dict(registered_domains=20,required_domains=20,contract_coverage_percent=95,cross_domain_foreign_keys_verified=True,tenant_isolation_verified=True,event_contracts_versioned=True,idempotency_coverage_percent=90,critical_integration_failures=0);d[field]=value
 assert code in evaluate_cross_domain_integration(**d)['reason_codes']

def test_security_passes():assert evaluate_security_compliance_posture(auth_controls_passed=True,tenant_isolation_passed=True,secrets_encrypted=True,audit_coverage_percent=95,critical_vulnerabilities=0,high_vulnerabilities=0,dependency_scan_passed=True,privacy_review_passed=True,scholarly_governance_passed=True)['allowed']
def test_security_blocks_highs():assert 'high_vulnerabilities_present' in evaluate_security_compliance_posture(auth_controls_passed=True,tenant_isolation_passed=True,secrets_encrypted=True,audit_coverage_percent=95,critical_vulnerabilities=0,high_vulnerabilities=1,dependency_scan_passed=True,privacy_review_passed=True,scholarly_governance_passed=True)['reason_codes']
def test_security_requires_scholarship():assert 'scholarly_governance_required' in evaluate_security_compliance_posture(auth_controls_passed=True,tenant_isolation_passed=True,secrets_encrypted=True,audit_coverage_percent=95,critical_vulnerabilities=0,high_vulnerabilities=0,dependency_scan_passed=True,privacy_review_passed=True,scholarly_governance_passed=False)['reason_codes']

def test_candidate_passes():assert evaluate_release_candidate(build_reproducible=True,test_pass_percent=100,migration_rendered=True,rollback_plan_verified=True,release_notes_complete=True,artifact_signed=True,sbom_generated=True,open_blockers=0,manifest_sha256=H)['allowed']
def test_candidate_requires_sbom():assert 'sbom_required' in evaluate_release_candidate(build_reproducible=True,test_pass_percent=100,migration_rendered=True,rollback_plan_verified=True,release_notes_complete=True,artifact_signed=True,sbom_generated=False,open_blockers=0,manifest_sha256=H)['reason_codes']
def test_candidate_requires_100_percent():assert 'release_test_pass_rate_below_threshold' in evaluate_release_candidate(build_reproducible=True,test_pass_percent=99,migration_rendered=True,rollback_plan_verified=True,release_notes_complete=True,artifact_signed=True,sbom_generated=True,open_blockers=0,manifest_sha256=H)['reason_codes']

def test_observability_passes():assert evaluate_observability_slo(service_coverage_percent=95,metrics_coverage_percent=95,trace_coverage_percent=90,log_integrity=True,alert_routes_tested=True,slo_definitions_complete=True,error_budget_policy=True,runbooks_complete_percent=95)['allowed']
def test_observability_requires_error_budget():assert 'error_budget_policy_required' in evaluate_observability_slo(service_coverage_percent=95,metrics_coverage_percent=95,trace_coverage_percent=90,log_integrity=True,alert_routes_tested=True,slo_definitions_complete=True,error_budget_policy=False,runbooks_complete_percent=95)['reason_codes']

def test_dr_passes():assert evaluate_disaster_recovery(backup_verified=True,restore_tested=True,rpo_minutes=5,rto_minutes=30,failover_tested=True,failback_tested=True,data_loss_detected=False,last_exercise_days=90)['allowed']
def test_dr_blocks_data_loss():assert 'data_loss_detected' in evaluate_disaster_recovery(backup_verified=True,restore_tested=True,rpo_minutes=5,rto_minutes=30,failover_tested=True,failback_tested=True,data_loss_detected=True,last_exercise_days=90)['reason_codes']
def test_dr_requires_failback():assert 'failback_test_required' in evaluate_disaster_recovery(backup_verified=True,restore_tested=True,rpo_minutes=5,rto_minutes=30,failover_tested=True,failback_tested=False,data_loss_detected=False,last_exercise_days=90)['reason_codes']

def test_performance_passes():assert evaluate_performance_readiness(peak_rps=100,tested_rps=100,p95_latency_ms=500,error_rate_basis_points=10,headroom_percent=30,corpus_records=1_000_000,load_profile_representative=True)['allowed']
def test_performance_blocks_small_corpus():assert 'corpus_scale_below_threshold' in evaluate_performance_readiness(peak_rps=100,tested_rps=100,p95_latency_ms=500,error_rate_basis_points=10,headroom_percent=30,corpus_records=999999,load_profile_representative=True)['reason_codes']

def test_governance_passes():assert evaluate_release_governance(release_owner_assigned=True,change_approval_complete=True,rollback_authority_assigned=True,maintenance_window_defined=True,stakeholder_notice_complete=True,support_handover_complete=True,go_no_go_recorded=True)['allowed']
def test_governance_requires_rollback_authority():assert 'rollback_authority_required' in evaluate_release_governance(release_owner_assigned=True,change_approval_complete=True,rollback_authority_assigned=False,maintenance_window_defined=True,stakeholder_notice_complete=True,support_handover_complete=True,go_no_go_recorded=True)['reason_codes']

def _accept(**x):
 d=dict(integration_passed=True,security_passed=True,release_candidate_passed=True,observability_passed=True,disaster_recovery_passed=True,performance_passed=True,governance_passed=True,live_deployment_validated=False,external_security_audit=False,external_scholarly_audit=False,live_failover_exercise=False);d.update(x);return evaluate_v1_acceptance(**d)
def test_acceptance_fails_control():
 r=_accept(integration_passed=False);assert r['outcome']=='failed' and not r['portable_ready']
def test_acceptance_portable_only():
 r=_accept();assert r['outcome']=='conditional' and r['portable_ready'] and not r['production_ready']
def test_acceptance_production():
 r=_accept(live_deployment_validated=True,external_security_audit=True,external_scholarly_audit=True,live_failover_exercise=True);assert r['allowed'] and r['production_ready']
def test_policy_version_stable():assert POLICY_VERSION=='islamic-civilization-platform-v1'
def test_all_models_have_tables():
 classes=[PlatformComponent,IntegrationContract,CrossDomainVerification,SecurityPostureReview,ComplianceControlResult,ReleaseCandidate,ReleaseArtifact,SoftwareBillOfMaterials,ObservabilityReadiness,ServiceLevelObjective,DisasterRecoveryReview,RecoveryExercise,PerformanceBenchmark,ReleaseGovernanceDecision,ProductionValidationRecord,PlatformV1Acceptance]
 assert all(getattr(c,'__tablename__',None) for c in classes)
def test_acceptance_table_name():assert PlatformV1Acceptance.__tablename__=='platform_v1_acceptance'
