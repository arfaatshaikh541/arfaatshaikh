import uuid

from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog, FeatureChangeLog, SupportAccessLog
from app.modules.audit.repository import (
    AuditLogRepository,
    FeatureChangeLogRepository,
    SupportAccessLogRepository,
)


def log_event(
    db: Session, *, tenant_id: uuid.UUID | None, actor_user_id: uuid.UUID | None, action: str,
    entity_type: str, entity_id: uuid.UUID | None = None, before: dict | None = None, after: dict | None = None,
) -> AuditLog:
    """Writes one immutable audit entry. Call this from every module's
    service layer after a mutation that touches auth, tenancy, roles,
    subscriptions, or entitlements — never skip it for those categories."""
    return AuditLogRepository(db).create(
        tenant_id=tenant_id, actor_user_id=actor_user_id, action=action,
        entity_type=entity_type, entity_id=entity_id, before=before, after=after,
    )


def log_support_access(db: Session, *, tenant_id: uuid.UUID, platform_admin_user_id: uuid.UUID, reason: str, resource: str) -> SupportAccessLog:
    return SupportAccessLogRepository(db).create(
        tenant_id=tenant_id, platform_admin_user_id=platform_admin_user_id, reason=reason, resource=resource
    )


def log_feature_change(db: Session, *, tenant_id: uuid.UUID, changed_by: uuid.UUID | None, change_type: str, details: dict) -> FeatureChangeLog:
    return FeatureChangeLogRepository(db).create(
        tenant_id=tenant_id, changed_by=changed_by, change_type=change_type, details=details
    )


def list_tenant_audit_logs(db: Session, tenant_id: uuid.UUID, *, limit: int = 100, offset: int = 0) -> list[AuditLog]:
    return AuditLogRepository(db).list_for_tenant(tenant_id, limit=limit, offset=offset)


def list_all_audit_logs(db: Session, *, limit: int = 100, offset: int = 0) -> list[AuditLog]:
    return AuditLogRepository(db).list_all(limit=limit, offset=offset)


def list_support_access_logs(db: Session, *, limit: int = 100, offset: int = 0) -> list[SupportAccessLog]:
    return SupportAccessLogRepository(db).list_all(limit=limit, offset=offset)
