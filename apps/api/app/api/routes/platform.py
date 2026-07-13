from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_platform_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.platform_reporting import PlatformOverviewOut
from app.schemas.subscription import (
    SubscriptionAssignRequest,
    SubscriptionOut,
    SubscriptionPlanCreate,
    SubscriptionPlanOut,
    SubscriptionPlanUpdate,
)
from app.schemas.tenant import TenantCreate, TenantOut
from app.services.platform_reporting_service import PlatformReportingService
from app.services.platform_service import PlatformService
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/platform", tags=["platform"])


class SetTenantStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|suspended|archived)$")
    reason: str = Field(min_length=3, max_length=500)


@router.get("/tenants", response_model=list[TenantOut])
def list_tenants(
    db: Session = Depends(get_db), _admin: User = Depends(get_platform_admin)
) -> list[TenantOut]:
    tenants = PlatformService(db).list_tenants()
    return [TenantOut.model_validate(t) for t in tenants]


@router.post("/tenants", response_model=TenantOut, status_code=201)
def create_tenant(
    payload: TenantCreate, db: Session = Depends(get_db), _admin: User = Depends(get_platform_admin)
) -> TenantOut:
    tenant = TenantService(db).create_tenant_with_owner(
        name=payload.name,
        slug=payload.slug,
        legal_name=payload.legal_name,
        timezone=payload.timezone,
        currency=payload.currency,
        owner_email=payload.owner_email,
        owner_first_name=payload.owner_first_name,
        owner_last_name=payload.owner_last_name,
        owner_password=payload.owner_password,
    )
    db.commit()
    return TenantOut.model_validate(tenant)


@router.get("/tenants/{tenant_id}", response_model=TenantOut)
def get_tenant_detail(
    tenant_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(get_platform_admin)
) -> TenantOut:
    tenant = PlatformService(db).get_tenant_detail(actor=admin, tenant_id=tenant_id)
    db.commit()
    return TenantOut.model_validate(tenant)


@router.post("/tenants/{tenant_id}/status", response_model=TenantOut)
def set_tenant_status(
    tenant_id: uuid.UUID,
    payload: SetTenantStatusRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_platform_admin),
) -> TenantOut:
    tenant = PlatformService(db).set_tenant_status(
        actor=admin, tenant_id=tenant_id, status=payload.status, reason=payload.reason
    )
    db.commit()
    return TenantOut.model_validate(tenant)


@router.get("/plans", response_model=list[SubscriptionPlanOut])
def list_plans(
    db: Session = Depends(get_db), _admin: User = Depends(get_platform_admin)
) -> list[SubscriptionPlanOut]:
    plans = PlatformService(db).list_plans()
    return [SubscriptionPlanOut.model_validate(p) for p in plans]


@router.post("/plans", response_model=SubscriptionPlanOut, status_code=201)
def create_plan(
    payload: SubscriptionPlanCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_platform_admin),
) -> SubscriptionPlanOut:
    plan = PlatformService(db).create_plan(
        code=payload.code,
        name=payload.name,
        price_cents=payload.price_cents,
        currency=payload.currency,
        features=payload.features,
    )
    db.commit()
    return SubscriptionPlanOut.model_validate(plan)


@router.patch("/plans/{plan_id}", response_model=SubscriptionPlanOut)
def update_plan(
    plan_id: uuid.UUID,
    payload: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_platform_admin),
) -> SubscriptionPlanOut:
    plan = PlatformService(db).update_plan(plan_id, **payload.model_dump(exclude_unset=True))
    db.commit()
    return SubscriptionPlanOut.model_validate(plan)


@router.get("/tenants/{tenant_id}/subscription", response_model=SubscriptionOut | None)
def get_tenant_subscription(
    tenant_id: uuid.UUID, db: Session = Depends(get_db), _admin: User = Depends(get_platform_admin)
) -> SubscriptionOut | None:
    subscription = PlatformService(db).get_tenant_subscription(tenant_id)
    return SubscriptionOut.model_validate(subscription) if subscription else None


@router.post("/tenants/{tenant_id}/subscription", response_model=SubscriptionOut)
def assign_tenant_subscription(
    tenant_id: uuid.UUID,
    payload: SubscriptionAssignRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_platform_admin),
) -> SubscriptionOut:
    subscription = PlatformService(db).assign_subscription(
        actor=admin, tenant_id=tenant_id, plan_id=payload.plan_id, status=payload.status
    )
    db.commit()
    return SubscriptionOut.model_validate(subscription)


@router.get("/overview", response_model=PlatformOverviewOut)
def get_platform_overview(
    db: Session = Depends(get_db), _admin: User = Depends(get_platform_admin)
) -> PlatformOverviewOut:
    overview = PlatformReportingService(db).get_overview()
    return PlatformOverviewOut.model_validate(overview)
