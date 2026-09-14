from __future__ import annotations

from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TafsirAuthor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_authors"
    __table_args__ = (UniqueConstraint("canonical_name"),)

    canonical_name: Mapped[str] = mapped_column(String(300), nullable=False)
    arabic_name: Mapped[str] = mapped_column(String(300), nullable=False)
    aliases_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    birth_year_ah: Mapped[int | None] = mapped_column(Integer, nullable=True)
    death_year_ah: Mapped[int | None] = mapped_column(Integer, nullable=True)
    methodology_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class TafsirCollection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_collections"
    __table_args__ = (UniqueConstraint("collection_key"),)

    collection_key: Mapped[str] = mapped_column(String(120), nullable=False)
    arabic_title: Mapped[str] = mapped_column(String(400), nullable=False)
    display_title: Mapped[str] = mapped_column(String(400), nullable=False)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_authors.id", ondelete="RESTRICT"), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class TafsirEdition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_editions"
    __table_args__ = (
        UniqueConstraint("edition_key"),
        UniqueConstraint("collection_id", "source_edition_id"),
    )

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_collections.id", ondelete="RESTRICT"), nullable=False, index=True)
    source_edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="RESTRICT"), nullable=False)
    edition_key: Mapped[str] = mapped_column(String(120), nullable=False)
    publisher_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    publication_year: Mapped[str | None] = mapped_column(String(32), nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="ar", server_default="ar")
    attribution_text: Mapped[str] = mapped_column(Text, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class TafsirVolume(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_volumes"
    __table_args__ = (
        UniqueConstraint("edition_id", "volume_number"),
        CheckConstraint("volume_number > 0", name="ck_tafsir_volumes_number"),
    )

    edition_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_editions.id", ondelete="RESTRICT"), nullable=False, index=True)
    volume_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(400), nullable=True)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class TafsirSection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_sections"
    __table_args__ = (
        UniqueConstraint("edition_id", "section_key"),
        CheckConstraint("section_type IN ('surah','ayah','ayah_range','introduction','appendix','editorial_note')", name="ck_tafsir_sections_type"),
    )

    edition_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_editions.id", ondelete="RESTRICT"), nullable=False, index=True)
    volume_id: Mapped[UUID | None] = mapped_column(ForeignKey("tafsir_volumes.id", ondelete="RESTRICT"), nullable=True)
    section_key: Mapped[str] = mapped_column(String(180), nullable=False)
    section_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class TafsirEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_entries"
    __table_args__ = (
        UniqueConstraint("edition_id", "canonical_reference"),
        CheckConstraint("surah_number BETWEEN 1 AND 114", name="ck_tafsir_entries_surah"),
        CheckConstraint("start_ayah_number IS NULL OR start_ayah_number > 0", name="ck_tafsir_entries_start_ayah"),
        CheckConstraint("end_ayah_number IS NULL OR end_ayah_number >= start_ayah_number", name="ck_tafsir_entries_end_ayah"),
        Index("ix_tafsir_entries_surah_range", "surah_number", "start_ayah_number", "end_ayah_number"),
    )

    edition_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_editions.id", ondelete="RESTRICT"), nullable=False, index=True)
    section_id: Mapped[UUID | None] = mapped_column(ForeignKey("tafsir_sections.id", ondelete="RESTRICT"), nullable=True, index=True)
    canonical_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    surah_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ayah_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_ayah_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    arabic_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class TafsirTranslationEdition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_translation_editions"
    __table_args__ = (UniqueConstraint("translation_key"),)

    tafsir_edition_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_editions.id", ondelete="RESTRICT"), nullable=False, index=True)
    source_edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="RESTRICT"), nullable=False)
    translation_key: Mapped[str] = mapped_column(String(120), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    translator_name: Mapped[str] = mapped_column(String(300), nullable=False)
    publisher_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    attribution_text: Mapped[str] = mapped_column(Text, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class TafsirTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_translations"
    __table_args__ = (UniqueConstraint("translation_edition_id", "tafsir_entry_id"),)

    translation_edition_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_translation_editions.id", ondelete="RESTRICT"), nullable=False, index=True)
    tafsir_entry_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

import sqlalchemy as sa


class TafsirImportBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_import_batches"
    __table_args__ = (
        CheckConstraint("status IN ('draft','validating','failed','review_pending','approved','changes_requested','rejected','published')", name="ck_tafsir_import_batches_status"),
        CheckConstraint("expected_entry_count > 0", name="ck_tafsir_import_batches_count"),
    )
    edition_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_editions.id", ondelete="RESTRICT"), nullable=False, index=True)
    manifest_version: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_volume_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_section_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_entry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft")
    submitted_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    validation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_at: Mapped[object | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    published_at: Mapped[object | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class TafsirImportEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_import_entries"
    __table_args__ = (
        UniqueConstraint("import_batch_id", "canonical_reference"),
        CheckConstraint("validation_status IN ('pending','valid','invalid')", name="ck_tafsir_import_entries_validation"),
        Index("ix_tafsir_import_entries_batch_order", "import_batch_id", "volume_number", "section_sort_order", "surah_number", "start_ayah_number"),
    )
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    volume_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume_title: Mapped[str | None] = mapped_column(String(400), nullable=True)
    volume_source_passage_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=True)
    section_key: Mapped[str | None] = mapped_column(String(180), nullable=True)
    section_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    section_sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    section_source_passage_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=True)
    canonical_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    surah_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ayah_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_ayah_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    arabic_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    validation_errors: Mapped[str | None] = mapped_column(Text, nullable=True)


class TafsirImportReviewAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_import_review_assignments"
    __table_args__ = (
        UniqueConstraint("import_batch_id", "reviewer_user_id", "review_domain"),
        CheckConstraint("review_domain IN ('tafsir_text','source_provenance','arabic_language')", name="ck_tafsir_import_review_domain"),
        CheckConstraint("status IN ('open','completed','cancelled')", name="ck_tafsir_import_assignment_status"),
    )
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    review_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", server_default="open")
    due_at: Mapped[object | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class TafsirImportReview(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "tafsir_import_reviews"
    __table_args__ = (
        UniqueConstraint("assignment_id"),
        CheckConstraint("decision IN ('approved','changes_requested','rejected')", name="ck_tafsir_import_review_decision"),
    )
    assignment_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_import_review_assignments.id", ondelete="CASCADE"), nullable=False)
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    review_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class TafsirImportEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "tafsir_import_events"
    __table_args__ = (Index("ix_tafsir_import_events_batch_created", "import_batch_id", "created_at"),)
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(sa.DateTime(timezone=True), nullable=False)

class TafsirTranslationImportBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_translation_import_batches"
    __table_args__ = (
        CheckConstraint("status IN ('draft','validating','failed','review_pending','approved','changes_requested','rejected','published')", name="ck_tafsir_translation_import_status"),
        CheckConstraint("expected_translation_count > 0", name="ck_tafsir_translation_import_count"),
    )
    translation_edition_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_translation_editions.id", ondelete="RESTRICT"), nullable=False, index=True)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_translation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft")
    submitted_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    validation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_at: Mapped[object | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    published_at: Mapped[object | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class TafsirTranslationImportItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_translation_import_items"
    __table_args__ = (UniqueConstraint("import_batch_id", "tafsir_entry_id"),)
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_translation_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    tafsir_entry_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_entries.id", ondelete="RESTRICT"), nullable=False, index=True)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)


class TafsirTranslationImportReview(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "tafsir_translation_import_reviews"
    __table_args__ = (UniqueConstraint("import_batch_id", "reviewer_user_id"), CheckConstraint("decision IN ('approved','changes_requested','rejected')", name="ck_tafsir_translation_review_decision"))
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_translation_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(sa.DateTime(timezone=True), nullable=False)

class TafsirBookmark(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_bookmarks"
    __table_args__ = (UniqueConstraint("user_id", "tafsir_entry_id"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tafsir_entry_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TafsirStudyNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_study_notes"
    __table_args__ = (Index("ix_tafsir_study_notes_user_entry", "user_id", "tafsir_entry_id"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tafsir_entry_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(240), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)


class TafsirStudyCollection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_study_collections"
    __table_args__ = (UniqueConstraint("user_id", "name"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class TafsirStudyCollectionItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_study_collection_items"
    __table_args__ = (UniqueConstraint("collection_id", "tafsir_entry_id"),)
    collection_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_study_collections.id", ondelete="CASCADE"), nullable=False, index=True)
    tafsir_entry_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class TafsirStudyProgress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tafsir_study_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "tafsir_entry_id"),
        CheckConstraint("status IN ('not_started','in_progress','completed')", name="ck_tafsir_study_progress_status"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tafsir_entry_id: Mapped[UUID] = mapped_column(ForeignKey("tafsir_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="not_started", server_default="not_started")
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
