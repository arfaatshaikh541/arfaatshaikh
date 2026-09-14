from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TafsirAuthorCreate(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=300)
    arabic_name: str = Field(min_length=1, max_length=300)
    aliases_text: str | None = None
    birth_year_ah: int | None = Field(default=None, ge=1)
    death_year_ah: int | None = Field(default=None, ge=1)
    methodology_note: str | None = None
    source_passage_id: UUID


class TafsirCollectionCreate(BaseModel):
    collection_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9-]+$")
    arabic_title: str = Field(min_length=1, max_length=400)
    display_title: str = Field(min_length=1, max_length=400)
    author_id: UUID
    description: str | None = None


class TafsirEditionCreate(BaseModel):
    collection_id: UUID
    source_edition_id: UUID
    edition_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9-]+$")
    publisher_name: str | None = Field(default=None, max_length=300)
    publication_year: str | None = Field(default=None, max_length=32)
    language: str = Field(default="ar", min_length=2, max_length=16)
    attribution_text: str = Field(min_length=5, max_length=2000)


class TafsirVolumeCreate(BaseModel):
    volume_number: int = Field(gt=0)
    title: str | None = Field(default=None, max_length=400)
    source_passage_id: UUID


class TafsirSectionCreate(BaseModel):
    volume_id: UUID | None = None
    section_key: str = Field(min_length=1, max_length=180)
    section_type: str = Field(pattern=r"^(surah|ayah|ayah_range|introduction|appendix|editorial_note)$")
    title: str | None = Field(default=None, max_length=500)
    sort_order: int = 0
    source_passage_id: UUID


class TafsirEntryCreate(BaseModel):
    section_id: UUID | None = None
    surah_number: int = Field(ge=1, le=114)
    start_ayah_number: int | None = Field(default=None, gt=0)
    end_ayah_number: int | None = Field(default=None, gt=0)
    entry_type: str = Field(pattern=r"^(surah|ayah|ayah_range|introduction|appendix|editorial_note)$")
    arabic_text: str = Field(min_length=1)
    source_passage_id: UUID

    @field_validator("arabic_text")
    @classmethod
    def reject_latin_letters(cls, value: str) -> str:
        if any("A" <= c <= "Z" or "a" <= c <= "z" for c in value):
            raise ValueError("Arabic tafsir text must not contain Latin letters")
        return value

    @model_validator(mode="after")
    def validate_range(self):
        if self.entry_type in {"ayah", "ayah_range"} and self.start_ayah_number is None:
            raise ValueError("Ayah commentary requires a start ayah")
        if self.end_ayah_number is not None and self.start_ayah_number is not None and self.end_ayah_number < self.start_ayah_number:
            raise ValueError("End ayah cannot precede start ayah")
        return self


class TafsirTranslationEditionCreate(BaseModel):
    tafsir_edition_id: UUID
    source_edition_id: UUID
    translation_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9-]+$")
    language: str = Field(min_length=2, max_length=16)
    translator_name: str = Field(min_length=1, max_length=300)
    publisher_name: str | None = Field(default=None, max_length=300)
    attribution_text: str = Field(min_length=5, max_length=2000)


class TafsirTranslationCreate(BaseModel):
    translation_edition_id: UUID
    tafsir_entry_id: UUID
    translated_text: str = Field(min_length=1)
    source_passage_id: UUID


class TafsirAuthorView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    canonical_name: str
    arabic_name: str
    methodology_note: str | None


class TafsirCollectionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    collection_key: str
    arabic_title: str
    display_title: str
    author_id: UUID


class TafsirEntryView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    canonical_reference: str
    surah_number: int
    start_ayah_number: int | None
    end_ayah_number: int | None
    entry_type: str
    arabic_text: str

class TafsirImportBatchCreate(BaseModel):
    edition_id: UUID
    manifest_version: str = Field(min_length=1, max_length=32)
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_volume_count: int = Field(ge=0)
    expected_section_count: int = Field(ge=0)
    expected_entry_count: int = Field(gt=0)


