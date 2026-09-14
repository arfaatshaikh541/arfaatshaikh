from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

SOURCE_TYPES = {
    "quran", "hadith", "tafsir", "fiqh", "aqidah", "seerah", "history", "arabic",
    "comparative_religion", "modern_analysis", "other",
}


class LicenceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    spdx_identifier: str | None = Field(default=None, max_length=80)
    version: str | None = Field(default=None, max_length=40)
    licence_url: str | None = Field(default=None, max_length=500)
    copyright_holder: str | None = Field(default=None, max_length=240)
    redistribution_allowed: bool = False
    modification_allowed: bool = False
    commercial_use_allowed: bool = False
    attribution_text: str | None = None
    restrictions: str | None = None


class SourceCreate(BaseModel):
    canonical_title: str = Field(min_length=2, max_length=500)
    original_title: str | None = Field(default=None, max_length=500)
    source_type: str
    primary_language: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
    author_name: str | None = Field(default=None, max_length=300)
    compiler_name: str | None = Field(default=None, max_length=300)
    description: str | None = None

    @model_validator(mode="after")
    def validate_type(self) -> "SourceCreate":
        if self.source_type not in SOURCE_TYPES:
            raise ValueError("Unsupported source type")
        return self


class EditionCreate(BaseModel):
    licence_id: UUID | None = None
    edition_key: str = Field(pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$", min_length=2, max_length=120)
    edition_statement: str | None = Field(default=None, max_length=300)
    publisher: str | None = Field(default=None, max_length=300)
    publication_year: int | None = Field(default=None, ge=500, le=2200)
    editor_name: str | None = Field(default=None, max_length=300)
    translator_name: str | None = Field(default=None, max_length=300)
    language: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
    isbn: str | None = Field(default=None, max_length=32)
    citation_format: str = Field(min_length=5)


class AcquisitionCreate(BaseModel):
    method: str
    acquired_from: str = Field(min_length=3, max_length=500)
    acquired_at: datetime
    evidence_reference: str | None = Field(default=None, max_length=500)
    terms_snapshot_object_key: str | None = Field(default=None, max_length=500)


class SourceView(BaseModel):
    id: UUID
    canonical_title: str
    original_title: str | None
    source_type: str
    primary_language: str
    author_name: str | None
    compiler_name: str | None
    authority_status: str


class EditionView(BaseModel):
    id: UUID
    source_id: UUID
    licence_id: UUID | None
    edition_key: str
    language: str
    publisher: str | None
    publication_year: int | None
    ingestion_status: str
    review_status: str
    approved_for_retrieval: bool


class IntegrityVerifyRequest(BaseModel):
    object_key: str = Field(min_length=1, max_length=500)
    algorithm: str = Field(pattern=r"^(sha256|sha512)$")


class LegalReviewUpdate(BaseModel):
    decision: str = Field(pattern=r"^(approved|changes_requested|rejected)$")
    rationale: str = Field(min_length=10, max_length=4000)


class AuthorityUpdate(BaseModel):
    status: str = Field(pattern=r"^(candidate|approved|restricted|rejected)$")
    rationale: str = Field(min_length=10, max_length=4000)


class IngestionTransition(BaseModel):
    status: str = Field(pattern=r"^(validating|ready|blocked|retired)$")
    rationale: str = Field(min_length=10, max_length=4000)


class ReviewAssignmentCreate(BaseModel):
    reviewer_user_id: UUID
    review_domain: str = Field(pattern=r"^[a-z][a-z0-9_]{2,59}$")
    due_at: datetime | None = None


class ReviewDecisionCreate(BaseModel):
    decision: str = Field(pattern=r"^(approved|changes_requested|rejected)$")
    rationale: str = Field(min_length=20, max_length=8000)
    valid_until: datetime | None = None


class PassageCreate(BaseModel):
    passage_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,239}$")
    language: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
    source_locator: str = Field(min_length=1, max_length=500)
    citation_label: str = Field(min_length=2, max_length=500)
    content: str = Field(min_length=1, max_length=200000)


class AttributionUpsert(BaseModel):
    language: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
    display_text: str = Field(min_length=2, max_length=4000)
    source_url: str | None = Field(default=None, max_length=500)
    licence_url: str | None = Field(default=None, max_length=500)


class PassageView(BaseModel):
    id: UUID
    edition_id: UUID
    passage_key: str
    version: int
    language: str
    source_locator: str
    citation_label: str
    content: str
    content_sha256: str

class SourceClaimCreate(BaseModel):
    claim_text: str = Field(min_length=2, max_length=20000)
    language: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
    methodology: str | None = Field(default=None, max_length=120)


class ClaimPassageLinkCreate(BaseModel):
    passage_id: UUID
    relation_type: str = Field(pattern=r"^(supports|qualifies|disputes|contextualises)$")
    citation_start: int = Field(ge=0)
    citation_end: int = Field(gt=0)
    rationale: str = Field(min_length=5, max_length=4000)

    @model_validator(mode="after")
    def validate_span(self) -> "ClaimPassageLinkCreate":
        if self.citation_end <= self.citation_start:
            raise ValueError("citation_end must be greater than citation_start")
        return self


class PassageCorrectionCreate(BaseModel):
    reason: str = Field(min_length=10, max_length=8000)


class PassageCorrectionDecision(BaseModel):
    status: str = Field(pattern=r"^(accepted|rejected)$")
    replacement_passage_id: UUID | None = None
    decision_notes: str = Field(min_length=10, max_length=8000)


class SupersessionCreate(BaseModel):
    replacement_edition_id: UUID
    rationale: str = Field(min_length=10, max_length=8000)


class ApprovalPolicyCreate(BaseModel):
    source_type: str
    policy_version: int = Field(ge=1)
    minimum_reviewers: int = Field(ge=1, le=12)
    require_legal_approval: bool = True
    require_integrity_verification: bool = True
    required_review_domains: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_source_type(self) -> "ApprovalPolicyCreate":
        if self.source_type not in SOURCE_TYPES:
            raise ValueError("Unsupported source type")
        if len(set(self.required_review_domains)) != len(self.required_review_domains):
            raise ValueError("Review domains must be unique")
        return self

class ReviewerQueueItem(BaseModel):
    assignment_id: UUID
    edition_id: UUID
    source_title: str
    edition_key: str
    review_domain: str
    status: str
    due_at: datetime | None


class ProvenanceCitationView(BaseModel):
    link_id: UUID
    passage_id: UUID
    relation_type: str
    citation_start: int
    citation_end: int
    citation_text: str
    citation_label: str
    source_locator: str
    rationale: str


class ProvenanceClaimView(BaseModel):
    claim_id: UUID
    claim_text: str
    language: str
    claim_status: str
    methodology: str | None
    citations: list[ProvenanceCitationView]


class RetrievalEvaluationView(BaseModel):
    eligible: bool
    failed_gates: list[str]
    policy_id: UUID | None
    policy_version: int | None
    required_review_domains: list[str]
    approved_reviewers: int


class AuditExportRequest(BaseModel):
    edition_id: UUID | None = None
    format: str = Field(pattern=r"^(json|csv)$")


class RegistryDashboardView(BaseModel):
    source_count: int
    edition_count: int
    retrieval_eligible_count: int
    pending_review_count: int
    open_correction_count: int
