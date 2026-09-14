from __future__ import annotations

from uuid import UUID
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AssistantAnswerRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assistant_answer_runs"
    __table_args__ = (
        CheckConstraint("status IN ('received','classified','evidence_ready','assembled','insufficient','failed')", name="ck_assistant_answer_runs_status"),
        CheckConstraint("risk_level IN ('standard','sensitive','high_risk')", name="ck_assistant_answer_runs_risk"),
        Index("ix_assistant_answer_runs_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    question_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    question_language: Mapped[str] = mapped_column(String(16), nullable=False)
    classification: Mapped[str] = mapped_column(String(48), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    classifier_version: Mapped[str] = mapped_column(String(64), nullable=False)
    grounding_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="received", server_default="received")
    insufficiency_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AssistantClaim(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assistant_claims"
    __table_args__ = (
        CheckConstraint("claim_type IN ('direct_quote','source_summary','scholarly_interpretation','difference_of_opinion','general_explanation')", name="ck_assistant_claims_type"),
        CheckConstraint("status IN ('proposed','verified','rejected')", name="ck_assistant_claims_status"),
        CheckConstraint("position >= 0", name="ck_assistant_claims_position"),
        UniqueConstraint("answer_run_id", "position", name="uq_assistant_claim_position"),
    )

    answer_run_id: Mapped[UUID] = mapped_column(ForeignKey("assistant_answer_runs.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed", server_default="proposed")
    rejection_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)


class AssistantClaimEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assistant_claim_evidence"
    __table_args__ = (
        CheckConstraint("support_type IN ('quotes','supports','attributes','contrasts')", name="ck_assistant_claim_evidence_support"),
        UniqueConstraint("claim_id", "chunk_id", name="uq_assistant_claim_evidence_chunk"),
    )

    claim_id: Mapped[UUID] = mapped_column(ForeignKey("assistant_claims.id", ondelete="CASCADE"), nullable=False)
    chunk_id: Mapped[UUID] = mapped_column(ForeignKey("retrieval_chunks.id", ondelete="RESTRICT"), nullable=False)
    support_type: Mapped[str] = mapped_column(String(20), nullable=False)
    citation_label: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

class AssistantSafetyPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assistant_safety_policies"
    __table_args__ = (UniqueConstraint("policy_key", "version", name="uq_assistant_safety_policy_version"),)
    policy_key: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    active: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    rules_json: Mapped[str] = mapped_column(Text, nullable=False)

class AssistantPolicyDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assistant_policy_decisions"
    answer_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("assistant_answer_runs.id", ondelete="SET NULL"), nullable=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    reasons_json: Mapped[str] = mapped_column(Text, nullable=False)
    raw_question_retention_days: Mapped[int] = mapped_column(Integer, nullable=False)

class AssistantAuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assistant_answer_audit_log"
    __table_args__ = (UniqueConstraint("answer_run_id", "version", name="uq_assistant_audit_version"),)
    answer_run_id: Mapped[UUID] = mapped_column(ForeignKey("assistant_answer_runs.id", ondelete="RESTRICT"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_entry_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

class AssistantConversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assistant_conversations"
    __table_args__ = (Index("ix_assistant_conversations_user_updated", "user_id", "updated_at"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), nullable=False, default="en", server_default="en")
    archived: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")

class AssistantMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assistant_messages"
    __table_args__ = (UniqueConstraint("conversation_id", "position", name="uq_assistant_message_position"),)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("assistant_conversations.id", ondelete="CASCADE"), nullable=False)
    answer_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("assistant_answer_runs.id", ondelete="SET NULL"), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

class AssistantFeedback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assistant_feedback"
    __table_args__ = (UniqueConstraint("user_id", "answer_run_id", name="uq_assistant_feedback_user_answer"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    answer_run_id: Mapped[UUID] = mapped_column(ForeignKey("assistant_answer_runs.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
