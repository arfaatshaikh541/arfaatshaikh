from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class HadithCollectionCreate(BaseModel):
    source_edition_id: UUID
    collection_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9-]+$")
    arabic_title: str = Field(min_length=1, max_length=300)
    display_title: str = Field(min_length=1, max_length=300)
    compiler_name: str = Field(min_length=1, max_length=300)


class HadithBookCreate(BaseModel):
    book_number: int = Field(gt=0)
    arabic_title: str = Field(min_length=1, max_length=300)
    display_title: str = Field(min_length=1, max_length=300)
    source_passage_id: UUID


class HadithChapterCreate(BaseModel):
    chapter_number: int = Field(gt=0)
    arabic_title: str = Field(min_length=1, max_length=500)
    display_title: str = Field(min_length=1, max_length=500)
    source_passage_id: UUID


class HadithNarrationCreate(BaseModel):
    book_id: UUID
    chapter_id: UUID | None = None
    collection_hadith_number: int = Field(gt=0)
    arabic_matn: str = Field(min_length=1)
    source_passage_id: UUID

    @field_validator("arabic_matn")
    @classmethod
    def reject_latin_letters(cls, value: str) -> str:
        if any("A" <= c <= "Z" or "a" <= c <= "z" for c in value):
            raise ValueError("Arabic matn must not contain Latin letters")
        return value


class HadithNarratorCreate(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=300)
    arabic_name: str = Field(min_length=1, max_length=300)
    disambiguation_note: str | None = None
    source_passage_id: UUID | None = None


class HadithIsnadNodeCreate(BaseModel):
    narrator_id: UUID | None = None
    position: int = Field(gt=0)
    transmitted_name: str = Field(min_length=1, max_length=300)
    transmission_term: str | None = Field(default=None, max_length=120)
    source_passage_id: UUID


class HadithGradingCreate(BaseModel):
    grader_name: str = Field(min_length=1, max_length=300)
    grading_label: str = Field(pattern=r"^(sahih|hasan|daif|mawdu|mixed|ungraded|other)$")
    grading_text: str = Field(min_length=1)
    methodology_note: str | None = None
    source_passage_id: UUID


class HadithCollectionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    collection_key: str
    arabic_title: str
    display_title: str
    compiler_name: str


class HadithNarrationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    canonical_reference: str
    collection_hadith_number: int
    arabic_matn: str

class HadithImportManifestCreate(BaseModel):
    collection_id: UUID
    manifest_version: str = Field(min_length=1, max_length=32)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_book_count: int = Field(gt=0, le=10000)
    expected_chapter_count: int = Field(ge=0, le=100000)
    expected_narration_count: int = Field(gt=0, le=1000000)
    require_complete_isnad: bool = False


class HadithImportNarrationCreate(BaseModel):
    book_number: int = Field(gt=0)
    book_arabic_title: str = Field(min_length=1, max_length=300)
    book_display_title: str = Field(min_length=1, max_length=300)
    book_source_passage_id: UUID
    chapter_number: int | None = Field(default=None, gt=0)
    chapter_arabic_title: str | None = Field(default=None, max_length=500)
    chapter_display_title: str | None = Field(default=None, max_length=500)
    chapter_source_passage_id: UUID | None = None
    collection_hadith_number: int = Field(gt=0)
    arabic_matn: str = Field(min_length=1)
    source_passage_id: UUID

    @field_validator("arabic_matn")
    @classmethod
    def reject_latin_matn(cls, value: str) -> str:
        if any("A" <= c <= "Z" or "a" <= c <= "z" for c in value):
            raise ValueError("Arabic matn must not contain Latin letters")
        return value

    @field_validator("chapter_arabic_title", "chapter_display_title")
    @classmethod
    def reject_blank_optional_title(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Chapter title cannot be blank")
        return value


class HadithImportIsnadNodeCreate(BaseModel):
    narrator_id: UUID | None = None
    position: int = Field(gt=0, le=1000)
    transmitted_name: str = Field(min_length=1, max_length=300)
    transmission_term: str | None = Field(default=None, max_length=120)
    source_passage_id: UUID


class HadithDuplicateResolutionCreate(BaseModel):
    resolution: str = Field(pattern=r"^(not_duplicate|confirmed_duplicate|replace_existing)$")
    rationale: str = Field(min_length=10, max_length=4000)


class HadithImportReviewAssignmentCreate(BaseModel):
    reviewer_user_id: UUID
    review_domain: str = Field(pattern=r"^(hadith_text|isnad|source_provenance)$")
    due_at: object | None = None


class HadithImportReviewCreate(BaseModel):
    decision: str = Field(pattern=r"^(approved|changes_requested|rejected)$")
    rationale: str = Field(min_length=10, max_length=4000)


class HadithImportBatchView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    collection_id: UUID
    manifest_version: str
    manifest_sha256: str
    expected_book_count: int
    expected_chapter_count: int
    expected_narration_count: int
    require_complete_isnad: bool
    status: str
    validation_summary: str | None

class HadithTranslationEditionCreate(BaseModel):
    source_edition_id: UUID
    translation_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9-]+$")
    language: str = Field(min_length=2, max_length=16)
    translator_name: str = Field(min_length=1, max_length=300)
    publisher_name: str | None = Field(default=None, max_length=300)
    attribution_text: str = Field(min_length=5, max_length=2000)


