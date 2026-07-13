"""Tenant configuration catalogs: services, branches, tags, loss reasons,
and pipeline stages. All gated behind settings.manage at the route layer."""

from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.pipeline import LossReason, PipelineStage, Tag
from app.models.service import Service, ServiceCategory
from app.repositories.branch import BranchRepository
from app.repositories.pipeline import LossReasonRepository, PipelineStageRepository, TagRepository
from app.repositories.service import ServiceCategoryRepository, ServiceRepository
from app.services.errors import ConflictError, NotFoundError, ValidationError

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    return _SLUG_RE.sub("-", value.strip().lower()).strip("-")


class ServiceCatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.categories = ServiceCategoryRepository(db)
        self.services = ServiceRepository(db)

    def list_categories(self, tenant_id: uuid.UUID) -> list[ServiceCategory]:
        return self.categories.list_for_tenant(tenant_id)

    def create_category(
        self, tenant_id: uuid.UUID, *, name: str, sort_order: int = 0
    ) -> ServiceCategory:
        return self.categories.create(tenant_id=tenant_id, name=name, sort_order=sort_order)

    def list_services(self, tenant_id: uuid.UUID, *, active_only: bool = False) -> list[Service]:
        return self.services.list_for_tenant(tenant_id, active_only=active_only)

    def create_service(
        self,
        tenant_id: uuid.UUID,
        *,
        name: str,
        category_id: uuid.UUID | None = None,
        description: str | None = None,
        sort_order: int = 0,
    ) -> Service:
        if (
            category_id is not None
            and self.categories.get_by_id_for_tenant(tenant_id, category_id) is None
        ):
            raise ValidationError("Service category does not belong to this tenant.")
        slug = slugify(name)
        if self.services.get_by_slug_for_tenant(tenant_id, slug) is not None:
            raise ConflictError(f"A service named '{name}' already exists.")
        return self.services.create(
            tenant_id=tenant_id,
            name=name,
            slug=slug,
            category_id=category_id,
            description=description,
            sort_order=sort_order,
        )

    def update_service(
        self, tenant_id: uuid.UUID, service_id: uuid.UUID, **fields: object
    ) -> Service:
        service = self.services.get_by_id_for_tenant(tenant_id, service_id)
        if service is None:
            raise NotFoundError("Service not found.")
        for key, value in fields.items():
            if value is not None:
                setattr(service, key, value)
        self.db.flush()
        return service


class BranchService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.branches = BranchRepository(db)

    def list_branches(self, tenant_id: uuid.UUID, *, active_only: bool = False) -> list[Branch]:
        return self.branches.list_for_tenant(tenant_id, active_only=active_only)

    def create(self, tenant_id: uuid.UUID, *, name: str) -> Branch:
        return self.branches.create(tenant_id=tenant_id, name=name)


class TagService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.tags = TagRepository(db)

    def list_tags(self, tenant_id: uuid.UUID) -> list[Tag]:
        return self.tags.list_for_tenant(tenant_id)

    def create(self, tenant_id: uuid.UUID, *, name: str, color: str = "#6B7280") -> Tag:
        return self.tags.create(tenant_id=tenant_id, name=name, color=color)


class LossReasonService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.reasons = LossReasonRepository(db)

    def list_reasons(self, tenant_id: uuid.UUID) -> list[LossReason]:
        return self.reasons.list_for_tenant(tenant_id)

    def create(self, tenant_id: uuid.UUID, *, label: str, sort_order: int = 0) -> LossReason:
        return self.reasons.create(tenant_id=tenant_id, label=label, sort_order=sort_order)


class PipelineStageService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.stages = PipelineStageRepository(db)

    def list_stages(self, tenant_id: uuid.UUID) -> list[PipelineStage]:
        return self.stages.list_for_tenant(tenant_id)

    def create(
        self, tenant_id: uuid.UUID, *, name: str, is_won: bool = False, is_lost: bool = False
    ) -> PipelineStage:
        slug = slugify(name)
        if self.stages.get_by_slug_for_tenant(tenant_id, slug) is not None:
            raise ConflictError(f"A pipeline stage named '{name}' already exists.")
        existing = self.stages.list_for_tenant(tenant_id)
        next_order = max((s.sort_order for s in existing), default=-1) + 1
        return self.stages.create(
            tenant_id=tenant_id,
            name=name,
            slug=slug,
            sort_order=next_order,
            is_won=is_won,
            is_lost=is_lost,
        )

    def reorder(
        self, tenant_id: uuid.UUID, ordered_stage_ids: list[uuid.UUID]
    ) -> list[PipelineStage]:
        stages_by_id = {s.id: s for s in self.stages.list_for_tenant(tenant_id)}
        if set(ordered_stage_ids) != set(stages_by_id.keys()):
            raise ValidationError("Reorder list must include every pipeline stage exactly once.")
        for index, stage_id in enumerate(ordered_stage_ids):
            stages_by_id[stage_id].sort_order = index
        self.db.flush()
        return self.stages.list_for_tenant(tenant_id)
