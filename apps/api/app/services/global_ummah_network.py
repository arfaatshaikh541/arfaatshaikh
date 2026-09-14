from __future__ import annotations
import hashlib,json,re
POLICY_VERSION="global-ummah-network-v1"
SHA=re.compile(r"^[0-9a-f]{64}$")
def _sha(v:str)->bool:return bool(SHA.fullmatch(v))
def _result(r:list[str],ok:str,**x)->dict:return {"allowed":not r,"reason_codes":r or [ok],"policy_version":POLICY_VERSION,**x}
def compute_federation_manifest(*,network_slug:str,member_ids:list[str],trust_policy_sha256:str,capabilities:list[str])->str:
 if not network_slug.strip() or not member_ids:raise ValueError("network and members required")
 if not _sha(trust_policy_sha256):raise ValueError("invalid trust policy fingerprint")
 body=json.dumps({"network":network_slug.strip(),"members":sorted(set(member_ids)),"trust":trust_policy_sha256,"capabilities":sorted(set(capabilities))},sort_keys=True,separators=(",",":"))
 return hashlib.sha256(body.encode()).hexdigest()
def evaluate_institution_federation(*,verified_institutions:int,independent_jurisdictions:int,trust_policy_published:bool,governance_council_active:bool,member_exit_process:bool,manifest_sha256:str)->dict:
 if min(verified_institutions,independent_jurisdictions)<0:raise ValueError("values cannot be negative")
 r=[]
 if verified_institutions<3:r.append("verified_institution_threshold_not_met")
 if independent_jurisdictions<2:r.append("jurisdiction_diversity_required")
 if not trust_policy_published:r.append("trust_policy_required")
 if not governance_council_active:r.append("federation_governance_required")
 if not member_exit_process:r.append("member_exit_process_required")
 if not _sha(manifest_sha256):r.append("valid_federation_manifest_required")
 return _result(r,"institution_federation_allowed",status="active" if not r else "restricted")
def evaluate_trusted_identity(*,institution_verified:bool,identity_assurance_level:int,mfa_enforced:bool,credential_rotation_days:int,revocation_supported:bool,proof_sha256:str)->dict:
 if min(identity_assurance_level,credential_rotation_days)<0:raise ValueError("values cannot be negative")
 r=[]
 if not institution_verified:r.append("verified_issuer_required")
 if identity_assurance_level<2:r.append("identity_assurance_too_low")
 if not mfa_enforced:r.append("mfa_required")
 if not 1<=credential_rotation_days<=365:r.append("credential_rotation_out_of_bounds")
 if not revocation_supported:r.append("credential_revocation_required")
 if not _sha(proof_sha256):r.append("valid_identity_proof_required")
 return _result(r,"trusted_identity_allowed")
def evaluate_interoperability_profile(*,open_standard_used:bool,schema_versioned:bool,backward_compatible:bool,conformance_tests_passed:bool,security_review_passed:bool,data_minimization:bool)->dict:
 r=[]
 if not open_standard_used:r.append("open_standard_required")
 if not schema_versioned:r.append("versioned_schema_required")
 if not backward_compatible:r.append("backward_compatibility_required")
 if not conformance_tests_passed:r.append("conformance_tests_required")
 if not security_review_passed:r.append("security_review_required")
 if not data_minimization:r.append("data_minimization_required")
 return _result(r,"interoperability_profile_allowed")
def evaluate_federated_search(*,participating_nodes:int,evidence_grounding_percent:int,source_attribution_percent:int,query_privacy_protected:bool,harmful_result_rate_basis_points:int,timeout_ms:int)->dict:
 if min(participating_nodes,evidence_grounding_percent,source_attribution_percent,harmful_result_rate_basis_points,timeout_ms)<0:raise ValueError("values cannot be negative")
 r=[]
 if participating_nodes<2:r.append("multiple_search_nodes_required")
 if evidence_grounding_percent<98:r.append("grounding_below_threshold")
 if source_attribution_percent<99:r.append("attribution_below_threshold")
 if not query_privacy_protected:r.append("query_privacy_required")
 if harmful_result_rate_basis_points>0:r.append("harmful_results_detected")
 if timeout_ms>3000:r.append("federated_search_latency_too_high")
 return _result(r,"federated_search_allowed")
def evaluate_data_sharing_agreement(*,purpose_limited:bool,consent_or_lawful_basis:bool,minimum_fields_only:bool,retention_days:int,cross_border_assessment:bool,deletion_supported:bool,audit_logging:bool)->dict:
 if retention_days<0:raise ValueError("retention cannot be negative")
 r=[]
 if not purpose_limited:r.append("purpose_limitation_required")
 if not consent_or_lawful_basis:r.append("lawful_basis_required")
 if not minimum_fields_only:r.append("field_minimization_required")
 if not 1<=retention_days<=2555:r.append("retention_out_of_bounds")
 if not cross_border_assessment:r.append("cross_border_assessment_required")
 if not deletion_supported:r.append("deletion_capability_required")
 if not audit_logging:r.append("audit_logging_required")
 return _result(r,"data_sharing_allowed")
