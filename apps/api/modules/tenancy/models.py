from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

TENANT_STATUSES = ("trial", "active", "read_only", "suspended", "archived")


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(
        Enum(*TENANT_STATUSES, name="tenant_status"), nullable=False, default="trial"
    )
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    settings: Mapped[TenantSettings] = relationship(
        back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )
    security_profile: Mapped[TenantSecurityProfile] = relationship(
        back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )
    domains: Mapped[list[TenantDomain]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class TenantSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenant_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_tenant_settings_tenant"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    default_automation_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="guided"
    )
    branding_logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    tenant: Mapped[Tenant] = relationship(back_populates="settings")


class TenantSecurityProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Security posture toggles that gate sensitive tenant-level behaviour
    — e.g. whether step-up auth is mandatory for disruptive approvals."""

    __tablename__ = "tenant_security_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_tenant_security_profile_tenant"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    require_mfa_for_admins: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    require_step_up_for_disruptive_actions: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    session_ttl_seconds: Mapped[int] = mapped_column(nullable=False, default=43200)

    tenant: Mapped[Tenant] = relationship(back_populates="security_profile")


class TenantDomain(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Ownership-verified domains — the attack-surface perimeter a tenant
    claims as their own. `modules.attack_surface` (Milestone 11) is what
    finally verifies these; this table stayed dormant since Milestone 1
    (schema only, no service/routes) until then.

    Verification is HTTP-file based (`GET https://{domain}/.well-known/
    gridkeep-verification.txt` must contain `verification_token`) rather
    than the DNS TXT this docstring originally named as the mechanism —
    a deliberate substitution, not a shortcut: raw DNS queries are
    network-blocked in the environment this was built in, and unlike a
    mock connector's demo data, faking a real ownership check would
    defeat its actual security purpose rather than just simulate it.
    DNS TXT and email verification remain reasonable future methods."""

    __tablename__ = "tenant_domains"
    __table_args__ = (UniqueConstraint("domain", name="uq_tenant_domains_domain"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    verification_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped[Tenant] = relationship(back_populates="domains")
