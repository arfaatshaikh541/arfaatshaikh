from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from modules.assets.models import Asset

SEVERITY_LEVELS = ("critical", "high", "medium", "low")
FINDING_STATUSES = ("open", "assigned", "remediated", "resolved", "accepted_risk", "false_positive")

# States a correlation re-run treats as "actively tracking" — a finding
# in one of these gets auto-resolved if its rule no longer matches, and
# gets its evidence/last_observed_at refreshed if it still does.
ACTIVE_STATUSES = ("open", "assigned", "accepted_risk")
# States a correlation re-run leaves untouched even when the asset no
# longer matches — a human decided these, not the engine.
TERMINAL_STATUSES = ("remediated", "false_positive")


class Finding(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """One security issue detected by the correlation engine
    (modules.findings.engine) against a single asset. `dedup_key`
    (`f"{rule_key}:{asset_id}"`) makes re-running correlation idempotent —
    the same condition on the same asset always maps to the same row,
    matching the dedup pattern Milestone 2 used for asset identifiers."""

    __tablename__ = "findings"
    __table_args__ = (UniqueConstraint("tenant_id", "dedup_key", name="uq_findings_tenant_dedup_key"),)

    rule_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    dedup_key: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(Enum(*SEVERITY_LEVELS, name="finding_severity"), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(*FINDING_STATUSES, name="finding_status"), nullable=False, default="open", index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_risk_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    asset: Mapped[Asset] = relationship()
