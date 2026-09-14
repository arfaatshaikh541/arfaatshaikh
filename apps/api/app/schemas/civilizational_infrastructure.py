from pydantic import BaseModel, Field
class ArchiveDepositRequest(BaseModel):
 content_type:str; manifest_sha256:str; source_sha256:str; signature_verified:bool; scholarly_approved:bool; retention_years:int; immutable_storage:bool
class ArchiveManifestRequest(BaseModel):
 archive_slug:str; version:str; objects:list[dict[str,object]]
class ReplicaSetRequest(BaseModel):
 replica_regions:set[str]; replica_count:int=Field(ge=0); independent_providers:int=Field(ge=0); air_gapped_copy:bool; fixity_verified:bool
class FixityCheckRequest(BaseModel):
 expected_sha256:str; observed_sha256:str; objects_expected:int=Field(ge=0); objects_verified:int=Field(ge=0); unreadable_objects:int=Field(ge=0)
class SemanticIndexRequest(BaseModel):
 content_type:str; source_coverage_percent:int=Field(ge=0,le=100); evidence_linked:bool; embedding_model_fingerprint:str; index_fingerprint:str; scholarly_reviewed:bool
class SearchReleaseRequest(BaseModel):
 precision_at_10:int=Field(ge=0,le=100); recall_at_10:int=Field(ge=0,le=100); grounding_rate:int=Field(ge=0,le=100); harmful_result_rate:int=Field(ge=0,le=100); arabic_evaluation_passed:bool; bias_reviewed:bool
class OfflinePackageRequest(BaseModel):
 manifest_sha256:str; package_sha256:str; signature_verified:bool; expires_in_days:int; max_size_mb:int; contains_personal_data:bool; revocation_list_embedded:bool
class OfflineUpdateRequest(BaseModel):
 base_version:str; target_version:str; delta_sha256:str; signature_verified:bool; rollback_available:bool; free_space_mb:int=Field(ge=0); required_space_mb:int=Field(ge=0)
class FailoverRequest(BaseModel):
 healthy_regions:int=Field(ge=0); replication_lag_seconds:int=Field(ge=0); rpo_seconds:int=Field(ge=0); rto_seconds:int=Field(ge=0); last_drill_days:int=Field(ge=0); data_loss_detected:bool
class ObservabilityRequest(BaseModel):
 metrics_coverage:int=Field(ge=0,le=100); trace_coverage:int=Field(ge=0,le=100); log_integrity_verified:bool; sensitive_data_redacted:bool; alert_routes_tested:bool; slo_burn_alerts:bool
class CapacityRequest(BaseModel):
 peak_rps:int=Field(ge=0); tested_rps:int=Field(ge=0); p95_latency_ms:int=Field(ge=0); error_rate_basis_points:int=Field(ge=0); search_corpus_millions:int=Field(ge=0); headroom_percent:int=Field(ge=0)
class Milestone14AcceptanceRequest(BaseModel):
 archive_preservation_passed:bool; search_quality_passed:bool; offline_distribution_passed:bool; failover_passed:bool; observability_passed:bool; capacity_passed:bool; live_multi_region_validated:bool; external_preservation_audit:bool
