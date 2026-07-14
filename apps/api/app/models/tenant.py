import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_uuid

TENANT_STATUSES = ("active", "suspended", "archived")


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    public_key: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, default=new_uuid, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Dubai")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="AED")

    settings: Mapped["TenantSettings"] = relationship(
        back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )
    domains: Mapped[list["TenantDomain"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    features: Mapped[list["TenantFeature"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Tenant {self.slug!r} status={self.status!r}>"


class TenantSettings(TimestampMixin, Base):
    __tablename__ = "tenant_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    logo_url: Mapped[str | None] = mapped_column(Text)
    brand_primary_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#F97316")
    brand_secondary_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#111827")
    contact_email: Mapped[str | None] = mapped_column(String(320))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    business_hours: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    data_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=730)
    privacy_text: Mapped[str | None] = mapped_column(Text)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped["Tenant"] = relationship(back_populates="settings")


class TenantDomain(TimestampMixin, Base):
    __tablename__ = "tenant_domains"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped["Tenant"] = relationship(back_populates="domains")


class TenantFeature(TimestampMixin, Base):
    __tablename__ = "tenant_features"
    __table_args__ = (UniqueConstraint("tenant_id", "feature_key", name="uq_tenant_feature"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_key: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="features")
