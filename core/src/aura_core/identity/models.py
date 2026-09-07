"""Owner enrollment schema: exactly one Owner per installation, and zero
or more DeviceTrust records naming machines that have proven possession
of a token issued at enrollment time. Shares the same Base/database as
every other store in this codebase (see memory/models.py) -- there is
one SQLite file, not a separate identity store to keep in sync.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ..memory.models import Base, _now, _uuid


class Owner(Base):
    __tablename__ = "owners"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DeviceTrust(Base):
    __tablename__ = "device_trusts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(String(36))
    label: Mapped[str] = mapped_column(String(200))
    # Only ever the SHA-256 hash of the token is stored -- the raw value
    # is shown to the owner exactly once, at issuance, and never again.
    token_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
