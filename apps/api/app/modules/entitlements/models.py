import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TenantFeatureOverride(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Platform-admin-granted override for a single tenant/feature pair.

    Always wins over the plan's own configuration for that feature. An
    override with `config = {"enabled": false}` can also explicitly
    revoke a feature the plan would otherwise grant. `expires_at = NULL`
    means the override does not expire on its own (a trial would set
    `expires_at`).
    """

    __tablename__ = "tenant_feature_overrides"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("features.id", ondelete="CASCADE"), nullable=False, index=True
    )
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")


class UsageMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "usage_metrics"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="count")


class UsageRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Period-bucketed usage aggregate per tenant per metric.

    For point-in-time counters (e.g. `users`) `period` is always the first
    of the current month and the row is upserted in place under a row
    lock so concurrent requests cannot both slip past a limit. For
    cumulative-per-period counters (e.g. `messages_sent`) a new period
    row is created each month.
    """

    __tablename__ = "usage_records"
    __table_args__ = (UniqueConstraint("tenant_id", "metric_id", "period", name="uq_usage_records_tenant_metric_period"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usage_metrics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    period: Mapped[date] = mapped_column(Date, nullable=False)
