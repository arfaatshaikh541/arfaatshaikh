"""MemoryStore: the CRUD + query API over the memory schema.

This is the only path any caller (deterministic actions, the model router's
context assembly, the API) uses to read or write memory — nothing talks to
the SQLAlchemy session directly. That's what makes provenance and
contradiction detection actually enforced rather than optional per-caller
discipline.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Commitment, Decision, EpisodicEvent, SemanticFact, _uuid


@dataclass
class ContradictionWarning:
    existing_fact_id: str
    subject: str
    predicate: str
    existing_object: str
    new_object: str


class MemoryStore:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        Base.metadata.create_all(self._engine)
        self._Session: sessionmaker[Session] = sessionmaker(bind=self._engine)

    # -- Episodic ---------------------------------------------------------
    def record_event(self, *, event_type: str, summary: str, source: str,
                      occurred_at: datetime | None = None) -> EpisodicEvent:
        with self._Session() as session:
            event = EpisodicEvent(
                event_type=event_type,
                summary=summary,
                source=source,
                occurred_at=occurred_at or datetime.now(timezone.utc),
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            return event

    def events_since(self, since: datetime) -> list[EpisodicEvent]:
        with self._Session() as session:
            stmt = select(EpisodicEvent).where(EpisodicEvent.occurred_at >= since).order_by(EpisodicEvent.occurred_at)
            return list(session.scalars(stmt))

    # -- Semantic (with contradiction detection) ---------------------------
    def assert_fact(self, *, subject: str, predicate: str, object: str, source: str,
                     confidence: float = 1.0) -> tuple[SemanticFact, ContradictionWarning | None]:
        with self._Session() as session:
            stmt = (
                select(SemanticFact)
                .where(SemanticFact.subject == subject, SemanticFact.predicate == predicate)
                .where(SemanticFact.superseded_by_id.is_(None))
                .order_by(SemanticFact.confidence.desc())
            )
            existing = session.scalars(stmt).first()

            warning: ContradictionWarning | None = None
            # id is generated explicitly (rather than left to the column's
            # flush-time default) because we need it below, before commit,
            # to link the existing fact's superseded_by_id.
            new_fact = SemanticFact(
                id=_uuid(),
                subject=subject, predicate=predicate, object=object,
                source=source, confidence=confidence,
            )

            if existing is not None and existing.object != object and existing.confidence >= 0.5:
                # Conflicting high-confidence fact: flag, do not silently overwrite.
                warning = ContradictionWarning(
                    existing_fact_id=existing.id,
                    subject=subject, predicate=predicate,
                    existing_object=existing.object, new_object=object,
                )
            elif existing is not None and existing.object != object:
                # Low-confidence prior fact: supersede cleanly.
                existing.superseded_by_id = new_fact.id
                new_fact.supersedes_id = existing.id

            session.add(new_fact)
            session.commit()
            session.refresh(new_fact)
            return new_fact, warning

    def resolve_contradiction(self, *, keep_fact_id: str, discard_fact_id: str) -> None:
        """Owner-driven correction: the discarded fact is marked superseded,
        never deleted, preserving the 'we used to believe X' trail."""
        with self._Session() as session:
            discard = session.get(SemanticFact, discard_fact_id)
            if discard is not None:
                discard.superseded_by_id = keep_fact_id
                session.commit()

    def facts_about(self, subject: str) -> list[SemanticFact]:
        with self._Session() as session:
            stmt = (
                select(SemanticFact)
                .where(SemanticFact.subject == subject, SemanticFact.superseded_by_id.is_(None))
            )
            return list(session.scalars(stmt))

    # -- Decision -----------------------------------------------------------
    def record_decision(self, *, goal: str, statement: str, reasoning: str, source: str) -> Decision:
        with self._Session() as session:
            decision = Decision(goal=goal, statement=statement, reasoning=reasoning, source=source)
            session.add(decision)
            session.commit()
            session.refresh(decision)
            return decision

    def decisions_for_goal(self, goal: str) -> list[Decision]:
        with self._Session() as session:
            stmt = select(Decision).where(Decision.goal == goal).order_by(Decision.created_at)
            return list(session.scalars(stmt))

    # -- Commitment -----------------------------------------------------------
    def add_commitment(self, *, description: str, source: str,
                        due_at: datetime | None = None) -> Commitment:
        with self._Session() as session:
            commitment = Commitment(description=description, source=source, due_at=due_at)
            session.add(commitment)
            session.commit()
            session.refresh(commitment)
            return commitment

    def open_commitments(self) -> list[Commitment]:
        with self._Session() as session:
            stmt = select(Commitment).where(Commitment.status == "open").order_by(Commitment.due_at)
            return list(session.scalars(stmt))

    def fulfill_commitment(self, commitment_id: str) -> None:
        with self._Session() as session:
            commitment = session.get(Commitment, commitment_id)
            if commitment is not None:
                commitment.status = "fulfilled"
                session.commit()
