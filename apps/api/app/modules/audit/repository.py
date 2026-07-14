import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog, FeatureChangeLog, SupportAccessLog


class AuditLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, *, tenant_id: uuid.UUID | None, actor_user_id: uuid.UUID | None, action: str,
        entity_type: str, entity_id: uuid.UUID | None, before: dict | None, after: dict | None,
    ) -> AuditLog:
        entry = AuditLog(
            tenant_id=tenant_id, actor_user_id=actor_user_id, action=action, entity_type=entity_type,
            entity_id=entity_id, before=before, after=after,
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_for_tenant(self, tenant_id: uuid.UUID, *, limit: int = 100, offset: int = 0) -> list[AuditLog]:
        return list(
            self.db.execute(
                select(AuditLog)
                .where(AuditLog.tenant_id == tenant_id)
                .order_by(AuditLog.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )

    def list_all(self, *, limit: int = 100, offset: int = 0) -> list[AuditLog]:
        return list(
            self.db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset))
            .scalars()
            .all()
        )


class SupportAccessLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, tenant_id: uuid.UUID, platform_admin_user_id: uuid.UUID, reason: str, resource: str) -> SupportAccessLog:
        entry = SupportAccessLog(
            tenant_id=tenant_id, platform_admin_user_id=platform_admin_user_id, reason=reason, resource=resource
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_all(self, *, limit: int = 100, offset: int = 0) -> list[SupportAccessLog]:
        return list(
            self.db.execute(
                select(SupportAccessLog).order_by(SupportAccessLog.created_at.desc()).limit(limit).offset(offset)
            )
            .scalars()
            .all()
        )


class FeatureChangeLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, tenant_id: uuid.UUID, changed_by: uuid.UUID | None, change_type: str, details: dict) -> FeatureChangeLog:
        entry = FeatureChangeLog(tenant_id=tenant_id, changed_by=changed_by, change_type=change_type, details=details)
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_for_tenant(self, tenant_id: uuid.UUID, *, limit: int = 100, offset: int = 0) -> list[FeatureChangeLog]:
        return list(
            self.db.execute(
                select(FeatureChangeLog)
                .where(FeatureChangeLog.tenant_id == tenant_id)
                .order_by(FeatureChangeLog.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
