from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.tenant import TenantRepository
from app.services.errors import NotFoundError


class PlatformService:
    """Platform super-admin operations. Every tenant-data access performed
    through this service is written to the immutable audit log, per
    docs/architecture/tenant-isolation-strategy.md."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.tenants = TenantRepository(db)
        self.audit = AuditLogRepository(db)

    def list_tenants(self, *, limit: int = 100, offset: int = 0) -> list[Tenant]:
        return self.tenants.list_all(limit=limit, offset=offset)

    def get_tenant_detail(self, *, actor: User, tenant_id: uuid.UUID) -> Tenant:
        tenant = self.tenants.get_by_id(tenant_id)
        if tenant is None:
            raise NotFoundError("Tenant not found.")
        self.audit.record(
            event_type="super_admin.tenant.viewed",
            tenant_id=tenant.id,
            actor_user_id=actor.id,
            entity_type="tenant",
            entity_id=str(tenant.id),
        )
        return tenant

    def set_tenant_status(
        self, *, actor: User, tenant_id: uuid.UUID, status: str, reason: str
    ) -> Tenant:
        tenant = self.tenants.get_by_id(tenant_id)
        if tenant is None:
            raise NotFoundError("Tenant not found.")
        previous_status = tenant.status
        tenant.status = status
        self.db.flush()
        self.audit.record(
            event_type="super_admin.tenant.status_changed",
            tenant_id=tenant.id,
            actor_user_id=actor.id,
            entity_type="tenant",
            entity_id=str(tenant.id),
            metadata={"from": previous_status, "to": status, "reason": reason},
        )
        return tenant
