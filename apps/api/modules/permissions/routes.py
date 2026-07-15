from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import (
    TenantContext,
    get_tenant_context,
    get_tenant_db,
    require_csrf,
    require_permission,
    require_tenant_write,
)
from core.errors import NotFoundError
from modules.audit import service as audit_service
from modules.identity.models import User
from modules.permissions import service as permissions_service
from modules.permissions.models import Membership, Role
from modules.permissions.schemas import (
    InvitationCreateRequest,
    MembershipRead,
    RoleRead,
)

logger = structlog.get_logger("gridkeep.permissions.routes")

router = APIRouter(prefix="/api", tags=["permissions"])


@router.get("/roles", response_model=list[RoleRead])
async def list_roles(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[RoleRead]:
    roles = await permissions_service.list_tenant_roles(db)
    return [RoleRead.model_validate(r) for r in roles]


@router.get("/users", response_model=list[MembershipRead])
async def list_members(
    ctx: TenantContext = Depends(require_permission("users.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[MembershipRead]:
    result = await db.execute(
        select(Membership, User, Role)
        .join(User, User.id == Membership.user_id)
        .join(Role, Role.id == Membership.role_id)
        .where(Membership.tenant_id == ctx.tenant_id)
    )
    return [
        MembershipRead(
            id=membership.id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role_name=role.name,
            status=membership.status,
        )
        for membership, user, role in result.all()
    ]


@router.post(
    "/users/invitations",
    dependencies=[Depends(require_csrf)],
)
async def invite_member(
    payload: InvitationCreateRequest,
    ctx: TenantContext = Depends(require_permission("users.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    require_tenant_write(ctx)
    invitation, raw_token = await permissions_service.create_invitation(
        db,
        tenant_id=ctx.tenant_id,
        invited_by_user_id=ctx.user.id,
        email=payload.email,
        role_name=payload.role_name,
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="users.invited",
        target_type="invitation",
        target_id=str(invitation.id),
        context={"invited_email": payload.email, "role": payload.role_name},
    )
    await db.commit()
    # Invitation tokens are bearer credentials — never returned in an API
    # response body. Dispatched via the (dev-only) simulated email adapter.
    logger.info(
        "email_dispatch_simulated",
        template="invitation",
        to=payload.email,
        invitation_token=raw_token,
    )
    return {"status": "ok", "invitation_id": str(invitation.id)}


@router.delete("/users/{membership_id}", dependencies=[Depends(require_csrf)])
async def remove_member(
    membership_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("users.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    require_tenant_write(ctx)
    membership = (
        await db.execute(
            select(Membership).where(
                Membership.id == membership_id, Membership.tenant_id == ctx.tenant_id
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise NotFoundError("Member not found.")

    membership.status = "removed"
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="users.removed",
        target_type="membership",
        target_id=str(membership.id),
    )
    await db.commit()
    return {"status": "ok"}
