from __future__ import annotations

from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AIOrchestrationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_orchestration_runs"
    __table_args__ = (
        CheckConstraint("status IN ('received','classified','retrieving','grounding','blocked','escalated','completed','failed')", name="ck_ai_orchestration_run_status"),
        CheckConstraint("risk_level IN ('standard','sensitive','high_risk')", name="ck_ai_orchestration_run_risk"),
        CheckConstraint("evidence_count >= 0", name="ck_ai_orchestration_evidence_count"),
        Index("ix_ai_orchestration_user_created", "user_id", "created_at"),
    )
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    question_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False)
    classification: Mapped[str] = mapped_column(String(48), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="received", server_default="received")
    orchestration_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    grounding_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    requires_scholar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    terminal_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)


class AIClaimVerification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_claim_verifications"
    __table_args__ = (
        CheckConstraint("claim_type IN ('direct_quote','source_summary','scholarly_interpretation','difference_of_opinion','general_explanation','ruling')", name="ck_ai_claim_verification_type"),
        CheckConstraint("decision IN ('verified','blocked','escalated')", name="ck_ai_claim_verification_decision"),
        CheckConstraint("position >= 0", name="ck_ai_claim_verification_position"),
        UniqueConstraint("orchestration_run_id", "position", name="uq_ai_claim_verification_position"),
    )
    orchestration_run_id: Mapped[UUID] = mapped_column(ForeignKey("ai_orchestration_runs.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(40), nullable=False)
    claim_text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    citation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)


class AIClaimCitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_claim_citations"
    __table_args__ = (
        CheckConstraint("support_type IN ('quotes','supports','attributes','contrasts')", name="ck_ai_claim_citation_support"),
        UniqueConstraint("claim_verification_id", "source_passage_id", "support_type", name="uq_ai_claim_citation_source"),
    )
    claim_verification_id: Mapped[UUID] = mapped_column(ForeignKey("ai_claim_verifications.id", ondelete="CASCADE"), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    retrieval_chunk_id: Mapped[UUID | None] = mapped_column(ForeignKey("retrieval_chunks.id", ondelete="SET NULL"), nullable=True)
    support_type: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    citation_label: Mapped[str] = mapped_column(String(80), nullable=False)


class AIScholarEscalation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_scholar_escalations"
    __table_args__ = (
        CheckConstraint("status IN ('queued','assigned','resolved','closed')", name="ck_ai_scholar_escalation_status"),
        CheckConstraint("priority IN ('normal','high','urgent')", name="ck_ai_scholar_escalation_priority"),
        Index("ix_ai_scholar_escalation_status_priority", "status", "priority", "created_at"),
    )
    orchestration_run_id: Mapped[UUID] = mapped_column(ForeignKey("ai_orchestration_runs.id", ondelete="CASCADE"), nullable=False)
    assigned_scholar_profile_id: Mapped[UUID | None] = mapped_column(ForeignKey("scholar_profiles.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", server_default="queued")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal", server_default="normal")
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    context_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
