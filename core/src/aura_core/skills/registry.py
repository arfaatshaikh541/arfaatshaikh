"""SkillRegistry: CRUD for persisted Skills, backed by the same real
SQLite/SQLAlchemy pattern (and the same additive `ensure_schema`
migration) every other durable subsystem in this codebase uses. A Skill
created in one process is reachable in the next -- "preserve it for
future use" is a real property of this storage, not an aspiration.
"""
from __future__ import annotations

import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ..memory.schema_migration import ensure_schema
from .models import SkillRecord, SkillStep


class SkillRegistry:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        ensure_schema(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    def create(self, name: str, description: str, domain: str, steps: list[SkillStep], created_by: str = "owner") -> SkillRecord:
        with self._Session() as session:
            record = SkillRecord(
                name=name, description=description, domain=domain,
                steps_json=json.dumps([s.to_dict() for s in steps]), created_by=created_by,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def get(self, skill_id: str) -> SkillRecord | None:
        with self._Session() as session:
            return session.get(SkillRecord, skill_id)

    def get_by_name(self, name: str) -> SkillRecord | None:
        with self._Session() as session:
            stmt = select(SkillRecord).where(SkillRecord.name == name).order_by(SkillRecord.created_at.desc())
            return session.scalars(stmt).first()

    def list_all(self) -> list[SkillRecord]:
        with self._Session() as session:
            return list(session.scalars(select(SkillRecord).order_by(SkillRecord.created_at.desc())))

    def list_by_domain(self, domain: str) -> list[SkillRecord]:
        with self._Session() as session:
            stmt = select(SkillRecord).where(SkillRecord.domain == domain).order_by(SkillRecord.created_at.desc())
            return list(session.scalars(stmt))
