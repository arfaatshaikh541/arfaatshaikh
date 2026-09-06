"""Persistent memory schema.

Implements the provenance envelope specified in
docs/architecture/02-world-model-memory.md for four of the ten documented
memory systems: Episodic, Semantic (with contradiction detection),
Decision, and Commitment. The remaining six (Working, Procedural,
Relationship, Failure, Creative, Business) are designed in that document
but not yet implemented as tables here — they are real future work, not
silently assumed to exist.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ProvenanceMixin:
    """Common envelope fields required on every memory record."""

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    sensitivity: Mapped[str] = mapped_column(String(20), default="internal")
    owner: Mapped[str] = mapped_column(String(200), default="owner")
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    supersedes_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    superseded_by_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    retention_policy: Mapped[str] = mapped_column(String(50), default="standard")


class EpisodicEvent(ProvenanceMixin, Base):
    """What happened and when."""

    __tablename__ = "episodic_events"

    event_type: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SemanticFact(ProvenanceMixin, Base):
    """Durable facts about the business world, as subject/predicate/object
    triples so new relationship shapes don't require schema migrations."""

    __tablename__ = "semantic_facts"

    subject: Mapped[str] = mapped_column(String(200), index=True)
    predicate: Mapped[str] = mapped_column(String(100), index=True)
    object: Mapped[str] = mapped_column(Text)


class Decision(ProvenanceMixin, Base):
    """A decision made, with the reasoning behind it. Backs the
    'why did you make that decision' owner command."""

    __tablename__ = "decisions"

    goal: Mapped[str] = mapped_column(String(300))
    statement: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text)


class Commitment(ProvenanceMixin, Base):
    """A promise, deadline, or obligation."""

    __tablename__ = "commitments"

    description: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|fulfilled|broken
