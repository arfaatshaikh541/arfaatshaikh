from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.deps import AuthContext, get_auth_context, require_csrf
from core.email import send_email
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
    MembershipSummary,
    MeResponse,
    MfaBackupCodesResponse,
    MfaConfirmRequest,
    MfaConfirmResponse,
    MfaDisableRequest,
    MfaEnrollResponse,
    MfaRegenerateBackupCodesRequest,
    MfaRequiredResponse,
    MfaVerifyLoginRequest,
    ResetPasswordRequest,
    StepUpRequest,
    StepUpResponse,
    TenantSwitchRequest,
    UserRead,
    VerifyEmailRequest,
)
from modules.permissions.service import accept_invitation as accept_invitation_service
from modules.tenancy.service import is_mfa_enrollment_required

logger = structlog.get_logger("gridkeep.identity.routes")

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _build_user_read(db: AsyncSession, user: User) -> UserRead:
    platform_role_name = await identity_service.get_platform_role_name(db, user)
    return UserRead.model_validate(user).model_copy(update={"platform_role_name": platform_role_name})


async def _compute_mfa_enrollment_required(
    db: AsyncSession,
    user: User,
    memberships: list[MembershipSummary],
    active_membership_id: uuid.UUID | None,
) -> bool:
    """Informational-only mirror of the real gate in
    `core.deps.get_tenant_context` — lets the frontend redirect to MFA
    enrollment proactively (Milestone 14) instead of only discovering the
    block from a failed tenant API call. Nothing tenant-scoped is ever
    actually served based on this flag; `get_tenant_context` is what
    enforces it."""
    if active_membership_id is None:
        return False
    active = next((m for m in memberships if m.membership_id == active_membership_id), None)
    if active is None:
        return False
    return await is_mfa_enrollment_required(
        db, tenant_id=active.tenant_id, role_name=active.role_name, user=user
    )

_SESSION_COOKIE_KW = dict(httponly=True, samesite="lax", secure=False, path="/")
_CSRF_COOKIE_KW = dict(httponly=False, samesite="lax", secure=False, path="/")


def _cookie_secure_kwargs(base: dict) -> dict:
    kw = dict(base)
    kw["secure"] = settings.is_production
    return kw


