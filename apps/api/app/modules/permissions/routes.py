import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.dependencies.permissions import require_permission
from app.modules.permissions import service as permissions_service
from app.modules.permissions.schemas import (
    CreateRoleRequest,
    RoleSummary,
    UpdateRolePermissionsRequest,
)

router = APIRouter(prefix="/tenant/roles", tags=["roles"])


@router.get("", response_model=list[RoleSummary])
def list_roles(ctx: TenantContext = Depends(require_permission("roles.manage")), db: Session = Depends(get_db)) -> list[RoleSummary]:
    roles = permissions_service.list_tenant_roles(db, ctx.tenant_id)
    return [
        RoleSummary(id=r.id, name=r.name, is_system=r.is_system, permission_codes=sorted(permissions_service.get_role_permission_codes(db, r.id)))
        for r in roles
    ]


@router.get("/permission-catalog")
def get_permission_catalog(ctx: TenantContext = Depends(require_permission("roles.manage"))) -> dict:
    return permissions_service.list_assignable_tenant_permissions()


@router.post("", response_model=RoleSummary, status_code=201)
def create_role(
    payload: CreateRoleRequest, ctx: TenantContext = Depends(require_permission("roles.manage")), db: Session = Depends(get_db)
) -> RoleSummary:
    role = permissions_service.create_tenant_role(
        db, tenant_id=ctx.tenant_id, name=payload.name, permission_codes=payload.permission_codes
    )
    return RoleSummary(id=role.id, name=role.name, is_system=role.is_system, permission_codes=sorted(payload.permission_codes))


@router.patch("/{role_id}/permissions", response_model=RoleSummary)
def update_role_permissions(
    role_id: uuid.UUID, payload: UpdateRolePermissionsRequest,
    ctx: TenantContext = Depends(require_permission("roles.manage")), db: Session = Depends(get_db),
) -> RoleSummary:
    role = permissions_service.update_tenant_role_permissions(
        db, tenant_id=ctx.tenant_id, role_id=role_id, permission_codes=payload.permission_codes
    )
    return RoleSummary(id=role.id, name=role.name, is_system=role.is_system, permission_codes=sorted(payload.permission_codes))
