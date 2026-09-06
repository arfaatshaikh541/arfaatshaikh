"""Goal schema per docs/architecture/03-goal-engine.md. A goal cannot
become 'active' without success_metric, budget, and at least one stop
condition — enforced by GoalEngine, not merely documented."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..memory.models import Base, _now, _uuid

GOAL_STATUSES = ("draft", "active", "paused", "completed", "abandoned")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner: Mapped[str] = mapped_column(String(200), default="owner")
    statement: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    success_metric: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraints_json: Mapped[str] = mapped_column(Text, default="[]")
    budget_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_actions_json: Mapped[str] = mapped_column(Text, default="[]")
    prohibited_actions_json: Mapped[str] = mapped_column(Text, default="[]")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    review_interval_seconds: Mapped[int] = mapped_column(Integer, default=86400)
    stop_conditions_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
