import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.service import Service, ServiceCategory


class ServiceCategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[ServiceCategory]:
        stmt = (
            select(ServiceCategory)
            .where(ServiceCategory.tenant_id == tenant_id)
            .order_by(ServiceCategory.sort_order)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id_for_tenant(
        self, tenant_id: uuid.UUID, category_id: uuid.UUID
    ) -> ServiceCategory | None:
        stmt = select(ServiceCategory).where(
            ServiceCategory.tenant_id == tenant_id, ServiceCategory.id == category_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, *, tenant_id: uuid.UUID, name: str, sort_order: int = 0) -> ServiceCategory:
        category = ServiceCategory(tenant_id=tenant_id, name=name, sort_order=sort_order)
        self.db.add(category)
        self.db.flush()
        return category


class ServiceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_tenant(self, tenant_id: uuid.UUID, *, active_only: bool = False) -> list[Service]:
        stmt = select(Service).where(Service.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(Service.is_active.is_(True))
        stmt = stmt.order_by(Service.sort_order, Service.name)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id_for_tenant(self, tenant_id: uuid.UUID, service_id: uuid.UUID) -> Service | None:
        stmt = select(Service).where(Service.tenant_id == tenant_id, Service.id == service_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_slug_for_tenant(self, tenant_id: uuid.UUID, slug: str) -> Service | None:
        stmt = select(Service).where(Service.tenant_id == tenant_id, Service.slug == slug)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        slug: str,
        category_id: uuid.UUID | None = None,
        description: str | None = None,
        sort_order: int = 0,
    ) -> Service:
        service = Service(
            tenant_id=tenant_id,
            name=name,
            slug=slug,
            category_id=category_id,
            description=description,
            sort_order=sort_order,
        )
        self.db.add(service)
        self.db.flush()
        return service
