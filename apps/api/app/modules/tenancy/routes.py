from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.dependencies.permissions import require_permission
from app.dependencies.tenant import get_tenant_context
from app.modules.tenancy import service as tenancy_service
from app.modules.tenancy.schemas import TenantSettingsResponse, UpdateTenantSettingsRequest

router = APIRouter(prefix="/tenant/settings", tags=["tenant-settings"])


@router.get("", response_model=TenantSettingsResponse)
def get_settings(ctx: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> TenantSettingsResponse:
    settings = tenancy_service.get_tenant_settings(db, ctx.tenant_id)
    return TenantSettingsResponse.model_validate(settings)


@router.patch("", response_model=TenantSettingsResponse)
def update_settings(
    payload: UpdateTenantSettingsRequest,
    ctx: TenantContext = Depends(require_permission("settings.manage")),
    db: Session = Depends(get_db),
) -> TenantSettingsResponse:
    settings = tenancy_service.update_tenant_settings(
        db, tenant_id=ctx.tenant_id, updates=payload.model_dump(exclude_unset=True)
    )
    return TenantSettingsResponse.model_validate(settings)
