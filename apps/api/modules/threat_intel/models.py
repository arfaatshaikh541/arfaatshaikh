from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ThreatIndicator(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """A stored indicator of compromise (IOC) from a threat-intelligence
    feed — deliberately NOT an `Asset`. `modules.assets.ingestion` has
    documented since Milestone 2 that indicator records are skipped by
    the asset graph because they describe external threats, not
    infrastructure the tenant owns; this table is that "different
    subsystem" finally landing.

    `indicator_type` is a free string, not a Postgres enum, since a real
    threat-intel feed's vocabulary (ip, domain, hash, url, email, ...) is
    open-ended and connector-defined — adding a new type should never
    require a migration, the same reasoning `AssetType.category` already
    used."""

    __tablename__ = "threat_indicators"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uq_threat_indicators_tenant_external_id"),
    )

    tenant_integration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_integrations.id", ondelete="SET NULL"), nullable=True
    )
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    indicator_type: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.5)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
