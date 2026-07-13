from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import MembershipContext, get_current_membership, require_permission
from app.db.session import get_db
from app.schemas.catalog import (
    BranchCreate,
    BranchOut,
    LossReasonCreate,
    LossReasonOut,
    PipelineStageCreate,
    PipelineStageOut,
    PipelineStageReorderRequest,
    ServiceCategoryCreate,
    ServiceCategoryOut,
    ServiceCreate,
    ServiceOut,
    ServiceUpdate,
    TagCreate,
    TagOut,
)
from app.services.catalog_service import (
    BranchService,
    LossReasonService,
    PipelineStageService,
    ServiceCatalogService,
    TagService,
)

router = APIRouter(prefix="/tenants/me", tags=["catalog"])


@router.get("/service-categories", response_model=list[ServiceCategoryOut])
def list_service_categories(
    db: Session = Depends(get_db), ctx: MembershipContext = Depends(get_current_membership)
) -> list[ServiceCategoryOut]:
    items = ServiceCatalogService(db).list_categories(ctx.tenant_id)
    return [ServiceCategoryOut.model_validate(i) for i in items]


@router.post("/service-categories", response_model=ServiceCategoryOut, status_code=201)
def create_service_category(
    payload: ServiceCategoryCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("settings.manage")),
) -> ServiceCategoryOut:
    item = ServiceCatalogService(db).create_category(
        ctx.tenant_id, name=payload.name, sort_order=payload.sort_order
    )
    db.commit()
    return ServiceCategoryOut.model_validate(item)


@router.get("/services", response_model=list[ServiceOut])
def list_services(
    active_only: bool = False,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(get_current_membership),
) -> list[ServiceOut]:
    items = ServiceCatalogService(db).list_services(ctx.tenant_id, active_only=active_only)
    return [ServiceOut.model_validate(i) for i in items]


@router.post("/services", response_model=ServiceOut, status_code=201)
def create_service(
    payload: ServiceCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("settings.manage")),
) -> ServiceOut:
    item = ServiceCatalogService(db).create_service(
        ctx.tenant_id,
        name=payload.name,
        category_id=payload.category_id,
        description=payload.description,
        sort_order=payload.sort_order,
    )
    db.commit()
    return ServiceOut.model_validate(item)


@router.patch("/services/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: uuid.UUID,
    payload: ServiceUpdate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("settings.manage")),
) -> ServiceOut:
    item = ServiceCatalogService(db).update_service(
        ctx.tenant_id, service_id, **payload.model_dump(exclude_unset=True)
    )
    db.commit()
    return ServiceOut.model_validate(item)


@router.get("/branches", response_model=list[BranchOut])
def list_branches(
    active_only: bool = False,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(get_current_membership),
) -> list[BranchOut]:
    items = BranchService(db).list_branches(ctx.tenant_id, active_only=active_only)
    return [BranchOut.model_validate(i) for i in items]


@router.post("/branches", response_model=BranchOut, status_code=201)
def create_branch(
    payload: BranchCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("settings.manage")),
) -> BranchOut:
    item = BranchService(db).create(ctx.tenant_id, name=payload.name)
    db.commit()
    return BranchOut.model_validate(item)


@router.get("/tags", response_model=list[TagOut])
def list_tags(
    db: Session = Depends(get_db), ctx: MembershipContext = Depends(get_current_membership)
) -> list[TagOut]:
    items = TagService(db).list_tags(ctx.tenant_id)
    return [TagOut.model_validate(i) for i in items]


@router.post("/tags", response_model=TagOut, status_code=201)
def create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("settings.manage")),
) -> TagOut:
    item = TagService(db).create(ctx.tenant_id, name=payload.name, color=payload.color)
    db.commit()
    return TagOut.model_validate(item)


@router.get("/loss-reasons", response_model=list[LossReasonOut])
def list_loss_reasons(
    db: Session = Depends(get_db), ctx: MembershipContext = Depends(get_current_membership)
) -> list[LossReasonOut]:
    items = LossReasonService(db).list_reasons(ctx.tenant_id)
    return [LossReasonOut.model_validate(i) for i in items]


@router.post("/loss-reasons", response_model=LossReasonOut, status_code=201)
def create_loss_reason(
    payload: LossReasonCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("settings.manage")),
) -> LossReasonOut:
    item = LossReasonService(db).create(
        ctx.tenant_id, label=payload.label, sort_order=payload.sort_order
    )
    db.commit()
    return LossReasonOut.model_validate(item)


@router.get("/pipeline-stages", response_model=list[PipelineStageOut])
def list_pipeline_stages(
    db: Session = Depends(get_db), ctx: MembershipContext = Depends(get_current_membership)
) -> list[PipelineStageOut]:
    items = PipelineStageService(db).list_stages(ctx.tenant_id)
    return [PipelineStageOut.model_validate(i) for i in items]


@router.post("/pipeline-stages", response_model=PipelineStageOut, status_code=201)
def create_pipeline_stage(
    payload: PipelineStageCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("settings.manage")),
) -> PipelineStageOut:
    item = PipelineStageService(db).create(
        ctx.tenant_id, name=payload.name, is_won=payload.is_won, is_lost=payload.is_lost
    )
    db.commit()
    return PipelineStageOut.model_validate(item)


@router.post("/pipeline-stages/reorder", response_model=list[PipelineStageOut])
def reorder_pipeline_stages(
    payload: PipelineStageReorderRequest,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("settings.manage")),
) -> list[PipelineStageOut]:
    items = PipelineStageService(db).reorder(ctx.tenant_id, payload.stage_ids)
    db.commit()
    return [PipelineStageOut.model_validate(i) for i in items]
