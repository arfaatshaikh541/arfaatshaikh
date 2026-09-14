from pydantic import BaseModel,Field
class ScholarlyCouncilRequest(BaseModel):
 active_scholars:int=Field(ge=0); independent_institutions:int=Field(ge=0); conflict_policy_published:bool; minority_views_preserved:bool; quorum_percent:int=Field(ge=0,le=100); evidence_sha256:str
class ScholarlyDecisionRequest(BaseModel):
 content_type:str; reviewer_count:int=Field(ge=0); independent_reviewer_count:int=Field(ge=0); quorum_met:bool; evidence_linked:bool; dissent_recorded:bool; decision_sha256:str
class ProvenanceLineageRequest(BaseModel):
 canonical_id:str; version:str; parent_fingerprints:list[str]=[]; evidence_fingerprints:list[str]=[]; payload_sha256:str
class ProvenanceReleaseRequest(BaseModel):
 lineage_sha256:str; source_count:int=Field(ge=0); primary_source_count:int=Field(ge=0); unresolved_breaks:int=Field(ge=0); supersession_declared:bool; sensitive_content:bool; scholarly_approved:bool
class ResearchProjectRequest(BaseModel):
 institution_count:int=Field(ge=0); lead_researcher_verified:bool; methodology_published:bool; data_management_plan:bool; ethics_review_required:bool; ethics_review_passed:bool; open_conflicts:int=Field(ge=0)
class CurriculumReleaseRequest(BaseModel):
 learning_objectives_covered:int=Field(ge=0); total_learning_objectives:int=Field(gt=0); evidence_coverage_percent:int=Field(ge=0,le=100); assessment_validated:bool; accessibility_reviewed:bool; child_safe:bool; scholarly_reviewed:bool
class CertificationAwardRequest(BaseModel):
 identity_verified:bool; assessment_score:int=Field(ge=0,le=100); minimum_score:int=Field(ge=0,le=100); proctoring_required:bool; proctoring_verified:bool; attempt_integrity_verified:bool; certificate_fingerprint:str
class CommunityContributionRequest(BaseModel):
 content_type:str; evidence_count:int=Field(ge=0); moderation_passed:bool; duplicate_checked:bool; privacy_safe:bool; scholarly_reviewed:bool; author_consent:bool
class StewardshipTransferRequest(BaseModel):
 current_steward_active:bool; new_steward_verified:bool; asset_inventory_complete:bool; credential_rotation_planned:bool; audit_handover_complete:bool; open_critical_incidents:int=Field(ge=0)
class AnalyticsReleaseRequest(BaseModel):
 k_anonymity:int=Field(ge=0); minimum_group_size:int=Field(ge=0); personal_data_removed:bool; consent_basis_verified:bool; bias_reviewed:bool; metric_definitions_published:bool; export_fingerprint:str
class APIEcosystemRequest(BaseModel):
 active_products:int=Field(ge=0); deprecated_without_successor:int=Field(ge=0); sdk_coverage_percent:int=Field(ge=0,le=100); documentation_coverage_percent:int=Field(ge=0,le=100); breaking_change_notice_days:int=Field(ge=0); security_review_passed:bool
class PlatformMaturityRequest(BaseModel):
 scholarly_governance_passed:bool; provenance_passed:bool; research_collaboration_passed:bool; curriculum_passed:bool; community_stewardship_passed:bool; analytics_passed:bool; api_ecosystem_passed:bool; live_operations_validated:bool; external_scholarly_audit:bool
