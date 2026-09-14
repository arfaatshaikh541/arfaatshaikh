from pydantic import BaseModel,Field
class ZakatFundRequest(BaseModel):
 scholarly_policy_approved:bool; independent_trustees:int=Field(ge=0); segregated_accounts:bool; audit_frequency_days:int=Field(ge=0); beneficiary_categories_configured:bool; administrative_cost_percent:int=Field(ge=0,le=100); evidence_sha256:str
class ZakatDistributionRequest(BaseModel):
 eligibility_verified:bool; duplicate_checked:bool; conflict_screened:bool; amount_minor:int=Field(ge=0); currency:str; available_minor:int=Field(ge=0); restricted_purpose_respected:bool; approval_count:int=Field(ge=0)
class WaqfAssetRequest(BaseModel):
 ownership_verified:bool; perpetual_purpose_declared:bool; valuation_current:bool; maintenance_plan:bool; conflict_of_interest_cleared:bool; asset_sha256:str
class AidCaseFingerprintRequest(BaseModel):
 case_reference:str; need_categories:list[str]=Field(min_length=1); region_code:str; evidence_fingerprints:list[str]=[]
class BeneficiaryCaseRequest(BaseModel):
 identity_minimized:bool; consent_or_lawful_basis:bool; need_assessment_complete:bool; safeguarding_screened:bool; duplicate_risk_percent:int=Field(ge=0,le=100); case_fingerprint:str; retention_days:int=Field(ge=0)
class AidProgramRequest(BaseModel):
 verified_partner_count:int=Field(ge=0); restricted_funds_segregated:bool; monitoring_plan:bool; complaints_channel:bool; anti_exploitation_controls:bool; open_critical_findings:int=Field(ge=0); programme_evidence_sha256:str
class MosqueServiceRequest(BaseModel):
 verified_institution:bool; service_type:str; qualified_lead:bool; accessibility_supported:bool; child_safeguarding_required:bool; child_safeguarding_passed:bool; privacy_notice_published:bool; complaints_process:bool
class VolunteerAssignmentRequest(BaseModel):
 identity_verified:bool; role_training_complete:bool; background_check_required:bool; background_check_passed:bool; conflict_disclosed:bool; maximum_weekly_hours:int=Field(ge=0); safeguarding_code_accepted:bool
class ServiceReferralRequest(BaseModel):
 consent_captured:bool; minimum_data_shared:bool; receiving_provider_verified:bool; urgent_risk:bool; urgent_escalation_available:bool; referral_evidence_sha256:str
class CrisisResponseRequest(BaseModel):
 incident_command_assigned:bool; verified_partner_count:int=Field(ge=0); beneficiary_safeguarding:bool; stock_or_capacity_verified:bool; communications_verified:bool; financial_controls_active:bool; open_critical_blockers:int=Field(ge=0)
class PublicServiceAnalyticsRequest(BaseModel):
 k_anonymity:int=Field(ge=0); minimum_group_size:int=Field(ge=0); location_precision_reduced:bool; personal_data_removed:bool; beneficiary_consent_or_basis:bool; bias_reviewed:bool; publication_sha256:str
class UmmahServicesAcceptanceRequest(BaseModel):
 zakat_waqf_governance_passed:bool; humanitarian_safeguarding_passed:bool; mosque_services_passed:bool; crisis_readiness_passed:bool; privacy_analytics_passed:bool; live_disbursement_validated:bool; external_fiduciary_audit:bool; live_crisis_exercise:bool
