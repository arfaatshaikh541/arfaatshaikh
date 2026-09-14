from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeSyncSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_schedules"
    __table_args__ = (
        CheckConstraint("status IN ('active','paused','disabled')", name="ck_knowledge_sync_schedule_status"),
        CheckConstraint("direction IN ('pull','push')", name="ck_knowledge_sync_schedule_direction"),
        UniqueConstraint("organisation_id", "node_id", "direction", name="uq_knowledge_sync_schedule_org_node_direction"),
    )

    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_nodes.id", ondelete="CASCADE"), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="active", server_default="active")
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default="60")
    max_concurrent_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    jitter_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default="30")


class KnowledgeSyncTransferBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_transfer_batches"
    __table_args__ = (
        CheckConstraint("status IN ('planned','transferring','completed','partial','failed','cancelled')", name="ck_knowledge_sync_transfer_batch_status"),
        UniqueConstraint("run_id", "batch_number", name="uq_knowledge_sync_transfer_batch_run_number"),
        Index("ix_knowledge_sync_transfer_batch_run_status", "run_id", "status"),
    )

    run_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_runs.id", ondelete="CASCADE"), nullable=False)
    batch_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="planned", server_default="planned")
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    byte_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    completed_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class KnowledgeSyncTransferChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_transfer_chunks"
    __table_args__ = (
        CheckConstraint("status IN ('pending','transferring','verified','failed','dead_lettered','cancelled')", name="ck_knowledge_sync_transfer_chunk_status"),
        UniqueConstraint("batch_id", "chunk_number", name="uq_knowledge_sync_transfer_chunk_batch_number"),
        UniqueConstraint("batch_id", "idempotency_key", name="uq_knowledge_sync_transfer_chunk_batch_idempotency"),
        Index("ix_knowledge_sync_transfer_chunk_batch_status", "batch_id", "status"),
    )

    batch_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_transfer_batches.id", ondelete="CASCADE"), nullable=False)
    chunk_number: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    compressed_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    byte_count: Mapped[int] = mapped_column(Integer, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")


class KnowledgeSyncTransferAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_transfer_attempts"
    __table_args__ = (
        CheckConstraint("outcome IN ('success','retry','permanent_failure','cancelled')", name="ck_knowledge_sync_transfer_attempt_outcome"),
        UniqueConstraint("chunk_id", "attempt_number", name="uq_knowledge_sync_transfer_attempt_chunk_number"),
    )

    chunk_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_transfer_chunks.id", ondelete="CASCADE"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)


class KnowledgeSyncDeadLetter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_dead_letters"
    __table_args__ = (
        CheckConstraint("status IN ('open','requeued','resolved','discarded')", name="ck_knowledge_sync_dead_letter_status"),
        UniqueConstraint("chunk_id", name="uq_knowledge_sync_dead_letter_chunk"),
    )

    chunk_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_transfer_chunks.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open", server_default="open")
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
