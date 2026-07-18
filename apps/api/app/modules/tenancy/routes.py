from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.exceptions import ResourceNotFoundError
from app.dependencies import (
    TenantContext,
    get_current_session,
    get_current_user,
    get_tenant_context,
    require_permission,
    verify_csrf,
)
from app.modules.identity.models import Session as SessionModel
from app.modules.identity.models import User
from app.modules.permissions import repositories as perm_repo
from app.modules.tenancy import repositories as repo
from app.modules.tenancy import services
from app.modules.tenancy.schemas import (
    AcceptInvitationRequest,
    CreateTenantRequest,
    InvitationResponse,
    InviteMemberRequest,
    MemberResponse,
    RoleResponse,
    SwitchTenantRequest,
    TenantResponse,
)

router = APIRouter(tags=["tenancy"])


@router.post("/tenants", response_model=TenantResponse, dependencies=[Depends(verify_csrf)])
async def create_tenant(
    payload: CreateTenantRequest,
    user: User = Depends(get_current_user),
    session_row: SessionModel = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    tenant = await services.create_tenant_for_user(db, user=user, tenant_name=payload.name)
    # A freshly created tenant becomes this session's active tenant so the
    # caller can immediately continue into the tenant workspace.
    session_row.active_tenant_id = tenant.id
    return TenantResponse(id=tenant.id, name=tenant.name, slug=tenant.slug, status=tenant.status)


@router.post("/tenants/switch", response_model=TenantResponse, dependencies=[Depends(verify_csrf)])
async def switch_tenant(
    payload: SwitchTenantRequest,
    user: User = Depends(get_current_user),
    session_row: SessionModel = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    tenant = await services.switch_active_tenant(
        db, user=user, session_row=session_row, requested_tenant_id=payload.tenant_id
    )
    return TenantResponse(id=tenant.id, name=tenant.name, slug=tenant.slug, status=tenant.status)


@router.get("/tenants/current", response_model=TenantResponse)
async def get_current_tenant(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    tenant = await repo.get_tenant_by_id(db, ctx.tenant_id)
    if tenant is None:
        raise ResourceNotFoundError("Tenant not found.")
    return TenantResponse(id=tenant.id, name=tenant.name, slug=tenant.slug, status=tenant.status)


@router.get("/tenants/roles", response_model=list[RoleResponse])
async def list_roles(
    ctx: TenantContext = Depends(require_permission("roles.view")),
    db: AsyncSession = Depends(get_db),
):
    roles = await perm_repo.list_roles_for_tenant(db, ctx.tenant_id)
    return [RoleResponse(id=r.id, name=r.name, description=r.description) for r in roles]


@router.get("/tenants/members", response_model=list[MemberResponse])
async def list_members(
    ctx: TenantContext = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    rows = await repo.list_active_members_for_tenant(db, ctx.tenant_id)
    return [
        MemberResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role_id=role.id,
            role_name=role.name,
        )
        for _membership, user, role in rows
    ]


@router.post("/tenants/invitations", response_model=InvitationResponse)
async def invite_member(
    payload: InviteMemberRequest,
    ctx: TenantContext = Depends(require_permission("users.manage")),
    db: AsyncSession = Depends(get_db),
):
    invitation = await services.create_invitation(
        db,
        tenant_id=ctx.tenant_id,
        invited_by_user_id=ctx.user_id,
        email=payload.email,
        role_id=payload.role_id,
    )
    return InvitationResponse(
        id=invitation.id,
        email=invitation.email,
        role_id=invitation.role_id,
        status=invitation.status,
        expires_at=invitation.expires_at,
    )


@router.get("/tenants/invitations", response_model=list[InvitationResponse])
async def list_invitations(
    ctx: TenantContext = Depends(require_permission("users.manage")),
    db: AsyncSession = Depends(get_db),
):
    invitations = await repo.list_invitations_for_tenant(db, ctx.tenant_id)
    return [
        InvitationResponse(
            id=i.id, email=i.email, role_id=i.role_id, status=i.status, expires_at=i.expires_at
        )
        for i in invitations
    ]


@router.post("/invitations/accept", dependencies=[Depends(verify_csrf)])
async def accept_invitation(
    payload: AcceptInvitationRequest,
    user: User = Depends(get_current_user),
    session_row: SessionModel = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    membership = await services.accept_invitation(db, raw_token=payload.token, user=user)
    # Joining a workspace via invitation makes it this session's active
    # tenant, so the caller lands directly in the workspace they just
    # joined rather than wherever they happened to be active before.
    session_row.active_tenant_id = membership.tenant_id
    return {
        "tenant_id": str(membership.tenant_id),
        "role_id": str(membership.role_id),
        "status": membership.status,
    }
