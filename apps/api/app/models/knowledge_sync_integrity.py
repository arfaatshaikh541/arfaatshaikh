from __future__ import annotations

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeSyncSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_snapshots"
    __table_args__ = (
        CheckConstraint("status IN ('building','sealed','verified','invalidated')", name="ck_knowledge_sync_snapshot_status"),
        UniqueConstraint("node_id", "content_type", "snapshot_version", name="uq_knowledge_sync_snapshot_node_type_version"),
        Index("ix_knowledge_sync_snapshot_node_status", "node_id", "status"),
    )

    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_nodes.id", ondelete="CASCADE"), nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot_version: Mapped[str] = mapped_column(String(80), nullable=False)
    root_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    partition_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="building", server_default="building")


class KnowledgeSyncPartitionDigest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_partition_digests"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "partition_key", name="uq_knowledge_sync_partition_snapshot_key"),
        Index("ix_knowledge_sync_partition_snapshot", "snapshot_id"),
    )

    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_snapshots.id", ondelete="CASCADE"), nullable=False)
    partition_key: Mapped[str] = mapped_column(String(160), nullable=False)
    first_canonical_id: Mapped[str] = mapped_column(String(240), nullable=False)
    last_canonical_id: Mapped[str] = mapped_column(String(240), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    digest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class KnowledgeSyncDriftReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_drift_reports"
    __table_args__ = (
        CheckConstraint("status IN ('clean','drift_detected','repair_planned','resolved','dismissed')", name="ck_knowledge_sync_drift_status"),
        UniqueConstraint("local_snapshot_id", "remote_snapshot_id", name="uq_knowledge_sync_drift_snapshot_pair"),
    )

    local_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_snapshots.id", ondelete="CASCADE"), nullable=False)
    remote_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_snapshots.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="clean", server_default="clean")
    matching_partitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    divergent_partitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    missing_local_partitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    missing_remote_partitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class KnowledgeSyncRepairPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_repair_plans"
    __table_args__ = (
        CheckConstraint("status IN ('draft','approved','executing','completed','failed','cancelled')", name="ck_knowledge_sync_repair_plan_status"),
        CheckConstraint("strategy IN ('fetch_missing','replace_divergent','manual_review')", name="ck_knowledge_sync_repair_strategy"),
    )

    drift_report_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_drift_reports.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    strategy: Mapped[str] = mapped_column(String(24), nullable=False)
    partition_keys_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    requires_scholarly_review: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class KnowledgeSyncIntegrityVerification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_integrity_verifications"
    __table_args__ = (
        CheckConstraint("outcome IN ('passed','failed','inconclusive')", name="ck_knowledge_sync_integrity_verification_outcome"),
        UniqueConstraint("snapshot_id", "verification_version", name="uq_knowledge_sync_integrity_snapshot_version"),
    )

    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_snapshots.id", ondelete="CASCADE"), nullable=False)
    verification_version: Mapped[str] = mapped_column(String(40), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    calculated_root_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_root_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    verified_partitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
