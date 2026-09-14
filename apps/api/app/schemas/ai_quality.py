from pydantic import BaseModel, Field

class EvaluationRequest(BaseModel):
    expected_action: str = Field(pattern="^(answer|refuse|escalate)$")
    observed_action: str = Field(pattern="^(answer|refuse|escalate|error)$")
    response_text: str = Field(max_length=30000)
    evidence_fingerprints: list[str] = Field(default_factory=list, max_length=100)
    required_evidence_fingerprints: list[str] = Field(default_factory=list, max_length=100)
    forbidden_patterns: list[str] = Field(default_factory=list, max_length=100)
    risk_level: str = Field(default="low", pattern="^(low|medium|high|critical)$")

class RedTeamFindingRequest(BaseModel):
    attack_class: str = Field(min_length=1, max_length=80)
    severity: str = Field(pattern="^(low|medium|high|critical)$")
    status: str = Field(pattern="^(open|mitigated|accepted|false_positive)$")
    mitigation: str | None = Field(default=None, max_length=5000)

class ReleaseGateRequest(BaseModel):
    pass_rate: int = Field(ge=0, le=100)
    open_high_findings: int = Field(ge=0)
    open_critical_findings: int = Field(ge=0)
    dataset_approved: bool
