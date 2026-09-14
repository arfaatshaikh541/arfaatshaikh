from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeSyncNode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_nodes"
    __table_args__ = (
        CheckConstraint("status IN ('pending','trusted','suspended','revoked')", name="ck_knowledge_sync_node_status"),
        CheckConstraint("trust_level IN ('restricted','standard','high')", name="ck_knowledge_sync_node_trust_level"),
        UniqueConstraint("organisation_id", "slug", name="uq_knowledge_sync_node_org_slug"),
    )

    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    public_key_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    trust_level: Mapped[str] = mapped_column(String(16), nullable=False, default="restricted", server_default="restricted")
    allowed_domains: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")


class KnowledgeSyncTrustPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_trust_policies"
    __table_args__ = (
        CheckConstraint("direction IN ('pull','push','bidirectional')", name="ck_knowledge_sync_policy_direction"),
        UniqueConstraint("organisation_id", "node_id", name="uq_knowledge_sync_policy_org_node"),
    )

    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_nodes.id", ondelete="CASCADE"), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default="pull", server_default="pull")
    allowed_content_types: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    require_signature: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    require_scholarly_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    max_items_per_run: Mapped[int] = mapped_column(Integer, nullable=False, default=1000, server_default="1000")


class KnowledgeSyncRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_runs"
    __table_args__ = (
        CheckConstraint("status IN ('planned','running','completed','partial','failed','cancelled')", name="ck_knowledge_sync_run_status"),
        CheckConstraint("direction IN ('pull','push')", name="ck_knowledge_sync_run_direction"),
        Index("ix_knowledge_sync_run_node_status", "node_id", "status"),
    )

    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_nodes.id", ondelete="RESTRICT"), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="planned", server_default="planned")
    request_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_checkpoint: Mapped[str | None] = mapped_column(String(200), nullable=True)
    next_checkpoint: Mapped[str | None] = mapped_column(String(200), nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class KnowledgeSyncItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_items"
    __table_args__ = (
        CheckConstraint("status IN ('pending','accepted','rejected','conflict')", name="ck_knowledge_sync_item_status"),
        UniqueConstraint("run_id", "external_id", "content_version", name="uq_knowledge_sync_item_run_external_version"),
        Index("ix_knowledge_sync_item_run_status", "run_id", "status"),
    )

    run_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_runs.id", ondelete="CASCADE"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False)
    content_version: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    reason_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")


class KnowledgeSyncConflict(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_conflicts"
    __table_args__ = (
        CheckConstraint("resolution IN ('pending','keep_local','accept_remote','manual_merge','reject_remote')", name="ck_knowledge_sync_conflict_resolution"),
        UniqueConstraint("run_id", "external_id", name="uq_knowledge_sync_conflict_run_external"),
    )

    run_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_runs.id", ondelete="CASCADE"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    local_version: Mapped[str] = mapped_column(String(80), nullable=False)
    remote_version: Mapped[str] = mapped_column(String(80), nullable=False)
    local_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    remote_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    resolution: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    resolution_evidence_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)


class KnowledgeSyncAuditEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_audit_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence_number", name="uq_knowledge_sync_audit_run_sequence"),
        Index("ix_knowledge_sync_audit_run", "run_id"),
    )

    run_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_runs.id", ondelete="CASCADE"), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_event_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
