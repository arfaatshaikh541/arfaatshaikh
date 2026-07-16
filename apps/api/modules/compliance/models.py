from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin, utcnow

CONTROL_STATUSES = ("met", "partial", "not_met", "not_applicable")
EVIDENCE_TYPES = ("document", "url", "note")
EVIDENCE_TARGET_TYPES = ("compliance_control", "incident")


class ComplianceFramework(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Platform-wide catalogue, same shape and same reasoning as
    `modules.assets.models.AssetType` — a fixed, seeded list of frameworks
    (SOC 2, ISO 27001, ...), not something a tenant defines. Not
    tenant-scoped, no RLS: every tenant reads the same catalogue."""

    __tablename__ = "compliance_frameworks"

    key: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")


class ComplianceControl(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Also platform-wide — a control belongs to a framework, not a
    tenant. A tenant's per-control status lives separately in
    `TenantControlStatus`, the same "catalogue vs. tenant instance" split
    Milestone 2 used for `AssetType` vs. `Asset`."""

    __tablename__ = "compliance_controls"
    __table_args__ = (UniqueConstraint("framework_id", "key", name="uq_compliance_controls_framework_key"),)

    framework_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("compliance_frameworks.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TenantControlStatus(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """A tenant's own assessment of one control. Rows are created lazily —
    a control with no row yet is treated as `not_met` by the service layer
    (nothing has been assessed), so this table only ever holds controls a
    tenant has actually touched."""

    __tablename__ = "tenant_control_statuses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "control_id", name="uq_tenant_control_statuses_pair"),
    )

    control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("compliance_controls.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        Enum(*CONTROL_STATUSES, name="control_status"), nullable=False, default="not_met"
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class EvidenceRecord(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """A structured evidence entry — a title, description, and either a
    URL or a free-text note. Deliberately NOT a file upload: there is no
    object-storage client wired up anywhere in this codebase yet (the
    `object_storage_*` settings in `core/config.py` have sat unused since
    Milestone 1), so real document attachment is future work, not faked
    here with an untested upload path.

    `target_type`/`target_id` is the same polymorphic-target shape
    `audit_logs` already uses, reused deliberately rather than adding a
    fifth join-table pattern: evidence can attach to a compliance control
    or an incident. Which permission is required to *create* evidence
    depends on the target (`compliance.manage` or `incidents.manage` —
    see `modules.compliance.service`); `evidence.view`/`evidence.export`
    are the uniform read-side permissions that apply regardless of what
    the evidence is attached to."""

    __tablename__ = "evidence_records"

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_type: Mapped[str] = mapped_column(Enum(*EVIDENCE_TYPES, name="evidence_type"), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    target_type: Mapped[str] = mapped_column(
        Enum(*EVIDENCE_TARGET_TYPES, name="evidence_target_type"), nullable=False, index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
