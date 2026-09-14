from __future__ import annotations
import hashlib,json,re
POLICY_VERSION='islamic-civilization-platform-v1'
SHA=re.compile(r'^[0-9a-f]{64}$')
def _sha(v:str)->bool:return bool(SHA.fullmatch(v))
def _result(r:list[str],ok:str,**x)->dict:return {'allowed':not r,'reason_codes':r or [ok],'policy_version':POLICY_VERSION,**x}
def compute_release_manifest(*,release_version:str,component_ids:list[str],migration_head:str,artifact_sha256:list[str])->str:
 if not release_version.strip() or not migration_head.strip() or not component_ids:raise ValueError('release, migration head and components required')
 if not artifact_sha256 or any(not _sha(x) for x in artifact_sha256):raise ValueError('valid artifact fingerprints required')
 body=json.dumps({'release':release_version.strip(),'components':sorted(set(component_ids)),'migration_head':migration_head.strip(),'artifacts':sorted(set(artifact_sha256))},sort_keys=True,separators=(',',':'))
 return hashlib.sha256(body.encode()).hexdigest()
def evaluate_cross_domain_integration(*,registered_domains:int,required_domains:int,contract_coverage_percent:int,cross_domain_foreign_keys_verified:bool,tenant_isolation_verified:bool,event_contracts_versioned:bool,idempotency_coverage_percent:int,critical_integration_failures:int)->dict:
 if min(registered_domains,required_domains,contract_coverage_percent,idempotency_coverage_percent,critical_integration_failures)<0:raise ValueError('values cannot be negative')
 r=[]
 if registered_domains<required_domains:r.append('required_domains_not_integrated')
 if contract_coverage_percent<95:r.append('integration_contract_coverage_below_threshold')
 if not cross_domain_foreign_keys_verified:r.append('cross_domain_foreign_keys_unverified')
 if not tenant_isolation_verified:r.append('cross_domain_tenant_isolation_unverified')
 if not event_contracts_versioned:r.append('event_contract_versioning_required')
 if idempotency_coverage_percent<90:r.append('idempotency_coverage_below_threshold')
 if critical_integration_failures:r.append('critical_integration_failures_present')
 return _result(r,'cross_domain_integration_allowed')
def evaluate_security_compliance_posture(*,auth_controls_passed:bool,tenant_isolation_passed:bool,secrets_encrypted:bool,audit_coverage_percent:int,critical_vulnerabilities:int,high_vulnerabilities:int,dependency_scan_passed:bool,privacy_review_passed:bool,scholarly_governance_passed:bool)->dict:
 if min(audit_coverage_percent,critical_vulnerabilities,high_vulnerabilities)<0:raise ValueError('values cannot be negative')
 r=[]
 if not auth_controls_passed:r.append('authentication_controls_failed')
 if not tenant_isolation_passed:r.append('tenant_isolation_failed')
 if not secrets_encrypted:r.append('secrets_encryption_required')
 if audit_coverage_percent<95:r.append('audit_coverage_below_threshold')
 if critical_vulnerabilities:r.append('critical_vulnerabilities_present')
 if high_vulnerabilities>0:r.append('high_vulnerabilities_present')
 if not dependency_scan_passed:r.append('dependency_scan_failed')
 if not privacy_review_passed:r.append('privacy_review_required')
 if not scholarly_governance_passed:r.append('scholarly_governance_required')
 return _result(r,'security_compliance_posture_allowed')
def evaluate_release_candidate(*,build_reproducible:bool,test_pass_percent:int,migration_rendered:bool,rollback_plan_verified:bool,release_notes_complete:bool,artifact_signed:bool,sbom_generated:bool,open_blockers:int,manifest_sha256:str)->dict:
 if min(test_pass_percent,open_blockers)<0:raise ValueError('values cannot be negative')
 r=[]
 if not build_reproducible:r.append('reproducible_build_required')
 if test_pass_percent<100:r.append('release_test_pass_rate_below_threshold')
 if not migration_rendered:r.append('migration_render_required')
 if not rollback_plan_verified:r.append('rollback_plan_verification_required')
 if not release_notes_complete:r.append('release_notes_required')
 if not artifact_signed:r.append('signed_release_artifact_required')
 if not sbom_generated:r.append('sbom_required')
 if open_blockers:r.append('release_blockers_present')
 if not _sha(manifest_sha256):r.append('valid_release_manifest_required')
 return _result(r,'release_candidate_allowed')
