"""OpportunityLedger: CRUD for real, persisted Opportunity/Risk records.
Same real SQLite/SQLAlchemy pattern as every other durable subsystem in
this codebase -- what's recorded here survives a restart and is queryable
by the owner or a future workstream, but nothing in this module invents
what to record.
"""
from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ..memory.schema_migration import ensure_schema
from .models import OpportunityInput, OpportunityRecord


class OpportunityLedger:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        ensure_schema(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    def record(self, item: OpportunityInput) -> OpportunityRecord:
        with self._Session() as session:
            record = OpportunityRecord(
                kind=item.kind, category=item.category, summary=item.summary, evidence=item.evidence,
                confidence=item.confidence, estimated_impact=item.estimated_impact, effort=item.effort,
                recommended_next_action=item.recommended_next_action, source=item.source,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def get(self, item_id: str) -> OpportunityRecord | None:
        with self._Session() as session:
            return session.get(OpportunityRecord, item_id)

    def list_open(self, kind: str | None = None) -> list[OpportunityRecord]:
        with self._Session() as session:
            stmt = select(OpportunityRecord).where(OpportunityRecord.status == "open").order_by(OpportunityRecord.created_at.desc())
            if kind is not None:
                stmt = stmt.where(OpportunityRecord.kind == kind)
            return list(session.scalars(stmt))

    def set_status(self, item_id: str, status: str) -> None:
        with self._Session() as session:
            record = session.get(OpportunityRecord, item_id)
            if record is None:
                raise ValueError(f"no such opportunity/risk record '{item_id}'")
            record.status = status
            session.commit()
