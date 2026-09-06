"""MemoryStore: the CRUD + query API over the memory schema.

This is the only path any caller (deterministic actions, the model router's
context assembly, the API) uses to read or write memory — nothing talks to
the SQLAlchemy session directly. That's what makes provenance and
contradiction detection actually enforced rather than optional per-caller
discipline.
"""
from __future__ import annotations

import math
import re
from collections import Counter
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


@dataclass
class MemorySearchResult:
    kind: str  # "event" | "fact" | "decision" | "commitment"
    id: str
    text: str
    score: float
    created_at: datetime


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _tfidf_cosine_scores(query_tokens: list[str], doc_tokens: list[list[str]]) -> list[float]:
    """Deliberately stdlib-only -- no new dependency for what's still a
    thousands-of-rows-not-millions search over the current table
    contents, recomputed at query time rather than kept in a separate
    index that could drift out of sync with the actual data. Standard
    smoothed IDF (matches scikit-learn's default formula) so a term
    appearing in every document doesn't get an IDF of zero."""
    doc_count = len(doc_tokens)
    document_frequency: Counter[str] = Counter()
    for tokens in doc_tokens:
        document_frequency.update(set(tokens))

    def idf(term: str) -> float:
        df = document_frequency.get(term, 0)
        return math.log((1 + doc_count) / (1 + df)) + 1.0

    def vectorize(tokens: list[str]) -> dict[str, float]:
        counts = Counter(tokens)
        return {term: count * idf(term) for term, count in counts.items()}

    def cosine(a: dict[str, float], b: dict[str, float]) -> float:
        shared = set(a) & set(b)
        dot = sum(a[t] * b[t] for t in shared)
        norm_a = math.sqrt(sum(v * v for v in a.values()))
        norm_b = math.sqrt(sum(v * v for v in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    query_vector = vectorize(query_tokens)
    return [cosine(query_vector, vectorize(tokens)) for tokens in doc_tokens]


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
    def record_decision(
        self, *, goal: str, statement: str, reasoning: str, source: str, supersedes_id: str | None = None,
    ) -> Decision:
        with self._Session() as session:
            # id generated explicitly (not left to the column's flush-time
            # default) because, when supersedes_id is given, the prior
            # decision's superseded_by_id needs this id before commit --
            # the same fix this codebase already needed once before for a
            # SQLAlchemy Python-side default not being materialized early
            # enough (see memory/store.py's assert_fact).
            new_id = _uuid()
            decision = Decision(
                id=new_id, goal=goal, statement=statement, reasoning=reasoning,
                source=source, supersedes_id=supersedes_id,
            )
            if supersedes_id:
                prior = session.get(Decision, supersedes_id)
                if prior is not None:
                    prior.superseded_by_id = new_id
            session.add(decision)
            session.commit()
            session.refresh(decision)
            return decision

    def decisions_for_goal(self, goal: str) -> list[Decision]:
        with self._Session() as session:
            stmt = select(Decision).where(Decision.goal == goal).order_by(Decision.created_at)
            return list(session.scalars(stmt))

    def decision_chain(self, decision_id: str) -> list[Decision]:
        """Walks the full supersession lineage of one decision -- back to
        the original, forward through every amendment -- in chronological
        order. This is what lets "why did we decide X, and has that
        changed" be answered honestly instead of returning only whichever
        single row a search happened to rank first."""
        with self._Session() as session:
            start = session.get(Decision, decision_id)
            if start is None:
                return []

            chain = [start]
            cursor = start
            while cursor.supersedes_id:
                cursor = session.get(Decision, cursor.supersedes_id)
                if cursor is None:
                    break
                chain.insert(0, cursor)

            cursor = start
            while cursor.superseded_by_id:
                cursor = session.get(Decision, cursor.superseded_by_id)
                if cursor is None:
                    break
                chain.append(cursor)

            return chain

    # -- Cross-cutting free-text search -------------------------------------
    def search(self, query: str, limit: int = 10, kinds: list[str] | None = None) -> list[MemorySearchResult]:
        """TF-IDF cosine search across every memory kind at once, ranked
        by relevance -- the retrieval primitive "why did we decide to
        charge Gridkeep customers that way" needs, since that question
        names no goal id or exact subject string to look up directly."""
        with self._Session() as session:
            candidates: list[tuple[str, str, str, datetime]] = []
            if kinds is None or "event" in kinds:
                for e in session.scalars(select(EpisodicEvent)):
                    candidates.append(("event", e.id, e.summary, e.created_at))
            if kinds is None or "fact" in kinds:
                stmt = select(SemanticFact).where(SemanticFact.superseded_by_id.is_(None))
                for f in session.scalars(stmt):
                    candidates.append(("fact", f.id, f"{f.subject} {f.predicate} {f.object}", f.created_at))
            if kinds is None or "decision" in kinds:
                for d in session.scalars(select(Decision)):
                    candidates.append(("decision", d.id, f"{d.statement} {d.reasoning}", d.created_at))
            if kinds is None or "commitment" in kinds:
                for c in session.scalars(select(Commitment)):
                    candidates.append(("commitment", c.id, c.description, c.created_at))

        if not candidates:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        doc_tokens = [_tokenize(text) for _, _, text, _ in candidates]
        scores = _tfidf_cosine_scores(query_tokens, doc_tokens)

        ranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)
        return [
            MemorySearchResult(kind=kind, id=id_, text=text, score=score, created_at=created_at)
            for (kind, id_, text, created_at), score in ranked
            if score > 0
        ][:limit]

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
