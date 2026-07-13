from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import MembershipContext, require_permission
from app.db.session import get_db
from app.repositories.user import UserRepository
from app.schemas.common import ORMModel
from app.schemas.rbac import RoleOut
from app.services.membership_service import MembershipService

router = APIRouter(prefix="/tenants/me/members", tags=["members"])


class MemberOut(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: RoleOut
    status: str


class UpdateMemberRoleRequest(BaseModel):
    role_id: uuid.UUID


@router.get("", response_model=list[MemberOut])
def list_members(
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("users.manage")),
) -> list[MemberOut]:
    service = MembershipService(db)
    users = UserRepository(db)
    out: list[MemberOut] = []
    for membership in service.list_for_tenant(ctx.tenant_id):
        user = users.get_by_id(membership.user_id)
        if user is None:
            continue
        out.append(
            MemberOut(
                id=membership.id,
                user_id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                role=RoleOut.model_validate(membership.role),
                status=membership.status,
            )
        )
    return out


@router.patch("/{membership_id}/role", response_model=MemberOut)
def update_member_role(
    membership_id: uuid.UUID,
    payload: UpdateMemberRoleRequest,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("users.manage")),
) -> MemberOut:
    service = MembershipService(db)
    membership = service.update_role(ctx.tenant_id, membership_id, payload.role_id)
    db.commit()
    user = UserRepository(db).get_by_id(membership.user_id)
    assert user is not None
    return MemberOut(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=RoleOut.model_validate(membership.role),
        status=membership.status,
    )


@router.post("/{membership_id}/suspend", response_model=MemberOut)
def suspend_member(
    membership_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("users.manage")),
) -> MemberOut:
    service = MembershipService(db)
    membership = service.suspend(ctx.tenant_id, membership_id)
    db.commit()
    user = UserRepository(db).get_by_id(membership.user_id)
    assert user is not None
    return MemberOut(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=RoleOut.model_validate(membership.role),
        status=membership.status,
    )


@router.post("/{membership_id}/reactivate", response_model=MemberOut)
def reactivate_member(
    membership_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("users.manage")),
) -> MemberOut:
    service = MembershipService(db)
    membership = service.reactivate(ctx.tenant_id, membership_id)
    db.commit()
    user = UserRepository(db).get_by_id(membership.user_id)
    assert user is not None
    return MemberOut(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=RoleOut.model_validate(membership.role),
        status=membership.status,
    )
