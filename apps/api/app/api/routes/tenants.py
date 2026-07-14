from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import MembershipContext, get_current_membership, require_permission
from app.db.session import get_db
from app.schemas.tenant import (
    TenantOut,
    TenantProfileUpdate,
    TenantSettingsOut,
    TenantSettingsUpdate,
)
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/tenants/me", tags=["tenants"])


@router.get("", response_model=TenantOut)
def get_current_tenant(ctx: MembershipContext = Depends(get_current_membership)) -> TenantOut:
    return TenantOut.model_validate(ctx.tenant)


@router.patch("", response_model=TenantOut)
def update_current_tenant(
    payload: TenantProfileUpdate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("settings.manage")),
) -> TenantOut:
    tenant = TenantService(db).update_profile(ctx.tenant, **payload.model_dump(exclude_unset=True))
    db.commit()
    return TenantOut.model_validate(tenant)


@router.get("/settings", response_model=TenantSettingsOut)
def get_settings_route(
    db: Session = Depends(get_db), ctx: MembershipContext = Depends(get_current_membership)
) -> TenantSettingsOut:
    settings = TenantService(db).get_settings_or_404(ctx.tenant_id)
    return TenantSettingsOut.model_validate(settings)


@router.patch("/settings", response_model=TenantSettingsOut)
def update_settings_route(
    payload: TenantSettingsUpdate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("settings.manage")),
) -> TenantSettingsOut:
    service = TenantService(db)
    settings = service.get_settings_or_404(ctx.tenant_id)
    settings = service.update_settings(settings, **payload.model_dump(exclude_unset=True))
    db.commit()
    return TenantSettingsOut.model_validate(settings)


@router.post("/onboarding/complete", response_model=TenantSettingsOut)
def complete_onboarding_route(
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("settings.manage")),
) -> TenantSettingsOut:
    service = TenantService(db)
    settings = service.get_settings_or_404(ctx.tenant_id)
    settings = service.complete_onboarding(settings)
    db.commit()
    return TenantSettingsOut.model_validate(settings)
