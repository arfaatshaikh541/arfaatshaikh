from __future__ import annotations
import hashlib, ipaddress, json, re
from urllib.parse import urlparse
POLICY_VERSION='civilizational-infrastructure-v1'
SHA=re.compile(r'^[0-9a-f]{64}$')
SENSITIVE={'quran','hadith','tafsir','fiqh','fatwa'}

def _sha(v:str)->bool:return bool(SHA.fullmatch(v))
def _https(v:str)->bool:
    try:
        p=urlparse(v)
        if p.scheme!='https' or not p.hostname or p.username or p.password:return False
        h=p.hostname.lower().rstrip('.')
        if h=='localhost' or h.endswith('.local'):return False
        try:i=ipaddress.ip_address(h)
        except ValueError:return True
        return not(i.is_private or i.is_loopback or i.is_link_local or i.is_reserved or i.is_multicast)
    except ValueError:return False

def evaluate_archive_deposit(*,content_type:str,manifest_sha256:str,source_sha256:str,signature_verified:bool,scholarly_approved:bool,retention_years:int,immutable_storage:bool)->dict:
    r=[]
    if not _sha(manifest_sha256) or not _sha(source_sha256):r.append('valid_archive_fingerprints_required')
    if not 10<=retention_years<=1000:r.append('retention_period_out_of_bounds')
    if not immutable_storage:r.append('immutable_storage_required')
    if not signature_verified:r.append('signature_verification_required')
    if content_type in SENSITIVE and not scholarly_approved:r.append('scholarly_approval_required')
    return {'allowed':not r,'status':'sealed' if not r else 'pending','reason_codes':r or ['archive_deposit_allowed'],'policy_version':POLICY_VERSION}

def compute_archive_manifest(*,archive_slug:str,version:str,objects:list[dict[str,object]])->str:
    if not archive_slug.strip() or not version.strip():raise ValueError('archive slug and version are required')
    if not objects:raise ValueError('archive objects are required')
    rows=[]
    for o in objects:
        path=str(o.get('path','')).strip(); digest=str(o.get('sha256','')); size=int(o.get('size_bytes',-1))
        if not path or path.startswith('/') or '..' in path.split('/'):raise ValueError('unsafe archive path')
        if not _sha(digest) or size<0:raise ValueError('invalid archive object')
        rows.append(f'{path}|{digest}|{size}')
    canonical='\n'.join([archive_slug.strip().lower(),version.strip(),*sorted(rows)])
    return hashlib.sha256(canonical.encode()).hexdigest()

def evaluate_replica_set(*,replica_regions:set[str],replica_count:int,independent_providers:int,air_gapped_copy:bool,fixity_verified:bool)->dict:
    r=[]
    if replica_count!=len(replica_regions):r.append('replica_count_mismatch')
    if replica_count<3:r.append('minimum_three_replicas_required')
    if independent_providers<2:r.append('provider_diversity_required')
    if not air_gapped_copy:r.append('air_gapped_copy_required')
    if not fixity_verified:r.append('fixity_verification_required')
    return {'allowed':not r,'reason_codes':r or ['replica_set_allowed'],'policy_version':POLICY_VERSION}

def evaluate_fixity_check(*,expected_sha256:str,observed_sha256:str,objects_expected:int,objects_verified:int,unreadable_objects:int)->dict:
    if min(objects_expected,objects_verified,unreadable_objects)<0:raise ValueError('counts cannot be negative')
    r=[]
    if not _sha(expected_sha256) or not _sha(observed_sha256):r.append('valid_fixity_fingerprints_required')
    if expected_sha256!=observed_sha256:r.append('archive_root_mismatch')
    if objects_expected!=objects_verified:r.append('object_verification_incomplete')
    if unreadable_objects:r.append('unreadable_archive_objects')
    return {'allowed':not r,'outcome':'passed' if not r else 'failed','reason_codes':r or ['fixity_check_passed'],'policy_version':POLICY_VERSION}

def evaluate_semantic_index(*,content_type:str,source_coverage_percent:int,evidence_linked:bool,embedding_model_fingerprint:str,index_fingerprint:str,scholarly_reviewed:bool)->dict:
    if not 0<=source_coverage_percent<=100:raise ValueError('coverage must be between 0 and 100')
    r=[]
    if source_coverage_percent<99:r.append('source_coverage_below_threshold')
    if not evidence_linked:r.append('evidence_linkage_required')
    if not _sha(embedding_model_fingerprint) or not _sha(index_fingerprint):r.append('valid_index_fingerprints_required')
    if content_type in SENSITIVE and not scholarly_reviewed:r.append('scholarly_review_required')
    return {'allowed':not r,'status':'ready' if not r else 'restricted','reason_codes':r or ['semantic_index_allowed'],'policy_version':POLICY_VERSION}

def evaluate_search_release(*,precision_at_10:int,recall_at_10:int,grounding_rate:int,harmful_result_rate:int,arabic_evaluation_passed:bool,bias_reviewed:bool)->dict:
    vals=[precision_at_10,recall_at_10,grounding_rate,harmful_result_rate]
    if any(v<0 or v>100 for v in vals):raise ValueError('metrics must be between 0 and 100')
    r=[]
    if precision_at_10<90:r.append('precision_below_threshold')
    if recall_at_10<85:r.append('recall_below_threshold')
    if grounding_rate<98:r.append('grounding_below_threshold')
    if harmful_result_rate>0:r.append('harmful_results_detected')
    if not arabic_evaluation_passed:r.append('arabic_evaluation_required')
    if not bias_reviewed:r.append('bias_review_required')
    return {'allowed':not r,'reason_codes':r or ['search_release_allowed'],'policy_version':POLICY_VERSION}

