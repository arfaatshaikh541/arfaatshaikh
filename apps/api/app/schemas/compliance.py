from pydantic import BaseModel, Field

class EvidenceValidationRequest(BaseModel):
    uri: str = Field(min_length=1, max_length=1200)
    sha256: str = Field(min_length=1, max_length=128)
    classification: str
    retention_days: int
    verified: bool = False

class ControlEvaluationRequest(BaseModel):
    framework_code: str
    implemented: bool
    independently_tested: bool
    evidence_verified: bool
    owner_assigned: bool
    exception_approved: bool = False

class RiskEvaluationRequest(BaseModel):
    likelihood: int
    impact: int
    treatment_plan_present: bool
    owner_assigned: bool
    accepted_by_authority: bool = False

class DisasterRecoveryRequest(BaseModel):
    rpo_minutes: int
    rto_minutes: int
    encrypted_backups: bool
    restore_test_passed: bool
    rollback_test_passed: bool
    evidence_verified: bool
    multi_region_required: bool
    multi_region_ready: bool

class EnterpriseReadinessRequest(BaseModel):
    control_failures: int = Field(ge=0)
    open_high_risks: int = Field(ge=0)
    overdue_evidence: int = Field(ge=0)
    disaster_recovery_ready: bool
    data_export_tested: bool
    data_deletion_tested: bool
    key_rotation_verified: bool
    secret_rotation_verified: bool
