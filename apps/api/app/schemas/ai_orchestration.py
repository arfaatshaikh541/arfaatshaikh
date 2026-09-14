from pydantic import BaseModel, Field, model_validator

class OrchestrationEvidenceInput(BaseModel):
    source_passage_id: str = Field(min_length=1)
    corpus_type: str = Field(min_length=1, max_length=40)
    exact_text: str = Field(min_length=1, max_length=20000)
    attribution: str = Field(min_length=1, max_length=500)
    evidence_sha256: str = Field(min_length=64, max_length=64)

class OrchestrationClaimInput(BaseModel):
    claim_type: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=6000)
    evidence_indices: list[int] = Field(min_length=1, max_length=12)

class OrchestrationEvaluateRequest(BaseModel):
    risk_level: str = Field(pattern="^(standard|sensitive|high_risk)$")
    evidence: list[OrchestrationEvidenceInput] = Field(min_length=1, max_length=50)
    claims: list[OrchestrationClaimInput] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def indices_are_bounded(self):
        upper = len(self.evidence) - 1
        if any(i < 0 or i > upper for claim in self.claims for i in claim.evidence_indices):
            raise ValueError("claim references unavailable evidence")
        return self
