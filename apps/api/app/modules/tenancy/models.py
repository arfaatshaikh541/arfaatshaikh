import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TenantStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    READ_ONLY = "read_only"
    ARCHIVED = "archived"


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status", native_enum=False, length=20),
        nullable=False,
        default=TenantStatus.ACTIVE,
    )

    settings: Mapped["TenantSettings"] = relationship(back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    domains: Mapped[list["TenantDomain"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class TenantSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenant_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_tenant_settings_tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Dubai")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="AED")
    branding: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    business_hours: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    tenant: Mapped["Tenant"] = relationship(back_populates="settings")


class TenantDomain(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenant_domains"
    __table_args__ = (UniqueConstraint("domain", name="uq_tenant_domains_domain"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="domains")


class TenantCaptureToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A stable, unguessable public identifier for a tenant's public lead
    capture form(s) — deliberately distinct from the tenant's slug/UUID
    so the public capture endpoint never has to expose (or accept)
    anything that could be used to probe internal tenant identifiers.
    Looked up only by this token's own uniqueness, so — like invitations,
    sessions, and reset tokens — it is intentionally NOT row-level-
    secured; the token itself is the authorization proof."""

    __tablename__ = "tenant_capture_tokens"
    __table_args__ = (UniqueConstraint("token", name="uq_tenant_capture_tokens_token"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
