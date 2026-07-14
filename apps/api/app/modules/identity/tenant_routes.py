import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.dependencies.entitlements import check_usage_limit
from app.dependencies.permissions import require_permission
from app.modules.identity import service as identity_service
from app.modules.identity.repository import MembershipRepository, UserRepository
from app.modules.permissions import service as permissions_service
from app.modules.tenancy import service as tenancy_service

router = APIRouter(prefix="/tenant/users", tags=["tenant-users"])


class InviteUserRequest(BaseModel):
    email: EmailStr
    role_id: uuid.UUID


class MemberSummary(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role_name: str
    status: str


@router.get("", response_model=list[MemberSummary])
def list_members(ctx: TenantContext = Depends(require_permission("users.manage")), db: Session = Depends(get_db)) -> list[MemberSummary]:
    memberships = MembershipRepository(db).list_for_tenant(ctx.tenant_id)
    results = []
    for membership in memberships:
        user = UserRepository(db).get_by_id(membership.user_id)
        role = permissions_service.get_role(db, membership.role_id)
        if user is None or role is None:
            continue
        results.append(
            MemberSummary(
                membership_id=membership.id, user_id=user.id, email=user.email,
                first_name=user.first_name, last_name=user.last_name,
                role_name=role.name, status=membership.status.value,
            )
        )
    return results


@router.post("/invitations", status_code=202)
def invite_user(
    payload: InviteUserRequest,
    ctx: TenantContext = Depends(require_permission("users.manage")),
    _usage: TenantContext = Depends(check_usage_limit("users", feature_code="users")),
    db: Session = Depends(get_db),
) -> dict:
    tenant = tenancy_service.get_tenant_or_404(db, ctx.tenant_id)
    identity_service.invite_user(
        db, tenant_id=ctx.tenant_id, email=payload.email, role_id=payload.role_id,
        invited_by=ctx.user_id, tenant_name=tenant.name,
    )
    return {"status": "invited"}
