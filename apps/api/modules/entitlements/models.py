from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

OVERRIDE_TYPES = ("grant", "revoke")


class TenantFeatureOverride(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-tenant deltas on top of plan entitlement — trial extensions,
    custom deals, temporary revocations. Always the most-specific layer in
    entitlement resolution (see service.resolve_entitlements)."""

    __tablename__ = "tenant_feature_overrides"
    __table_args__ = (
        UniqueConstraint("tenant_id", "feature_id", name="uq_tenant_feature_overrides_pair"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("features.id", ondelete="CASCADE"), nullable=False
    )
    override_type: Mapped[str] = mapped_column(String(10), nullable=False)
    limit_value: Mapped[int | None] = mapped_column(nullable=True)
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UsageMetric(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Catalogue of countable usage dimensions (assets, identities,
    automated_actions, playbook_runs, evidence_storage_mb, ...)."""

    __tablename__ = "usage_metrics"

    key: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="count")


class UsageRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "usage_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "metric_id", "period_start", name="uq_usage_records_period"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usage_metrics.id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False, default=0)

    metric: Mapped[UsageMetric] = relationship()


class FeatureLimit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Default consumption caps per plan-feature-metric triple; a
    TenantFeatureOverride or TenantAddOn can raise/lower the effective
    limit for a specific tenant."""

    __tablename__ = "feature_limits"
    __table_args__ = (UniqueConstraint("feature_id", "metric_id", name="uq_feature_limits_pair"),)

    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("features.id", ondelete="CASCADE"), nullable=False
    )
    metric_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usage_metrics.id", ondelete="CASCADE"), nullable=False
    )
    limit_value: Mapped[int] = mapped_column(nullable=False)
