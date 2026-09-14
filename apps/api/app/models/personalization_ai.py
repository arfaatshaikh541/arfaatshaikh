from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class AIPersonalizationProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_personalization_profiles"
    __table_args__ = (
        CheckConstraint("reading_depth IN ('concise','standard','detailed','scholarly')", name="ck_ai_personalization_depth"),
        CheckConstraint("recommendation_mode IN ('off','minimal','standard')", name="ck_ai_personalization_mode"),
        UniqueConstraint("user_id", name="uq_ai_personalization_profile_user"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reading_depth: Mapped[str] = mapped_column(String(16), nullable=False, default="standard", server_default="standard")
    recommendation_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="standard", server_default="standard")
    preferred_topics: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    hidden_topics: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    personalization_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

class AIAccessibilityProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_accessibility_profiles"
    __table_args__ = (
        CheckConstraint("text_scale_percent >= 75 AND text_scale_percent <= 200", name="ck_ai_accessibility_text_scale"),
        UniqueConstraint("user_id", name="uq_ai_accessibility_profile_user"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text_scale_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    reduced_motion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    high_contrast: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    screen_reader_optimised: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    captions_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

class AIPersonalizationEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_personalization_events"
    __table_args__ = (
        CheckConstraint("event_type IN ('explicit_preference','course_progress','bookmark','dismissal','language_choice','accessibility_change')", name="ck_ai_personalization_event_type"),
        CheckConstraint("retention_days >= 0 AND retention_days <= 365", name="ck_ai_personalization_retention"),
        Index("ix_ai_personalization_event_user_created", "user_id", "created_at"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_key: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    consent_basis: Mapped[str] = mapped_column(String(40), nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90, server_default="90")
    eligible_for_recommendation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

class AIRecommendationDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_recommendation_decisions"
    __table_args__ = (
        CheckConstraint("decision IN ('recommended','suppressed','blocked')", name="ck_ai_recommendation_decision"),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_ai_recommendation_score"),
        Index("ix_ai_recommendation_user_created", "user_id", "created_at"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    candidate_key: Mapped[str] = mapped_column(String(200), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
