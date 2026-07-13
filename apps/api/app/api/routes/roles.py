from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import MembershipContext, get_current_membership, require_permission
from app.db.session import get_db
from app.repositories.role import RoleRepository
from app.schemas.rbac import RoleCreate, RoleOut, RoleUpdate
from app.services.errors import ValidationError

router = APIRouter(prefix="/tenants/me/roles", tags=["roles"])


def _slugify(name: str) -> str:
    return "-".join(name.strip().lower().split())


@router.get("", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(get_db), ctx: MembershipContext = Depends(get_current_membership)
) -> list[RoleOut]:
    roles = RoleRepository(db).list_for_tenant(ctx.tenant_id)
    return [RoleOut.model_validate(r) for r in roles]


@router.post("", response_model=RoleOut, status_code=201)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("roles.manage")),
) -> RoleOut:
    repo = RoleRepository(db)
    slug = _slugify(payload.name)
    if repo.get_by_slug_for_tenant(ctx.tenant_id, slug) is not None:
        raise ValidationError("A role with a similar name already exists.")
    role = repo.create(
        tenant_id=ctx.tenant_id,
        name=payload.name,
        slug=slug,
        permission_codes=payload.permission_codes,
    )
    db.commit()
    return RoleOut.model_validate(role)


@router.patch("/{role_id}", response_model=RoleOut)
def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("roles.manage")),
) -> RoleOut:
    repo = RoleRepository(db)
    role = repo.get_by_id_for_tenant(ctx.tenant_id, role_id)
    if role is None:
        from app.services.errors import NotFoundError

        raise NotFoundError("Role not found.")
    if role.is_system:
        raise ValidationError(
            "Default system roles cannot be modified. Create a custom role instead."
        )
    if payload.name is not None:
        role.name = payload.name
    if payload.permission_codes is not None:
        repo.update_permissions(role, payload.permission_codes)
    db.commit()
    return RoleOut.model_validate(role)
