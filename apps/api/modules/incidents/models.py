from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

SEVERITY_LEVELS = ("critical", "high", "medium", "low")
INCIDENT_STATUSES = ("declared", "investigating", "contained", "resolved", "closed")


class Incident(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """A coordinating narrative over one or more findings/assets — not a
    control mechanism over them. Closing an incident deliberately does not
    change the status of any linked finding (some may already be
    remediated, some accepted-risk, some left deliberately open) — see
    docs/project-status.md's Milestone 5 architecture notes.

    The timeline (declared/status-changed/note-added/linked/closed/
    reopened events) is NOT a dedicated table here — it reuses the
    generic `audit_logs` ledger via `modules.audit.service`, the same
    decision Milestone 3 made for a finding's activity timeline, since an
    incident's history is the same shape (a sequence of discrete named
    events) `audit_logs` already models."""

    __tablename__ = "incidents"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    severity: Mapped[str] = mapped_column(Enum(*SEVERITY_LEVELS, name="incident_severity"), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(*INCIDENT_STATUSES, name="incident_status"), nullable=False, default="declared", index=True
    )
    declared_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    declared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closure_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class IncidentFinding(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "incident_findings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "incident_id", "finding_id", name="uq_incident_findings_pair"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True
    )


class IncidentAsset(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "incident_assets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "incident_id", "asset_id", name="uq_incident_assets_pair"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
