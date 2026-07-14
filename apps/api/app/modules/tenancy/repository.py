import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.tenancy.models import Tenant, TenantDomain, TenantSettings


class TenantRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID) -> Tenant | None:
        return self.db.get(Tenant, tenant_id)

    def get_by_slug(self, slug: str) -> Tenant | None:
        return self.db.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none()

    def list_all(self, *, limit: int = 200, offset: int = 0) -> list[Tenant]:
        return list(
            self.db.execute(select(Tenant).order_by(Tenant.created_at.desc()).limit(limit).offset(offset))
            .scalars()
            .all()
        )

    def create(self, *, name: str, slug: str) -> Tenant:
        tenant = Tenant(name=name, slug=slug)
        self.db.add(tenant)
        self.db.flush()
        settings = TenantSettings(tenant_id=tenant.id)
        self.db.add(settings)
        self.db.flush()
        return tenant

    def get_settings(self, tenant_id: uuid.UUID) -> TenantSettings | None:
        return self.db.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
        ).scalar_one_or_none()


class TenantDomainRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, tenant_id: uuid.UUID, domain: str, is_primary: bool = False) -> TenantDomain:
        record = TenantDomain(tenant_id=tenant_id, domain=domain, is_primary=is_primary)
        self.db.add(record)
        self.db.flush()
        return record
