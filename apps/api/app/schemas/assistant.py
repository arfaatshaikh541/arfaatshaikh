from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class QuestionClassificationRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    language: str = Field(default="en", min_length=2, max_length=16)


class AssistantQueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    locale: str = Field(default="en", min_length=2, max_length=16)
    limit: int = Field(default=8, ge=1, le=20)


class EvidenceInput(BaseModel):
    chunk_id: str
    document_id: str
    corpus_type: str
    canonical_reference: str
    source_edition_id: str
    source_passage_id: str
    exact_text: str = Field(min_length=1)
    text_sha256: str = Field(min_length=64, max_length=64)
    attribution: str = Field(min_length=1)
    licence: str = Field(min_length=1)


class ClaimDraftInput(BaseModel):
    claim_type: str
    text: str = Field(min_length=1, max_length=6000)
    evidence_indices: list[int] = Field(min_length=1, max_length=12)


class AssembleAnswerRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    language: str = Field(default="en", min_length=2, max_length=16)
    evidence: list[EvidenceInput] = Field(min_length=1, max_length=50)
    claims: list[ClaimDraftInput] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def validate_indices(self):
        maximum = len(self.evidence) - 1
        if any(index < 0 or index > maximum for claim in self.claims for index in claim.evidence_indices):
            raise ValueError("claim references an unavailable evidence index")
        return self
