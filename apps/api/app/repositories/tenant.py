import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import Tenant, TenantSettings


class TenantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self, *, slug: str, name: str, legal_name: str | None, timezone: str, currency: str
    ) -> Tenant:
        tenant = Tenant(
            slug=slug, name=name, legal_name=legal_name, timezone=timezone, currency=currency
        )
        self.db.add(tenant)
        self.db.flush()
        settings = TenantSettings(tenant_id=tenant.id)
        self.db.add(settings)
        self.db.flush()
        return tenant

    def get_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        return self.db.get(Tenant, tenant_id)

    def get_by_slug(self, slug: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.slug == slug)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_public_key(self, public_key: uuid.UUID) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.public_key == public_key)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(self, *, limit: int = 100, offset: int = 0) -> list[Tenant]:
        stmt = select(Tenant).order_by(Tenant.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.execute(stmt).scalars().all())

    def get_settings(self, tenant_id: uuid.UUID) -> TenantSettings | None:
        stmt = select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def set_status(self, tenant: Tenant, status: str) -> Tenant:
        tenant.status = status
        self.db.flush()
        return tenant
