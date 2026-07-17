"""Subscription and entitlement catalog/assignment models.

SubscriptionPlan, Feature, PlanFeature and AddOn are global platform
catalog data (not tenant-owned). TenantSubscription, TenantAddOn and
FeatureOverride are tenant-owned assignments of that catalog to a specific
tenant.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPKMixin


class Feature(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "features"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    value_type: Mapped[str] = mapped_column(
        String(20), default="boolean", nullable=False
    )  # boolean | limit


class SubscriptionPlan(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "subscription_plans"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    monthly_price_usd: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    monthly_credit_grant: Mapped[int] = mapped_column(default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PlanFeature(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "plan_features"
    __table_args__ = (
        UniqueConstraint("plan_id", "feature_id", name="uq_plan_features_plan_feature"),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class AddOn(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "add_ons"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    feature_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("features.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    monthly_price_usd: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)


class TenantSubscription(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "tenant_subscriptions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TenantAddOn(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "tenant_add_ons"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    add_on_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("add_ons.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)


class FeatureOverride(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "feature_overrides"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("features.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
