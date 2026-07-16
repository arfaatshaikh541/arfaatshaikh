from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import TenantContext, get_tenant_db, require_csrf, require_permission, require_tenant_write
from db.session import get_db
from modules.trust_passport import service as trust_passport_service
from modules.trust_passport.models import TrustPassportSettings
from modules.trust_passport.schemas import (
    PublicTrustPassportRead,
    TrustPassportSettingsRead,
    UpdateTrustPassportSettingsRequest,
)

router = APIRouter(prefix="/api/trust-passport", tags=["trust-passport"])
public_router = APIRouter(prefix="/api/public/trust-passport", tags=["trust-passport-public"])


def _to_settings_read(settings: TrustPassportSettings) -> TrustPassportSettingsRead:
    return TrustPassportSettingsRead(
        is_published=settings.is_published,
        public_slug=settings.public_slug,
        headline=settings.headline,
        description=settings.description,
        show_compliance_frameworks=settings.show_compliance_frameworks,
        updated_at=settings.updated_at,
    )


@router.get("/settings", response_model=TrustPassportSettingsRead)
async def get_settings(
    ctx: TenantContext = Depends(require_permission("trust_passport.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> TrustPassportSettingsRead:
    settings = await trust_passport_service.get_settings(db, tenant_id=ctx.tenant_id)
    if settings is None:
        return TrustPassportSettingsRead(
            is_published=False, public_slug=None, headline="", description="",
            show_compliance_frameworks=True, updated_at=None,
        )
    return _to_settings_read(settings)


@router.patch("/settings", response_model=TrustPassportSettingsRead, dependencies=[Depends(require_csrf)])
async def update_settings(
    payload: UpdateTrustPassportSettingsRequest,
    ctx: TenantContext = Depends(require_permission("trust_passport.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> TrustPassportSettingsRead:
    require_tenant_write(ctx)
    settings = await trust_passport_service.update_settings(
        db,
        tenant_id=ctx.tenant_id,
        is_published=payload.is_published,
        headline=payload.headline,
        description=payload.description,
        show_compliance_frameworks=payload.show_compliance_frameworks,
        actor_user_id=ctx.user.id,
    )
    response = _to_settings_read(settings)
    await db.commit()
    return response


@router.post(
    "/settings/regenerate-slug", response_model=TrustPassportSettingsRead,
    dependencies=[Depends(require_csrf)],
)
async def regenerate_slug(
    ctx: TenantContext = Depends(require_permission("trust_passport.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> TrustPassportSettingsRead:
    require_tenant_write(ctx)
    settings = await trust_passport_service.regenerate_slug(
        db, tenant_id=ctx.tenant_id, actor_user_id=ctx.user.id
    )
    response = _to_settings_read(settings)
    await db.commit()
    return response


@public_router.get("/{slug}", response_model=PublicTrustPassportRead)
async def get_public_passport(slug: str, db: AsyncSession = Depends(get_db)) -> PublicTrustPassportRead:
    passport = await trust_passport_service.get_public_passport(db, slug=slug)
    return PublicTrustPassportRead(**passport)