async def _complete_login(
    db: AsyncSession, user: User, request: Request, response: Response, *, mfa_method: str | None = None
) -> LoginResponse:
    """The part of signing in that only ever happens once a session should
    actually be created — shared between a normal (no-MFA) login and
    `/mfa/verify-login` completing a challenge, so there is exactly one
    place that creates a session, sets cookies, and records `auth.login`.
    `mfa_method` (Milestone 24: `"totp"` or `"backup_code"`) is tagged onto
    the audit record's `context` so a backup-code login — a signal worth a
    closer look, since it means the account's normal second factor wasn't
    used — is distinguishable from a routine one."""
    memberships = await identity_service.list_memberships_for_user(db, user.id)
    active_membership_id = memberships[0].membership_id if len(memberships) == 1 else None

    raw_token, _session_row = await identity_service.create_session(
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
        context={"mfa_method": mfa_method} if mfa_method else None,
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

    mfa_enrollment_required = await _compute_mfa_enrollment_required(
        db, user, memberships, active_membership_id
    )

    return LoginResponse(
        user=await _build_user_read(db, user),
        memberships=memberships,
        active_membership_id=active_membership_id,
        csrf_token=csrf_token,
        mfa_enrollment_required=mfa_enrollment_required,
    )


@router.post("/login", response_model=LoginResponse | MfaRequiredResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse | MfaRequiredResponse:
    await login_rate_limiter.check(
        f"login-ip:{request.client.host if request.client else 'unknown'}",
        limit=settings.rate_limit_login_per_minute,
        window_seconds=60,
    )
    await login_rate_limiter.check(
        f"login-account:{payload.email.lower()}",
        limit=settings.rate_limit_login_per_hour_per_account,
        window_seconds=3600,
    )

    user = await identity_service.authenticate_user(db, payload.email, payload.password)

    if user.mfa_enabled:
        challenge_token = await identity_service.issue_mfa_challenge_token(db, user)
        await audit_service.record(
            db,
            tenant_id=None,
            actor_user_id=user.id,
            actor_label=user.email,
            action="auth.mfa_challenge_issued",
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()
        return MfaRequiredResponse(mfa_challenge_token=challenge_token)

    return await _complete_login(db, user, request, response)


@router.post("/mfa/verify-login", response_model=LoginResponse)
async def verify_login_mfa(
    payload: MfaVerifyLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    user = await identity_service.consume_mfa_challenge_token(
        db, payload.mfa_challenge_token, code=payload.code, backup_code=payload.backup_code
    )
    mfa_method = "backup_code" if payload.backup_code else "totp"
    return await _complete_login(db, user, request, response, mfa_method=mfa_method)


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
    mfa_enrollment_required = await _compute_mfa_enrollment_required(
        db, ctx.user, memberships, session_row.active_membership_id
    )
    return MeResponse(
        user=await _build_user_read(db, ctx.user),
        memberships=memberships,
        active_membership_id=session_row.active_membership_id,
        mfa_enrollment_required=mfa_enrollment_required,
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


@router.post("/mfa/enroll", response_model=MfaEnrollResponse, dependencies=[Depends(require_csrf)])
async def enroll_mfa(
    ctx: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)
) -> MfaEnrollResponse:
    secret, provisioning_uri = await identity_service.enroll_mfa(db, ctx.user)
    await db.commit()
    return MfaEnrollResponse(secret=secret, provisioning_uri=provisioning_uri)


@router.post("/mfa/confirm", response_model=MfaConfirmResponse, dependencies=[Depends(require_csrf)])
async def confirm_mfa(
    payload: MfaConfirmRequest,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> MfaConfirmResponse:
    backup_codes = await identity_service.confirm_mfa_enrollment(db, ctx.user, payload.code)
    await audit_service.record(
        db, tenant_id=None, actor_user_id=ctx.user.id, actor_label=ctx.user.email, action="auth.mfa_enabled"
    )
    await db.commit()
    return MfaConfirmResponse(backup_codes=backup_codes)


@router.post("/mfa/disable", dependencies=[Depends(require_csrf)])
async def disable_mfa(
    payload: MfaDisableRequest,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await identity_service.disable_mfa(db, ctx.user, payload.code)
    await audit_service.record(
        db, tenant_id=None, actor_user_id=ctx.user.id, actor_label=ctx.user.email, action="auth.mfa_disabled"
    )
    await db.commit()
    return {"status": "ok"}


@router.post(
    "/mfa/backup-codes/regenerate",
    response_model=MfaBackupCodesResponse,
    dependencies=[Depends(require_csrf)],
)
async def regenerate_backup_codes(
    payload: MfaRegenerateBackupCodesRequest,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> MfaBackupCodesResponse:
    """Milestone 24: invalidates every existing backup code and issues a
    fresh batch — used both for routine rotation and for topping back up
    after several codes have been spent."""
    backup_codes = await identity_service.regenerate_backup_codes(db, ctx.user, payload.code)
    await audit_service.record(
        db,
        tenant_id=None,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="auth.mfa_backup_codes_regenerated",
    )
    await db.commit()
    return MfaBackupCodesResponse(backup_codes=backup_codes)


@router.post("/step-up", response_model=StepUpResponse, dependencies=[Depends(require_csrf)])
async def step_up(
    payload: StepUpRequest,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> StepUpResponse:
    session_row = await identity_service.step_up_session(
        db, ctx.user, session_id=ctx.session_id, code=payload.code
    )
    await audit_service.record(
        db, tenant_id=None, actor_user_id=ctx.user.id, actor_label=ctx.user.email, action="auth.step_up"
    )
    await db.commit()
    return StepUpResponse(status="ok", step_up_expires_at=session_row.step_up_expires_at)


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
    await login_rate_limiter.check(
        f"forgot-password:{payload.email.lower()}", limit=5, window_seconds=3600
    )
    from sqlalchemy import select

    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if user is not None and user.is_active:
        token = await identity_service.issue_password_reset_token(db, user)
        await db.commit()
        send_email(
            to=user.email,
            subject="Reset your GRIDKEEP password",
            body=(
                "We received a request to reset your GRIDKEEP password.\n\n"
                "Use this token to choose a new password:\n\n"
                f"{token}\n\n"
                "If you did not request this, you can ignore this message."
            ),
        )
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
        user=await _build_user_read(db, user),
        memberships=memberships,
        active_membership_id=membership.id,
        csrf_token=csrf_token,
    )
