from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

SUPPORT_ACCESS_STATUSES = ("pending", "active", "expired", "revoked")


class SupportAccessGrant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Just-in-time, time-boxed, tenant-visible grant of read access for a
    platform staff member. There is no standing/impersonation access path
    anywhere else in the codebase — every platform_admin read of tenant
    data must resolve an active grant row here first (see deps.py
    `require_support_access_grant`), and every grant is itself an audited
    event (both creation and each use).

    Milestone 15: `requested_by_user_id` and `approved_by_user_id` are
    genuinely distinct actors now — a grant starts `pending` and only
    becomes `active` once a *different* platform user (also holding
    `platform.support_access`) approves it. `requested_duration_hours` is
    the window length the requester asked for, applied starting at
    approval time (not request time), since the clock on a support
    engineer's access shouldn't run before anyone has actually agreed to
    it."""

    __tablename__ = "support_access_grants"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    requested_duration_hours: Mapped[int | None] = mapped_column(nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