class HadithTranslationImportManifestCreate(BaseModel):
    translation_edition_id: UUID
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_record_count: int = Field(gt=0, le=1000000)


class HadithTranslationImportItemCreate(BaseModel):
    narration_id: UUID
    translated_text: str = Field(min_length=1)
    source_passage_id: UUID


class HadithGradingImportManifestCreate(BaseModel):
    collection_id: UUID
    source_edition_id: UUID
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_record_count: int = Field(gt=0, le=1000000)


class HadithGradingImportItemCreate(BaseModel):
    narration_id: UUID
    grader_name: str = Field(min_length=1, max_length=300)
    grading_label: str = Field(pattern=r"^(sahih|hasan|daif|mawdu|mixed|ungraded|other)$")
    grading_text: str = Field(min_length=1)
    methodology_note: str | None = None
    source_passage_id: UUID


class HadithGovernedReviewCreate(BaseModel):
    decision: str = Field(pattern=r"^(approved|rejected)$")
    rationale: str = Field(min_length=10, max_length=4000)


class HadithBookView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    book_number: int
    arabic_title: str
    display_title: str


class HadithChapterView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    chapter_number: int
    arabic_title: str
    display_title: str


class HadithTranslationView(BaseModel):
    translation_key: str
    language: str
    translator_name: str
    attribution_text: str
    translated_text: str


class HadithGradingView(BaseModel):
    grader_name: str
    grading_label: str
    grading_text: str
    methodology_note: str | None


class HadithReadingNarrationView(BaseModel):
    id: UUID
    canonical_reference: str
    collection_hadith_number: int
    arabic_matn: str
    translations: list[HadithTranslationView]
    gradings: list[HadithGradingView]


class HadithChapterReadingView(BaseModel):
    collection_key: str
    collection_title: str
    book_number: int
    book_title: str
    chapter_number: int
    chapter_title: str
    narrations: list[HadithReadingNarrationView]

class HadithSearchResultView(BaseModel):
    id: UUID
    canonical_reference: str
    collection_key: str
    collection_title: str
    book_number: int
    chapter_number: int | None
    arabic_matn: str
    grading_labels: list[str]


class HadithIsnadNodeView(BaseModel):
    position: int
    narrator_id: UUID | None
    transmitted_name: str
    transmission_term: str | None


class HadithNarratorProfileView(BaseModel):
    id: UUID
    canonical_name: str
    arabic_name: str
    disambiguation_note: str | None
    aliases: list[str]
    source_passage_id: UUID | None


class HadithBookmarkCreate(BaseModel):
    narration_id: UUID
    note: str | None = Field(default=None, max_length=2000)


class HadithBookmarkView(BaseModel):
    id: UUID
    narration_id: UUID
    canonical_reference: str
    note: str | None


class HadithHistoryCreate(BaseModel):
    narration_id: UUID


class HadithHistoryView(BaseModel):
    narration_id: UUID
    canonical_reference: str
    last_read_at: object
    read_count: int


class HadithCitationExportCreate(BaseModel):
    narration_id: UUID
    format: str = Field(pattern=r"^(json|csv|plain_text)$")
