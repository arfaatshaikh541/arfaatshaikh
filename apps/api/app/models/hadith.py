from __future__ import annotations

from uuid import UUID
import sqlalchemy as sa
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class HadithCollection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_collections"
    __table_args__ = (UniqueConstraint("collection_key"),)

    source_edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="RESTRICT"), nullable=False)
    collection_key: Mapped[str] = mapped_column(String(120), nullable=False)
    arabic_title: Mapped[str] = mapped_column(String(300), nullable=False)
    display_title: Mapped[str] = mapped_column(String(300), nullable=False)
    compiler_name: Mapped[str] = mapped_column(String(300), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="ar", server_default="ar")
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class HadithBook(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_books"
    __table_args__ = (
        UniqueConstraint("collection_id", "book_number"),
        CheckConstraint("book_number > 0", name="ck_hadith_books_number"),
    )

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_collections.id", ondelete="RESTRICT"), nullable=False, index=True)
    book_number: Mapped[int] = mapped_column(Integer, nullable=False)
    arabic_title: Mapped[str] = mapped_column(String(300), nullable=False)
    display_title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class HadithChapter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_chapters"
    __table_args__ = (
        UniqueConstraint("book_id", "chapter_number"),
        CheckConstraint("chapter_number > 0", name="ck_hadith_chapters_number"),
    )

    book_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_books.id", ondelete="RESTRICT"), nullable=False, index=True)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    arabic_title: Mapped[str] = mapped_column(String(500), nullable=False)
    display_title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class HadithNarration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_narrations"
    __table_args__ = (
        UniqueConstraint("collection_id", "canonical_reference"),
        UniqueConstraint("collection_id", "collection_hadith_number"),
        CheckConstraint("collection_hadith_number > 0", name="ck_hadith_narrations_number"),
        Index("ix_hadith_narrations_reference", "canonical_reference"),
    )

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_collections.id", ondelete="RESTRICT"), nullable=False, index=True)
    book_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_books.id", ondelete="RESTRICT"), nullable=False, index=True)
    chapter_id: Mapped[UUID | None] = mapped_column(ForeignKey("hadith_chapters.id", ondelete="RESTRICT"), nullable=True, index=True)
    collection_hadith_number: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    arabic_matn: Mapped[str] = mapped_column(Text, nullable=False)
    matn_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class HadithNarrator(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_narrators"
    __table_args__ = (UniqueConstraint("canonical_name"),)

    canonical_name: Mapped[str] = mapped_column(String(300), nullable=False)
    arabic_name: Mapped[str] = mapped_column(String(300), nullable=False)
    disambiguation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_passage_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=True)


class HadithNarratorAlias(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "hadith_narrator_aliases"
    __table_args__ = (UniqueConstraint("narrator_id", "alias"),)

    narrator_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_narrators.id", ondelete="CASCADE"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(300), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)


class HadithIsnadNode(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "hadith_isnad_nodes"
    __table_args__ = (
        UniqueConstraint("narration_id", "position"),
        CheckConstraint("position > 0", name="ck_hadith_isnad_nodes_position"),
    )

    narration_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_narrations.id", ondelete="CASCADE"), nullable=False, index=True)
    narrator_id: Mapped[UUID | None] = mapped_column(ForeignKey("hadith_narrators.id", ondelete="RESTRICT"), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    transmitted_name: Mapped[str] = mapped_column(String(300), nullable=False)
    transmission_term: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)


class HadithGrading(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_gradings"
    __table_args__ = (
        UniqueConstraint("narration_id", "grader_name", "grading_label", "source_passage_id"),
        CheckConstraint("grading_label IN ('sahih','hasan','daif','mawdu','mixed','ungraded','other')", name="ck_hadith_gradings_label"),
    )

    narration_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_narrations.id", ondelete="CASCADE"), nullable=False, index=True)
    grader_name: Mapped[str] = mapped_column(String(300), nullable=False)
    grading_label: Mapped[str] = mapped_column(String(32), nullable=False)
    grading_text: Mapped[str] = mapped_column(Text, nullable=False)
    methodology_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

class HadithImportBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_import_batches"
    __table_args__ = (
        CheckConstraint("status IN ('draft','validating','validated','review_pending','approved','changes_requested','rejected','published','failed')", name="ck_hadith_import_batches_status"),
        CheckConstraint("expected_narration_count > 0", name="ck_hadith_import_batches_expected_count"),
        Index("ix_hadith_import_batches_collection_status", "collection_id", "status"),
    )

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_collections.id", ondelete="RESTRICT"), nullable=False, index=True)
    manifest_version: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_book_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_chapter_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_narration_count: Mapped[int] = mapped_column(Integer, nullable=False)
    require_complete_isnad: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft")
    submitted_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    validation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_at: Mapped[object | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    published_at: Mapped[object | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class HadithImportNarration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_import_narrations"
    __table_args__ = (
        UniqueConstraint("import_batch_id", "collection_hadith_number"),
        CheckConstraint("collection_hadith_number > 0", name="ck_hadith_import_narrations_number"),
        CheckConstraint("validation_status IN ('pending','valid','invalid','duplicate')", name="ck_hadith_import_narrations_validation"),
        Index("ix_hadith_import_narrations_batch_order", "import_batch_id", "book_number", "chapter_number", "collection_hadith_number"),
    )

    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    book_number: Mapped[int] = mapped_column(Integer, nullable=False)
    book_arabic_title: Mapped[str] = mapped_column(String(300), nullable=False)
    book_display_title: Mapped[str] = mapped_column(String(300), nullable=False)
    book_source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    chapter_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapter_arabic_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    chapter_display_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    chapter_source_passage_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=True)
    collection_hadith_number: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    arabic_matn: Mapped[str] = mapped_column(Text, nullable=False)
    matn_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    validation_errors: Mapped[str | None] = mapped_column(Text, nullable=True)


class HadithImportIsnadNode(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "hadith_import_isnad_nodes"
    __table_args__ = (
        UniqueConstraint("import_narration_id", "position"),
        CheckConstraint("position > 0", name="ck_hadith_import_isnad_position"),
    )

    import_narration_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_import_narrations.id", ondelete="CASCADE"), nullable=False, index=True)
    narrator_id: Mapped[UUID | None] = mapped_column(ForeignKey("hadith_narrators.id", ondelete="RESTRICT"), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    transmitted_name: Mapped[str] = mapped_column(String(300), nullable=False)
    transmission_term: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)


class HadithDuplicateCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_duplicate_candidates"
    __table_args__ = (
        UniqueConstraint("import_narration_id", "existing_narration_id"),
        CheckConstraint("match_type IN ('exact_reference','exact_matn','possible_matn')", name="ck_hadith_duplicate_match_type"),
        CheckConstraint("resolution IN ('pending','not_duplicate','confirmed_duplicate','replace_existing')", name="ck_hadith_duplicate_resolution"),
    )

    import_narration_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_import_narrations.id", ondelete="CASCADE"), nullable=False, index=True)
    existing_narration_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_narrations.id", ondelete="RESTRICT"), nullable=False)
    match_type: Mapped[str] = mapped_column(String(32), nullable=False)
    similarity_basis: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    resolved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    resolution_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)


class HadithImportReviewAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_import_review_assignments"
    __table_args__ = (
        UniqueConstraint("import_batch_id", "reviewer_user_id", "review_domain"),
        CheckConstraint("review_domain IN ('hadith_text','isnad','source_provenance')", name="ck_hadith_import_review_domain"),
        CheckConstraint("status IN ('open','completed','cancelled')", name="ck_hadith_import_review_assignment_status"),
    )

    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    review_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", server_default="open")
    due_at: Mapped[object | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class HadithImportReview(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "hadith_import_reviews"
    __table_args__ = (
        UniqueConstraint("assignment_id"),
        CheckConstraint("decision IN ('approved','changes_requested','rejected')", name="ck_hadith_import_reviews_decision"),
    )

    assignment_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_import_review_assignments.id", ondelete="CASCADE"), nullable=False)
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    review_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class HadithImportEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "hadith_import_events"
    __table_args__ = (Index("ix_hadith_import_events_batch_created", "import_batch_id", "created_at"),)

    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(sa.DateTime(timezone=True), nullable=False)

class HadithTranslationEdition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_translation_editions"
    __table_args__ = (
        UniqueConstraint("translation_key"),
        UniqueConstraint("source_edition_id", "language", "translator_name"),
    )

    source_edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="RESTRICT"), nullable=False)
    translation_key: Mapped[str] = mapped_column(String(120), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    translator_name: Mapped[str] = mapped_column(String(300), nullable=False)
    publisher_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    attribution_text: Mapped[str] = mapped_column(Text, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class HadithTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_translations"
    __table_args__ = (UniqueConstraint("translation_edition_id", "narration_id"),)

    translation_edition_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_translation_editions.id", ondelete="CASCADE"), nullable=False, index=True)
    narration_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_narrations.id", ondelete="CASCADE"), nullable=False, index=True)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class HadithTranslationImportBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_translation_import_batches"
    __table_args__ = (
        CheckConstraint("status IN ('draft','review_pending','approved','rejected','published','failed')", name="ck_hadith_translation_import_status"),
        CheckConstraint("expected_record_count > 0", name="ck_hadith_translation_import_count"),
    )
    translation_edition_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_translation_editions.id", ondelete="RESTRICT"), nullable=False, index=True)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", server_default="draft")
    submitted_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    validation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[object | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class HadithTranslationImportItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_translation_import_items"
    __table_args__ = (
        UniqueConstraint("import_batch_id", "narration_id"),
        CheckConstraint("validation_status IN ('pending','valid','invalid')", name="ck_hadith_translation_item_validation"),
    )
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_translation_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    narration_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_narrations.id", ondelete="RESTRICT"), nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")


class HadithTranslationImportReview(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "hadith_translation_import_reviews"
    __table_args__ = (
        UniqueConstraint("import_batch_id"),
        CheckConstraint("decision IN ('approved','rejected')", name="ck_hadith_translation_review_decision"),
    )
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_translation_import_batches.id", ondelete="CASCADE"), nullable=False)
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class HadithGradingImportBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_grading_import_batches"
    __table_args__ = (
        CheckConstraint("status IN ('draft','review_pending','approved','rejected','published','failed')", name="ck_hadith_grading_import_status"),
        CheckConstraint("expected_record_count > 0", name="ck_hadith_grading_import_count"),
    )
    collection_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_collections.id", ondelete="RESTRICT"), nullable=False, index=True)
    source_edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="RESTRICT"), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", server_default="draft")
    submitted_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    validation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[object | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class HadithGradingImportItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_grading_import_items"
    __table_args__ = (
        UniqueConstraint("import_batch_id", "narration_id", "grader_name", "grading_label", "source_passage_id"),
        CheckConstraint("grading_label IN ('sahih','hasan','daif','mawdu','mixed','ungraded','other')", name="ck_hadith_grading_import_label"),
        CheckConstraint("validation_status IN ('pending','valid','invalid')", name="ck_hadith_grading_item_validation"),
    )
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_grading_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    narration_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_narrations.id", ondelete="RESTRICT"), nullable=False)
    grader_name: Mapped[str] = mapped_column(String(300), nullable=False)
    grading_label: Mapped[str] = mapped_column(String(32), nullable=False)
    grading_text: Mapped[str] = mapped_column(Text, nullable=False)
    methodology_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")


class HadithGradingImportReview(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "hadith_grading_import_reviews"
    __table_args__ = (
        UniqueConstraint("import_batch_id"),
        CheckConstraint("decision IN ('approved','rejected')", name="ck_hadith_grading_review_decision"),
    )
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_grading_import_batches.id", ondelete="CASCADE"), nullable=False)
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(sa.DateTime(timezone=True), nullable=False)

class HadithBookmark(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_bookmarks"
    __table_args__ = (UniqueConstraint("user_id", "narration_id"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    narration_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_narrations.id", ondelete="CASCADE"), nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class HadithReadingHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hadith_reading_history"
    __table_args__ = (UniqueConstraint("user_id", "narration_id"), Index("ix_hadith_history_user_last_read", "user_id", "last_read_at"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    narration_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_narrations.id", ondelete="CASCADE"), nullable=False, index=True)
    last_read_at: Mapped[object] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    read_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class HadithCitationExport(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "hadith_citation_exports"
    __table_args__ = (CheckConstraint("format IN ('json','csv','plain_text')", name="ck_hadith_citation_exports_format"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    narration_id: Mapped[UUID] = mapped_column(ForeignKey("hadith_narrations.id", ondelete="RESTRICT"), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[object] = mapped_column(sa.DateTime(timezone=True), nullable=False)
