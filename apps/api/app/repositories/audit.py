import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.audit import AuditLog


class AuditLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        event_type: str,
        tenant_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        metadata: dict | None = None,
        correlation_id: uuid.UUID | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            event_metadata=metadata or {},
            correlation_id=correlation_id,
            created_at=utcnow(),
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_for_tenant(self, tenant_id: uuid.UUID, *, limit: int = 100) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_for_entity(
        self, tenant_id: uuid.UUID, *, entity_type: str, entity_id: str, limit: int = 200
    ) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
