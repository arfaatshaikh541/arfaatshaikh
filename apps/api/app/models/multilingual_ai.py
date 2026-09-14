from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class AILanguageProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_language_profiles"
    __table_args__ = (
        CheckConstraint("primary_language IN ('ar','en','ur','hi','transliteration')", name="ck_ai_language_profile_primary"),
        CheckConstraint("reading_level IN ('simple','standard','scholarly')", name="ck_ai_language_profile_level"),
        UniqueConstraint("user_id", name="uq_ai_language_profile_user"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    primary_language: Mapped[str] = mapped_column(String(20), nullable=False)
    secondary_language: Mapped[str | None] = mapped_column(String(20))
    reading_level: Mapped[str] = mapped_column(String(16), nullable=False, default="standard", server_default="standard")
    prefer_transliteration: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

class AITranslationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_translation_runs"
    __table_args__ = (
        CheckConstraint("source_language IN ('ar','en','ur','hi','transliteration')", name="ck_ai_translation_source_language"),
        CheckConstraint("target_language IN ('ar','en','ur','hi','transliteration')", name="ck_ai_translation_target_language"),
        CheckConstraint("status IN ('received','aligned','review_required','blocked','approved')", name="ck_ai_translation_status"),
        CheckConstraint("claim_count >= 0", name="ck_ai_translation_claim_count"),
        Index("ix_ai_translation_run_status_created", "status", "created_at"),
    )
    orchestration_run_id: Mapped[UUID] = mapped_column(ForeignKey("ai_orchestration_runs.id", ondelete="CASCADE"), nullable=False)
    source_language: Mapped[str] = mapped_column(String(20), nullable=False)
    target_language: Mapped[str] = mapped_column(String(20), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    target_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="received", server_default="received")
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)

class AIClaimLanguageAlignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_claim_language_alignments"
    __table_args__ = (
        CheckConstraint("decision IN ('approved','review','blocked')", name="ck_ai_claim_language_alignment_decision"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_ai_claim_language_alignment_confidence"),
        UniqueConstraint("translation_run_id", "claim_verification_id", name="uq_ai_claim_language_alignment_claim"),
    )
    translation_run_id: Mapped[UUID] = mapped_column(ForeignKey("ai_translation_runs.id", ondelete="CASCADE"), nullable=False)
    claim_verification_id: Mapped[UUID] = mapped_column(ForeignKey("ai_claim_verifications.id", ondelete="CASCADE"), nullable=False)
    source_text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    target_text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(5,4), nullable=False)
    citations_preserved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)

class AILanguageReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_language_reviews"
    __table_args__ = (
        CheckConstraint("status IN ('queued','assigned','approved','rejected')", name="ck_ai_language_review_status"),
        CheckConstraint("review_type IN ('language','translation','terminology','religious_meaning')", name="ck_ai_language_review_type"),
        Index("ix_ai_language_review_queue", "status", "review_type", "created_at"),
    )
    translation_run_id: Mapped[UUID] = mapped_column(ForeignKey("ai_translation_runs.id", ondelete="CASCADE"), nullable=False)
    reviewer_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    review_type: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", server_default="queued")
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    review_note: Mapped[str | None] = mapped_column(Text)
