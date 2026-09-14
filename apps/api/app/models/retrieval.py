from __future__ import annotations

from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RetrievalProjectionRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "retrieval_projection_runs"
    __table_args__ = (CheckConstraint("status IN ('pending','running','completed','failed','cancelled')", name="ck_retrieval_projection_runs_status"),)

    corpus_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    projected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    initiated_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class RetrievalDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "retrieval_documents"
    __table_args__ = (
        CheckConstraint("corpus_type IN ('quran','hadith','tafsir','topic','cross_reference')", name="ck_retrieval_documents_corpus_type"),
        UniqueConstraint("corpus_type", "entity_id", "content_sha256", name="uq_retrieval_document_version"),
        Index("ix_retrieval_documents_entity", "corpus_type", "entity_id"),
    )

    corpus_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(nullable=False)
    canonical_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    source_edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="RESTRICT"), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    content_language: Mapped[str] = mapped_column(String(16), nullable=False)
    content_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    licence_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    attribution_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    projection_run_id: Mapped[UUID] = mapped_column(ForeignKey("retrieval_projection_runs.id", ondelete="RESTRICT"), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class RetrievalChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "retrieval_chunks"
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="ck_retrieval_chunks_index"),
        CheckConstraint("start_offset >= 0 AND end_offset > start_offset", name="ck_retrieval_chunks_offsets"),
        UniqueConstraint("document_id", "chunk_index"),
        Index("ix_retrieval_chunks_document_active", "document_id", "active"),
    )

    document_id: Mapped[UUID] = mapped_column(ForeignKey("retrieval_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    boundary_type: Mapped[str] = mapped_column(String(32), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class RetrievalQueryAudit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "retrieval_query_audits"
    __table_args__ = (CheckConstraint("status IN ('started','completed','insufficient','failed')", name="ck_retrieval_query_audits_status"),)

    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    query_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    query_language: Mapped[str] = mapped_column(String(16), nullable=False)
    requested_corpora: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="started", server_default="started")
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    selected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    insufficiency_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class RetrievalEvidenceSelection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "retrieval_evidence_selections"
    __table_args__ = (
        CheckConstraint("rank_position > 0", name="ck_retrieval_evidence_selections_rank"),
        UniqueConstraint("query_audit_id", "chunk_id"),
    )

    query_audit_id: Mapped[UUID] = mapped_column(ForeignKey("retrieval_query_audits.id", ondelete="CASCADE"), nullable=False)
    chunk_id: Mapped[UUID] = mapped_column(ForeignKey("retrieval_chunks.id", ondelete="RESTRICT"), nullable=False)
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)
    retrieval_score_millis: Mapped[int] = mapped_column(Integer, nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    rejection_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