def evaluate_cross_border_scholarship(*,institutions:int,qualified_scholars:int,methodology_published:bool,conflicts_disclosed:bool,minority_views_preserved:bool,translation_reviewed:bool,evidence_sha256:str)->dict:
 if min(institutions,qualified_scholars)<0:raise ValueError("values cannot be negative")
 r=[]
 if institutions<2:r.append("cross_institution_participation_required")
 if qualified_scholars<3:r.append("scholar_threshold_not_met")
 if not methodology_published:r.append("published_methodology_required")
 if not conflicts_disclosed:r.append("conflict_disclosure_required")
 if not minority_views_preserved:r.append("minority_views_preservation_required")
 if not translation_reviewed:r.append("translation_review_required")
 if not _sha(evidence_sha256):r.append("valid_scholarly_evidence_required")
 return _result(r,"cross_border_scholarship_allowed")
def evaluate_consent_receipt(*,subject_controlled:bool,granular_purposes:bool,withdrawal_supported:bool,receipt_sha256:str,expires_days:int)->dict:
 if expires_days<0:raise ValueError("expiry cannot be negative")
 r=[]
 if not subject_controlled:r.append("data_subject_control_required")
 if not granular_purposes:r.append("granular_consent_required")
 if not withdrawal_supported:r.append("withdrawal_support_required")
 if not _sha(receipt_sha256):r.append("valid_consent_receipt_required")
 if not 1<=expires_days<=730:r.append("consent_expiry_out_of_bounds")
 return _result(r,"consent_receipt_allowed")
def evaluate_network_resilience(*,healthy_regions:int,healthy_federation_nodes:int,replication_lag_seconds:int,rpo_seconds:int,rto_minutes:int,exercise_within_days:int,partition_recovery_verified:bool)->dict:
 if min(healthy_regions,healthy_federation_nodes,replication_lag_seconds,rpo_seconds,rto_minutes,exercise_within_days)<0:raise ValueError("values cannot be negative")
 r=[]
 if healthy_regions<2:r.append("multi_region_health_required")
 if healthy_federation_nodes<3:r.append("federation_node_quorum_required")
 if replication_lag_seconds>rpo_seconds:r.append("replication_lag_exceeds_rpo")
 if rpo_seconds>300:r.append("rpo_above_limit")
 if rto_minutes>30:r.append("rto_above_limit")
 if exercise_within_days>90:r.append("resilience_exercise_stale")
 if not partition_recovery_verified:r.append("partition_recovery_required")
 return _result(r,"network_resilience_allowed",status="ready" if not r else "blocked")
def evaluate_public_trust_report(*,metrics_defined:bool,correction_channel:bool,incident_disclosure:bool,independent_review:bool,publication_sha256:str,reporting_delay_days:int)->dict:
 if reporting_delay_days<0:raise ValueError("delay cannot be negative")
 r=[]
 if not metrics_defined:r.append("defined_metrics_required")
 if not correction_channel:r.append("public_correction_channel_required")
 if not incident_disclosure:r.append("incident_disclosure_required")
 if not independent_review:r.append("independent_review_required")
 if not _sha(publication_sha256):r.append("valid_publication_fingerprint_required")
 if reporting_delay_days>90:r.append("reporting_delay_too_long")
 return _result(r,"public_trust_report_allowed")
def evaluate_federation_audit(*,member_coverage_percent:int,critical_findings:int,evidence_integrity:bool,remediation_owners_assigned:bool,follow_up_days:int)->dict:
 if min(member_coverage_percent,critical_findings,follow_up_days)<0:raise ValueError("values cannot be negative")
 r=[]
 if member_coverage_percent<95:r.append("member_audit_coverage_below_threshold")
 if critical_findings:r.append("critical_findings_unresolved")
 if not evidence_integrity:r.append("audit_evidence_integrity_required")
 if not remediation_owners_assigned:r.append("remediation_ownership_required")
 if follow_up_days>90:r.append("audit_follow_up_too_slow")
 return _result(r,"federation_audit_allowed")
def evaluate_global_ummah_acceptance(*,federation_passed:bool,identity_passed:bool,interoperability_passed:bool,search_passed:bool,privacy_passed:bool,resilience_passed:bool,transparency_passed:bool,live_partner_interop_validated:bool,external_security_audit:bool,live_partition_exercise:bool)->dict:
 controls=[federation_passed,identity_passed,interoperability_passed,search_passed,privacy_passed,resilience_passed,transparency_passed]
 if not all(controls):return _result(["deterministic_control_failure"],"",outcome="failed",portable_ready=False,production_ready=False)
 prod=live_partner_interop_validated and external_security_audit and live_partition_exercise
 reasons=[] if prod else [x for x,v in [("live_partner_interoperability_unverified",live_partner_interop_validated),("external_security_audit_required",external_security_audit),("live_partition_exercise_required",live_partition_exercise)] if not v]
 return {"allowed":prod,"reason_codes":reasons or ["global_ummah_network_accepted"],"policy_version":POLICY_VERSION,"outcome":"passed" if prod else "conditional","portable_ready":True,"production_ready":prod}