def evaluate_observability_slo(*,service_coverage_percent:int,metrics_coverage_percent:int,trace_coverage_percent:int,log_integrity:bool,alert_routes_tested:bool,slo_definitions_complete:bool,error_budget_policy:bool,runbooks_complete_percent:int)->dict:
 if min(service_coverage_percent,metrics_coverage_percent,trace_coverage_percent,runbooks_complete_percent)<0:raise ValueError('values cannot be negative')
 r=[]
 if service_coverage_percent<95:r.append('service_observability_coverage_below_threshold')
 if metrics_coverage_percent<95:r.append('metrics_coverage_below_threshold')
 if trace_coverage_percent<90:r.append('trace_coverage_below_threshold')
 if not log_integrity:r.append('log_integrity_required')
 if not alert_routes_tested:r.append('alert_routes_test_required')
 if not slo_definitions_complete:r.append('slo_definitions_required')
 if not error_budget_policy:r.append('error_budget_policy_required')
 if runbooks_complete_percent<95:r.append('runbook_coverage_below_threshold')
 return _result(r,'observability_slo_allowed')
def evaluate_disaster_recovery(*,backup_verified:bool,restore_tested:bool,rpo_minutes:int,rto_minutes:int,failover_tested:bool,failback_tested:bool,data_loss_detected:bool,last_exercise_days:int)->dict:
 if min(rpo_minutes,rto_minutes,last_exercise_days)<0:raise ValueError('values cannot be negative')
 r=[]
 if not backup_verified:r.append('verified_backup_required')
 if not restore_tested:r.append('restore_test_required')
 if rpo_minutes>5:r.append('rpo_above_limit')
 if rto_minutes>30:r.append('rto_above_limit')
 if not failover_tested:r.append('failover_test_required')
 if not failback_tested:r.append('failback_test_required')
 if data_loss_detected:r.append('data_loss_detected')
 if last_exercise_days>90:r.append('disaster_recovery_exercise_stale')
 return _result(r,'disaster_recovery_allowed')
def evaluate_performance_readiness(*,peak_rps:int,tested_rps:int,p95_latency_ms:int,error_rate_basis_points:int,headroom_percent:int,corpus_records:int,load_profile_representative:bool)->dict:
 if min(peak_rps,tested_rps,p95_latency_ms,error_rate_basis_points,headroom_percent,corpus_records)<0:raise ValueError('values cannot be negative')
 r=[]
 if tested_rps<peak_rps:r.append('tested_capacity_below_peak')
 if p95_latency_ms>500:r.append('p95_latency_above_limit')
 if error_rate_basis_points>10:r.append('error_rate_above_limit')
 if headroom_percent<30:r.append('capacity_headroom_below_threshold')
 if corpus_records<1_000_000:r.append('corpus_scale_below_threshold')
 if not load_profile_representative:r.append('representative_load_profile_required')
 return _result(r,'performance_readiness_allowed')
def evaluate_release_governance(*,release_owner_assigned:bool,change_approval_complete:bool,rollback_authority_assigned:bool,maintenance_window_defined:bool,stakeholder_notice_complete:bool,support_handover_complete:bool,go_no_go_recorded:bool)->dict:
 r=[]
 if not release_owner_assigned:r.append('release_owner_required')
 if not change_approval_complete:r.append('change_approval_required')
 if not rollback_authority_assigned:r.append('rollback_authority_required')
 if not maintenance_window_defined:r.append('maintenance_window_required')
 if not stakeholder_notice_complete:r.append('stakeholder_notice_required')
 if not support_handover_complete:r.append('support_handover_required')
 if not go_no_go_recorded:r.append('go_no_go_decision_required')
 return _result(r,'release_governance_allowed')
def evaluate_v1_acceptance(*,integration_passed:bool,security_passed:bool,release_candidate_passed:bool,observability_passed:bool,disaster_recovery_passed:bool,performance_passed:bool,governance_passed:bool,live_deployment_validated:bool,external_security_audit:bool,external_scholarly_audit:bool,live_failover_exercise:bool)->dict:
 controls=[integration_passed,security_passed,release_candidate_passed,observability_passed,disaster_recovery_passed,performance_passed,governance_passed]
 if not all(controls):return _result(['deterministic_control_failure'],'',outcome='failed',portable_ready=False,production_ready=False)
 prod=live_deployment_validated and external_security_audit and external_scholarly_audit and live_failover_exercise
 reasons=[] if prod else [x for x,v in [('live_deployment_validation_required',live_deployment_validated),('external_security_audit_required',external_security_audit),('external_scholarly_audit_required',external_scholarly_audit),('live_failover_exercise_required',live_failover_exercise)] if not v]
 return {'allowed':prod,'reason_codes':reasons or ['platform_v1_accepted'],'policy_version':POLICY_VERSION,'outcome':'passed' if prod else 'conditional','portable_ready':True,'production_ready':prod}
