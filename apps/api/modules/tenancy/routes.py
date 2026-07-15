from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import (
    TenantContext,
    get_tenant_db,
    require_csrf,
    require_permission,
    require_tenant_write,
)
from modules.audit import service as audit_service
from modules.tenancy import service as tenancy_service
from modules.tenancy.schemas import (
    OnboardingRequest,
    OnboardingResponse,
    TenantRead,
    TenantSettingsRead,
    TenantSettingsUpdate,
)

router = APIRouter(prefix="/api/tenancy", tags=["tenancy"])


@router.post("/onboarding", response_model=OnboardingResponse)
async def onboarding(payload: OnboardingRequest) -> OnboardingResponse:
    return await tenancy_service.onboard_tenant(payload)


@router.get("/current", response_model=TenantRead)
async def get_current_tenant(
    ctx: TenantContext = Depends(require_permission("assets.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> TenantRead:
    tenant = await tenancy_service.get_tenant_or_404(db, ctx.tenant_id)
    return TenantRead.model_validate(tenant)


@router.get("/settings", response_model=TenantSettingsRead)
async def get_settings(
    ctx: TenantContext = Depends(require_permission("settings.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> TenantSettingsRead:
    from modules.tenancy.repository import get_settings as get_settings_row

    settings_row = await get_settings_row(db, ctx.tenant_id)
    if settings_row is None:
        from core.errors import NotFoundError

        raise NotFoundError("Tenant settings not found.")
    return TenantSettingsRead.model_validate(settings_row)


@router.patch("/settings", response_model=TenantSettingsRead, dependencies=[Depends(require_csrf)])
async def update_settings(
    payload: TenantSettingsUpdate,
    ctx: TenantContext = Depends(require_permission("settings.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> TenantSettingsRead:
    require_tenant_write(ctx)
    settings_row = await tenancy_service.update_settings(db, ctx.tenant_id, payload)
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="tenancy.settings_updated",
        context=payload.model_dump(exclude_none=True),
    )
    await db.commit()
    return TenantSettingsRead.model_validate(settings_row)