def evaluate_offline_package(*,manifest_sha256:str,package_sha256:str,signature_verified:bool,expires_in_days:int,max_size_mb:int,contains_personal_data:bool,revocation_list_embedded:bool)->dict:
    r=[]
    if not _sha(manifest_sha256) or not _sha(package_sha256):r.append('valid_package_fingerprints_required')
    if not signature_verified:r.append('signature_verification_required')
    if not 1<=expires_in_days<=365:r.append('package_expiry_out_of_bounds')
    if not 1<=max_size_mb<=10240:r.append('package_size_out_of_bounds')
    if contains_personal_data:r.append('personal_data_forbidden_offline')
    if not revocation_list_embedded:r.append('revocation_list_required')
    return {'allowed':not r,'reason_codes':r or ['offline_package_allowed'],'policy_version':POLICY_VERSION}

def evaluate_offline_update(*,base_version:str,target_version:str,delta_sha256:str,signature_verified:bool,rollback_available:bool,free_space_mb:int,required_space_mb:int)->dict:
    if free_space_mb<0 or required_space_mb<0:raise ValueError('space values cannot be negative')
    r=[]
    if not base_version.strip() or not target_version.strip() or base_version==target_version:r.append('valid_version_transition_required')
    if not _sha(delta_sha256):r.append('valid_delta_fingerprint_required')
    if not signature_verified:r.append('signature_verification_required')
    if not rollback_available:r.append('rollback_required')
    if free_space_mb<required_space_mb:r.append('insufficient_device_space')
    return {'allowed':not r,'reason_codes':r or ['offline_update_allowed'],'policy_version':POLICY_VERSION}

def evaluate_failover(*,healthy_regions:int,replication_lag_seconds:int,rpo_seconds:int,rto_seconds:int,last_drill_days:int,data_loss_detected:bool)->dict:
    if min(healthy_regions,replication_lag_seconds,rpo_seconds,rto_seconds,last_drill_days)<0:raise ValueError('values cannot be negative')
    r=[]
    if healthy_regions<2:r.append('multi_region_health_required')
    if replication_lag_seconds>rpo_seconds:r.append('replication_lag_exceeds_rpo')
    if rpo_seconds>300:r.append('rpo_above_limit')
    if rto_seconds>1800:r.append('rto_above_limit')
    if last_drill_days>90:r.append('disaster_recovery_drill_stale')
    if data_loss_detected:r.append('data_loss_detected')
    return {'allowed':not r,'reason_codes':r or ['failover_allowed'],'policy_version':POLICY_VERSION}

def evaluate_observability(*,metrics_coverage:int,trace_coverage:int,log_integrity_verified:bool,sensitive_data_redacted:bool,alert_routes_tested:bool,slo_burn_alerts:bool)->dict:
    if not 0<=metrics_coverage<=100 or not 0<=trace_coverage<=100:raise ValueError('coverage must be between 0 and 100')
    r=[]
    if metrics_coverage<95:r.append('metrics_coverage_below_threshold')
    if trace_coverage<90:r.append('trace_coverage_below_threshold')
    if not log_integrity_verified:r.append('log_integrity_required')
    if not sensitive_data_redacted:r.append('sensitive_data_redaction_required')
    if not alert_routes_tested:r.append('alert_route_test_required')
    if not slo_burn_alerts:r.append('slo_burn_alerts_required')
    return {'allowed':not r,'reason_codes':r or ['observability_gate_passed'],'policy_version':POLICY_VERSION}

def evaluate_capacity(*,peak_rps:int,tested_rps:int,p95_latency_ms:int,error_rate_basis_points:int,search_corpus_millions:int,headroom_percent:int)->dict:
    if min(peak_rps,tested_rps,p95_latency_ms,error_rate_basis_points,search_corpus_millions,headroom_percent)<0:raise ValueError('capacity values cannot be negative')
    r=[]
    if tested_rps<peak_rps:r.append('peak_capacity_not_tested')
    if p95_latency_ms>500:r.append('p95_latency_above_limit')
    if error_rate_basis_points>10:r.append('error_rate_above_limit')
    if search_corpus_millions<1:r.append('large_corpus_test_required')
    if headroom_percent<30:r.append('capacity_headroom_below_threshold')
    return {'allowed':not r,'reason_codes':r or ['capacity_gate_passed'],'policy_version':POLICY_VERSION}

def evaluate_milestone_acceptance(*,archive_preservation_passed:bool,search_quality_passed:bool,offline_distribution_passed:bool,failover_passed:bool,observability_passed:bool,capacity_passed:bool,live_multi_region_validated:bool,external_preservation_audit:bool)->dict:
    checks={'archive_preservation':archive_preservation_passed,'search_quality':search_quality_passed,'offline_distribution':offline_distribution_passed,'failover':failover_passed,'observability':observability_passed,'capacity':capacity_passed}
    r=[f'{k}_required' for k,v in checks.items() if not v]
    portable=not r
    production=portable and live_multi_region_validated and external_preservation_audit
    if portable and not live_multi_region_validated:r.append('live_multi_region_validation_required_for_production')
    if portable and not external_preservation_audit:r.append('external_preservation_audit_required_for_production')
    outcome='passed' if production else ('conditional' if portable else 'failed')
    return {'outcome':outcome,'portable_ready':portable,'production_ready':production,'reason_codes':r or ['milestone_14_production_acceptance_passed'],'policy_version':POLICY_VERSION}
