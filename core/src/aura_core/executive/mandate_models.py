"""Mandate schema: the persistent, restart-durable directive a "Run
Gridkeep"-style instruction becomes, per the operating-loop product
specification. A Mandate owns zero or more workstreams (Goal rows linked
via Goal.mandate_id) and is never itself the unit of execution -- only
its workstreams are, through the existing Action-Broker-gated pipeline.
Mandate activation enforces the same "cannot activate without the fields
that make it governable" discipline GoalEngine already enforces for
goals, for the same reason: an ungoverned autonomous directive is a
liability, not a feature.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..memory.models import Base, _now, _uuid

MANDATE_STATUSES = ("draft", "active", "paused", "completed", "cancelled")

# Authority is deliberately coarser than PolicyEngine's per-action-type
# autonomy levels (0-5) -- it's a mandate-scoped ceiling on what its
# workstreams may even attempt, checked in addition to (never instead
# of) the real per-action Policy Engine evaluation.
MANDATE_AUTHORITY_LEVELS = ("advisory_only", "execute_green", "execute_amber_with_approval", "full")


class Mandate(Base):
    __tablename__ = "mandates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner: Mapped[str] = mapped_column(String(200), default="owner")
    title: Mapped[str] = mapped_column(String(300))
    mission: Mapped[str] = mapped_column(Text)
    authority: Mapped[str] = mapped_column(String(40), default="advisory_only")
    risk_ceiling: Mapped[str] = mapped_column(String(10), default="GREEN")  # GREEN|AMBER|RED
    policy_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    priority: Mapped[int] = mapped_column(Integer, default=3)
    objectives_json: Mapped[str] = mapped_column(Text, default="[]")
    kpis_json: Mapped[str] = mapped_column(Text, default="[]")  # [{"name":..., "target":..., "current":...}]
    constraints_json: Mapped[str] = mapped_column(Text, default="[]")
    linked_entity_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    observation_interval_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latest_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_actions_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
