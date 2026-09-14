from pydantic import BaseModel, Field

class TranslationAlignmentRequest(BaseModel):
    source_language: str = Field(pattern="^(ar|en|ur|hi|transliteration)$")
    target_language: str = Field(pattern="^(ar|en|ur|hi|transliteration)$")
    source_text: str = Field(min_length=1, max_length=20000)
    target_text: str = Field(min_length=1, max_length=20000)
    evidence_sha256: str = Field(min_length=64, max_length=64)
    preserves_citations: bool
    alignment_confidence: float = Field(ge=0, le=1)

class ClaimIdentityRequest(BaseModel):
    source_claim_ids: list[str] = Field(min_length=1, max_length=50)
    target_claim_ids: list[str] = Field(min_length=1, max_length=50)
