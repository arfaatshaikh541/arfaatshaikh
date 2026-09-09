"""WorldModelStore: entities and typed relationships between them. This
is "what is true now" (docs/architecture/02-world-model-memory.md),
distinct from MemoryStore's episodic/decision layers which answer "what
happened." Same engine-per-store pattern as MemoryStore/PolicyEngine —
see memory/store.py's docstring for why that's fine at this scale.
"""
from __future__ import annotations

import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from .models import Entity, Relationship
from .schema_migration import ensure_schema


class WorldModelStore:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        ensure_schema(self._engine)
        self._Session: sessionmaker[Session] = sessionmaker(bind=self._engine)

    def upsert_entity(
        self, *, entity_type: str, name: str, source: str,
        attributes: dict | None = None, entity_id: str | None = None,
    ) -> Entity:
        """Creates a new entity, or updates an existing one by id if
        entity_id is given and found — a real update, not a new version,
        since an entity's current attributes are exactly what "what is
        true now" means (contrast with SemanticFact's supersession model
        for facts where the history of belief matters)."""
        with self._Session() as session:
            entity = session.get(Entity, entity_id) if entity_id else None
            if entity is None:
                kwargs = {"id": entity_id} if entity_id else {}
                entity = Entity(
                    entity_type=entity_type, name=name, source=source,
                    attributes_json=json.dumps(attributes or {}), **kwargs,
                )
                session.add(entity)
            else:
                entity.name = name
                entity.attributes_json = json.dumps(attributes or {})
                entity.source = source
            session.commit()
            session.refresh(entity)
            return entity

    def get_entity(self, entity_id: str) -> Entity | None:
        with self._Session() as session:
            return session.get(Entity, entity_id)

    def find_entities(self, *, entity_type: str | None = None, name_contains: str | None = None) -> list[Entity]:
        with self._Session() as session:
            stmt = select(Entity)
            if entity_type:
                stmt = stmt.where(Entity.entity_type == entity_type)
            if name_contains:
                stmt = stmt.where(Entity.name.contains(name_contains))
            return list(session.scalars(stmt))

    def link(self, *, subject_id: str, predicate: str, object_id: str, source: str) -> Relationship:
        with self._Session() as session:
            relationship = Relationship(subject_id=subject_id, predicate=predicate, object_id=object_id, source=source)
            session.add(relationship)
            session.commit()
            session.refresh(relationship)
            return relationship

    def relationships_from(self, subject_id: str, predicate: str | None = None) -> list[Relationship]:
        with self._Session() as session:
            stmt = select(Relationship).where(Relationship.subject_id == subject_id)
            if predicate:
                stmt = stmt.where(Relationship.predicate == predicate)
            return list(session.scalars(stmt))

    def relationships_to(self, object_id: str, predicate: str | None = None) -> list[Relationship]:
        with self._Session() as session:
            stmt = select(Relationship).where(Relationship.object_id == object_id)
            if predicate:
                stmt = stmt.where(Relationship.predicate == predicate)
            return list(session.scalars(stmt))
