from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.deps import AuthContext, get_auth_context, require_csrf
from core.middleware import login_rate_limiter
from core.security import generate_csrf_token
from db.session import get_db
from modules.audit import service as audit_service
from modules.identity import service as identity_service
from modules.identity.models import User
from modules.identity.schemas import (
    AcceptInvitationRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    ResetPasswordRequest,
    TenantSwitchRequest,
    UserRead,
    VerifyEmailRequest,
)
from modules.permissions.service import accept_invitation as accept_invitation_service

logger = structlog.get_logger("gridkeep.identity.routes")

router = APIRouter(prefix="/api/auth", tags=["auth"])

_SESSION_COOKIE_KW = dict(httponly=True, samesite="lax", secure=False, path="/")
_CSRF_COOKIE_KW = dict(httponly=False, samesite="lax", secure=False, path="/")


def _cookie_secure_kwargs(base: dict) -> dict:
    kw = dict(base)
    kw["secure"] = settings.is_production
    return kw


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    login_rate_limiter.check(
        f"login-ip:{request.client.host if request.client else 'unknown'}",
        limit=settings.rate_limit_login_per_minute,
        window_seconds=60,
    )
    login_rate_limiter.check(
        f"login-account:{payload.email.lower()}",
        limit=settings.rate_limit_login_per_hour_per_account,
        window_seconds=3600,
    )

    user = await identity_service.authenticate_user(db, payload.email, payload.password)
    memberships = await identity_service.list_memberships_for_user(db, user.id)
    active_membership_id = memberships[0].membership_id if len(memberships) == 1 else None

    raw_token, session_row = await identity_service.create_session(
        db,
        user,
        active_membership_id=active_membership_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    csrf_token = generate_csrf_token()

    await audit_service.record(
        db,
        tenant_id=None,
        actor_user_id=user.id,
        actor_label=user.email,
        action="auth.login",
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    response.set_cookie(
        settings.session_cookie_name, raw_token, max_age=settings.session_ttl_seconds,
        **_cookie_secure_kwargs(_SESSION_COOKIE_KW),
    )
    response.set_cookie(
        settings.csrf_cookie_name, csrf_token, max_age=settings.session_ttl_seconds,
        **_cookie_secure_kwargs(_CSRF_COOKIE_KW),
    )

    return LoginResponse(
        user=UserRead.model_validate(user),
        memberships=memberships,
        active_membership_id=active_membership_id,
        csrf_token=csrf_token,
    )


@router.post("/logout", dependencies=[Depends(require_csrf)])
async def logout(
    request: Request,
    response: Response,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token:
        await identity_service.revoke_session_by_token(db, raw_token)
    await audit_service.record(
        db,
        tenant_id=None,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="auth.logout",
    )
    await db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    return {"status": "ok"}


@router.get("/me", response_model=MeResponse)
async def me(
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    memberships = await identity_service.list_memberships_for_user(db, ctx.user.id)
    from sqlalchemy import select

    from modules.identity.models import Session as SessionModel

    session_row = (
        await db.execute(select(SessionModel).where(SessionModel.id == ctx.session_id))
    ).scalar_one()
    return MeResponse(
        user=UserRead.model_validate(ctx.user),
        memberships=memberships,
        active_membership_id=session_row.active_membership_id,
    )


@router.post("/tenant-switch", dependencies=[Depends(require_csrf)])
async def tenant_switch(
    payload: TenantSwitchRequest,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from sqlalchemy import select

    from modules.identity.models import Session as SessionModel

    session_row = (
        await db.execute(select(SessionModel).where(SessionModel.id == ctx.session_id))
    ).scalar_one()
    membership = await identity_service.switch_active_tenant(
        db, user_id=ctx.user.id, session_row=session_row, membership_id=payload.membership_id
    )
    await audit_service.record(
        db,
        tenant_id=membership.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="auth.tenant_switch",
        target_type="membership",
        target_id=str(membership.id),
    )
    await db.commit()
    return {"status": "ok", "active_membership_id": str(membership.id)}


@router.post("/verify-email")
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)) -> dict:
    user = await identity_service.verify_email(db, payload.token)
    await audit_service.record(
        db, tenant_id=None, actor_user_id=user.id, actor_label=user.email, action="auth.email_verified"
    )
    await db.commit()
    return {"status": "ok"}


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> dict:
    """Always returns 200 regardless of whether the email is registered —
    prevents account enumeration."""
    login_rate_limiter.check(
        f"forgot-password:{payload.email.lower()}", limit=5, window_seconds=3600
    )
    from sqlalchemy import select

    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if user is not None and user.is_active:
        token = await identity_service.issue_password_reset_token(db, user)
        await db.commit()
        logger.info("email_dispatch_simulated", template="password_reset", to=user.email, token=token)
    return {"status": "ok"}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)) -> dict:
    user = await identity_service.reset_password(db, payload.token, payload.new_password)
    await audit_service.record(
        db, tenant_id=None, actor_user_id=user.id, actor_label=user.email, action="auth.password_reset"
    )
    await db.commit()
    return {"status": "ok"}


@router.post("/accept-invitation", response_model=LoginResponse)
async def accept_invitation(
    payload: AcceptInvitationRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    user, membership = await accept_invitation_service(
        db,
        raw_token=payload.token,
        full_name=payload.full_name,
        password=payload.password,
    )
    await audit_service.record(
        db,
        tenant_id=membership.tenant_id,
        actor_user_id=user.id,
        actor_label=user.email,
        action="auth.invitation_accepted",
        target_type="membership",
        target_id=str(membership.id),
    )
    await db.commit()

    memberships = await identity_service.list_memberships_for_user(db, user.id)
    raw_token, _session_row = await identity_service.create_session(
        db,
        user,
        active_membership_id=membership.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    csrf_token = generate_csrf_token()
    await db.commit()

    response.set_cookie(
        settings.session_cookie_name, raw_token, max_age=settings.session_ttl_seconds,
        **_cookie_secure_kwargs(_SESSION_COOKIE_KW),
    )
    response.set_cookie(
        settings.csrf_cookie_name, csrf_token, max_age=settings.session_ttl_seconds,
        **_cookie_secure_kwargs(_CSRF_COOKIE_KW),
    )
    return LoginResponse(
        user=UserRead.model_validate(user),
        memberships=memberships,
        active_membership_id=membership.id,
        csrf_token=csrf_token,
    )
