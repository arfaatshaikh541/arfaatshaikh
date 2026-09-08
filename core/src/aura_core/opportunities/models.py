"""Opportunity and Risk records: the data contract sections 17-18 of the
product brief ask for (evidence, confidence, estimated impact, effort,
risk, recommended next action). This module is deliberately just the
ledger -- a place any real mechanism (a Skill, a scheduled task, a
future connector) can record something it found, and the owner or a
future workstream can query -- not a fabricated "opportunity detection
algorithm." Detecting real sales/marketing/security opportunities
requires real business data (World Model entities the owner's actual
usage populates) to reason over; inventing pattern-matching against an
empty/synthetic World Model would produce exactly the fabricated
"insights" this system exists to refuse. See
docs/UNIVERSAL_CAPABILITY_LAYER.md for what's built versus what remains
a real, named gap.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..memory.models import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OpportunityRecord(Base):
    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(50), default="opportunity")  # "opportunity" | "risk"
    category: Mapped[str] = mapped_column(String(100))  # "market" | "upsell" | "security" | "operational" | ...
    summary: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    estimated_impact: Mapped[str] = mapped_column(String(20), default="unknown")  # "low" | "medium" | "high"
    effort: Mapped[str] = mapped_column(String(20), default="unknown")
    recommended_next_action: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(200), default="owner")  # what surfaced this
    status: Mapped[str] = mapped_column(String(20), default="open")  # "open" | "acted_on" | "dismissed"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


@dataclass
class OpportunityInput:
    category: str
    summary: str
    evidence: str = ""
    confidence: float = 0.5
    estimated_impact: str = "unknown"
    effort: str = "unknown"
    recommended_next_action: str = ""
    source: str = "owner"
    kind: str = field(default="opportunity")
