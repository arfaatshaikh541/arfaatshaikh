"""Platform support-access foundation.

SupportAccessGrant is a time-boxed, reason-logged, revocable grant that
lets a platform-role user read a specific tenant's data for support
purposes. It is not standing impersonation: every grant has an expiry,
every grant creation/use is written to `platform_audit_logs`, and a grant
never elevates the platform user's *write* permissions inside the tenant -
Milestone 1 wires the grant/revoke lifecycle and the audit trail; the
support-facing read UI is out of scope until a later milestone.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPKMixin


class SupportAccessGrant(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "support_access_grants"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
