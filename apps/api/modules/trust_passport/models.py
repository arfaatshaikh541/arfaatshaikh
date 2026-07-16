from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class TrustPassportSettings(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """One row per tenant, same lazy-singleton shape as
    `modules.actions.models.TenantAutomationSetting` — absence of a row
    means "never configured," not published.

    `public_slug` is stored in plaintext, deliberately unlike session or
    invitation tokens: those are secrets that grant a privileged action if
    leaked, so they're hashed at rest. This slug IS the public identifier
    — it's designed to be shared and put in a URL, so there's nothing to
    protect by hashing it.

    Row-level security here is intentionally not the standard
    `_SIMPLE_TENANT_TABLES` shape: SELECT is widened (same precedent as
    `memberships`) so an anonymous request can look this row up by slug
    when `is_published` is true, while INSERT/UPDATE/DELETE stay strictly
    tenant-scoped — see the Milestone 9 RLS migration."""

    __tablename__ = "trust_passport_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_trust_passport_settings_tenant"),)

    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    public_slug: Mapped[str | None] = mapped_column(String(60), unique=True, nullable=True, index=True)
    headline: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    show_compliance_frameworks: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
