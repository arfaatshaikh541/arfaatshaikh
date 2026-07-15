from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

CREDENTIAL_HEALTH_STATUSES = ("healthy", "degraded", "expired", "revoked")


class IntegrationCredential(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Encrypted-at-rest provider credential. `ciphertext`/`nonce`/
    `wrapped_dek` are opaque outside modules.credential_vault.service —
    nothing else in the codebase decrypts these directly, and no API route
    ever returns these fields (see schemas.py — response models omit them
    entirely, not just mask them).

    Milestone 1 foundation: this table stands alone (no FK to a tenant
    integration catalogue yet — that lands with the connector SDK in
    Milestone 2, which will add `tenant_integration_id`)."""

    __tablename__ = "integration_credentials"

    provider_key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)

    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    wrapped_dek: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(nullable=False)

    health_status: Mapped[str] = mapped_column(
        Enum(*CREDENTIAL_HEALTH_STATUSES, name="credential_health_status"),
        nullable=False,
        default="healthy",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