class TafsirImportEntryCreate(BaseModel):
    volume_number: int | None = Field(default=None, gt=0)
    volume_title: str | None = Field(default=None, max_length=400)
    volume_source_passage_id: UUID | None = None
    section_key: str | None = Field(default=None, max_length=180)
    section_type: str | None = Field(default=None, pattern=r"^(surah|ayah|ayah_range|introduction|appendix|editorial_note)$")
    section_title: str | None = Field(default=None, max_length=500)
    section_sort_order: int = 0
    section_source_passage_id: UUID | None = None
    surah_number: int = Field(ge=1, le=114)
    start_ayah_number: int | None = Field(default=None, gt=0)
    end_ayah_number: int | None = Field(default=None, gt=0)
    entry_type: str = Field(pattern=r"^(surah|ayah|ayah_range|introduction|appendix|editorial_note)$")
    arabic_text: str = Field(min_length=1)
    source_passage_id: UUID

    @field_validator("arabic_text")
    @classmethod
    def reject_latin(cls, value: str) -> str:
        if any(c.isascii() and c.isalpha() for c in value):
            raise ValueError("Arabic tafsir text must not contain Latin letters")
        return value

    @model_validator(mode="after")
    def validate_shape(self):
        if self.entry_type in {"ayah", "ayah_range"} and self.start_ayah_number is None:
            raise ValueError("Ayah commentary requires a start ayah")
        if self.end_ayah_number is not None and self.start_ayah_number is not None and self.end_ayah_number < self.start_ayah_number:
            raise ValueError("End ayah cannot precede start ayah")
        if self.volume_number is None and self.volume_source_passage_id is not None:
            raise ValueError("Volume provenance requires a volume number")
        if self.section_key is None and any(v is not None for v in (self.section_type, self.section_title, self.section_source_passage_id)):
            raise ValueError("Section metadata requires a section key")
        return self


class TafsirImportReviewAssignmentCreate(BaseModel):
    reviewer_user_id: UUID
    review_domain: str = Field(pattern=r"^(tafsir_text|source_provenance|arabic_language)$")
    due_at: object | None = None


class TafsirImportReviewCreate(BaseModel):
    decision: str = Field(pattern=r"^(approved|changes_requested|rejected)$")
    rationale: str = Field(min_length=5, max_length=4000)

class TafsirTranslationImportBatchCreate(BaseModel):
    translation_edition_id: UUID
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_translation_count: int = Field(gt=0)


class TafsirTranslationImportItemCreate(BaseModel):
    tafsir_entry_id: UUID
    translated_text: str = Field(min_length=1)
    source_passage_id: UUID

class KnowledgeTopicCreate(BaseModel):
    topic_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9-]+$")
    parent_topic_id: UUID | None = None
    english_name: str = Field(min_length=1, max_length=240)
    arabic_name: str = Field(min_length=1, max_length=240)
    description: str | None = None
    sort_order: int = Field(default=0, ge=0)
    source_passage_id: UUID


class KnowledgeTopicAliasCreate(BaseModel):
    language: str = Field(min_length=2, max_length=16)
    alias: str = Field(min_length=1, max_length=240)


class KnowledgeCrossReferenceCreate(BaseModel):
    source_type: str = Field(pattern=r"^(quran_ayah|hadith_narration|tafsir_entry|topic)$")
    source_entity_id: UUID
    target_type: str = Field(pattern=r"^(quran_ayah|hadith_narration|tafsir_entry|topic)$")
    target_entity_id: UUID
    relationship_type: str = Field(pattern=r"^(explains|supports|contextualises|parallel|topic_membership|linguistic_note|historical_context|asbab_al_nuzul|editorial_link)$")
    rationale: str = Field(min_length=5, max_length=4000)
    evidence_passage_id: UUID
    editorial_confidence: int = Field(default=100, ge=0, le=100)

    @model_validator(mode="after")
    def reject_self_link(self):
        if self.source_type == self.target_type and self.source_entity_id == self.target_entity_id:
            raise ValueError("A cross-reference cannot link an entity to itself")
        return self


class KnowledgeCrossReferenceReview(BaseModel):
    decision: str = Field(pattern=r"^(approved|rejected)$")
    rationale: str = Field(min_length=5, max_length=4000)


class TafsirSearchQuery(BaseModel):
    q: str = Field(min_length=2, max_length=200)
    collection: str | None = None
    author_id: UUID | None = None
    topic: str | None = None
    surah_number: int | None = Field(default=None, ge=1, le=114)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

class TafsirBookmarkCreate(BaseModel):
    tafsir_entry_id: UUID
    note: str | None = Field(default=None, max_length=4000)

class TafsirStudyNoteCreate(BaseModel):
    tafsir_entry_id: UUID
    title: str | None = Field(default=None, max_length=240)
    body: str = Field(min_length=1, max_length=20000)

class TafsirStudyCollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4000)

class TafsirStudyCollectionItemCreate(BaseModel):
    tafsir_entry_id: UUID
    sort_order: int = Field(default=0, ge=0)

class TafsirStudyProgressUpdate(BaseModel):
    tafsir_entry_id: UUID
    status: str = Field(pattern=r"^(not_started|in_progress|completed)$")
    progress_percent: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def completed_means_one_hundred(self):
        if self.status == "completed" and self.progress_percent != 100:
            raise ValueError("Completed progress must be 100 percent")
        return self
