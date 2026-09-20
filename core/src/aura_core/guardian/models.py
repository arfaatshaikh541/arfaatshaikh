"""Security Guardian's own persistence: a log only Guardian writes to. Per
docs/adr/0003-security-guardian-separate-trust-boundary.md, no other
component in this codebase writes to guardian_events — that separation is
enforced by which modules import this one, not by a runtime permission
check (this is a single Python process; true process/credential
isolation is future work, tracked in docs/project-status.md).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..memory.models import Base, _now, _uuid


class GuardianEvent(Base):
    __tablename__ = "guardian_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    rule_name: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(Text)
    action_taken: Mapped[str] = mapped_column(String(50))  # KILL_SWITCH_ENGAGED | LOGGED_ONLY
