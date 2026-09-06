"""Durable task schema. A native, SQLite-backed engine rather than
Temporal (docs/architecture/11-technology-stack.md's long-term pick) —
same pragmatic-now/swap-later pattern as ADR 0004's Policy Engine choice.
See docs/adr/0005-native-task-engine-not-temporal.md.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..memory.models import Base, _now, _uuid

TASK_STATUSES = (
    "QUEUED", "RUNNING", "WAITING", "BLOCKED", "NEEDS_APPROVAL",
    "RETRYING", "COMPLETED", "FAILED", "CANCELLED",
)


class TaskRecord(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_type: Mapped[str] = mapped_column(String(150))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    depends_on_json: Mapped[str] = mapped_column(Text, default="[]")  # list[str] of task ids
    lease_owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
