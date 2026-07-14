from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import AuthContext
from app.core.db import get_db, set_current_user_context, set_rls_context
from app.core.errors import RateLimitedError
from app.core.rate_limit import is_rate_limited, login_throttle_key, reset_rate_limit
from app.dependencies.auth import get_current_auth_context
from app.modules.identity import service as identity_service
from app.modules.identity.repository import UserRepository
from app.modules.identity.schemas import (
    AcceptInvitationRequest,
    CurrentUserResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MembershipSummary,
    ResetPasswordRequest,
    SwitchTenantRequest,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

LOGIN_MAX_ATTEMPTS = 8
LOGIN_WINDOW_SECONDS = 15 * 60


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_session_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_absolute_ttl_hours * 3600,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.session_cookie_name, path="/")


@router.post("/login", response_model=CurrentUserResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> CurrentUserResponse:
    ip_address = _client_ip(request)
    throttle_key = login_throttle_key(payload.email, ip_address)
    limited, retry_after = is_rate_limited(throttle_key, max_attempts=LOGIN_MAX_ATTEMPTS, window_seconds=LOGIN_WINDOW_SECONDS)
    if limited:
        raise RateLimitedError(
            f"Too many login attempts. Try again in {retry_after} seconds.", code="login_rate_limited"
        )

    user = identity_service.authenticate(db, email=payload.email, password=payload.password, ip_address=ip_address)
    reset_rate_limit(throttle_key)
    set_current_user_context(db, user_id=user.id)

    memberships = identity_service.list_user_memberships_with_tenant(db, user.id)
    active_tenant_id = memberships[0]["tenant_id"] if memberships else None
    # Now that the tenant this login activates is known, establish it as
    # the RLS context for the rest of the request (e.g. the audit log
    # entry written by create_session below).
    set_rls_context(db, tenant_id=active_tenant_id, is_platform_admin=user.is_platform_admin)

    session, raw_token = identity_service.create_session(
        db, user=user, active_tenant_id=active_tenant_id, ip_address=ip_address, user_agent=request.headers.get("user-agent")
    )
    _set_session_cookie(response, raw_token)

    return CurrentUserResponse(
        id=user.id, email=user.email, first_name=user.first_name, last_name=user.last_name,
        email_verified=user.email_verified, is_platform_admin=user.is_platform_admin,
        active_tenant_id=active_tenant_id,
        memberships=[MembershipSummary(**m) for m in memberships],
    )


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token:
        session = identity_service.get_session_by_raw_token(db, raw_token)
        if session:
            identity_service.revoke_session(db, session)
    _clear_session_cookie(response)


@router.get("/me", response_model=CurrentUserResponse)
def get_me(request: Request, auth: AuthContext = Depends(get_current_auth_context), db: Session = Depends(get_db)) -> CurrentUserResponse:
    user = UserRepository(db).get_by_id(auth.user_id)
    memberships = identity_service.list_user_memberships_with_tenant(db, auth.user_id)
    session = request.state.session
    return CurrentUserResponse(
        id=user.id, email=user.email, first_name=user.first_name, last_name=user.last_name,
        email_verified=user.email_verified, is_platform_admin=user.is_platform_admin,
        active_tenant_id=session.active_tenant_id,
        memberships=[MembershipSummary(**m) for m in memberships],
    )


@router.post("/switch-tenant", response_model=CurrentUserResponse)
def switch_tenant(
    payload: SwitchTenantRequest, request: Request, auth: AuthContext = Depends(get_current_auth_context), db: Session = Depends(get_db)
) -> CurrentUserResponse:
    session = request.state.session
    identity_service.switch_active_tenant(db, session=session, user_id=auth.user_id, tenant_id=payload.tenant_id)
    user = UserRepository(db).get_by_id(auth.user_id)
    memberships = identity_service.list_user_memberships_with_tenant(db, auth.user_id)
    return CurrentUserResponse(
        id=user.id, email=user.email, first_name=user.first_name, last_name=user.last_name,
        email_verified=user.email_verified, is_platform_admin=user.is_platform_admin,
        active_tenant_id=session.active_tenant_id,
        memberships=[MembershipSummary(**m) for m in memberships],
    )


@router.post("/accept-invitation", response_model=CurrentUserResponse, status_code=201)
def accept_invitation(payload: AcceptInvitationRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> CurrentUserResponse:
    user, invitation = identity_service.accept_invitation(
        db, token=payload.token, password=payload.password, first_name=payload.first_name, last_name=payload.last_name
    )
    session, raw_token = identity_service.create_session(
        db, user=user, active_tenant_id=invitation.tenant_id, ip_address=_client_ip(request), user_agent=request.headers.get("user-agent")
    )
    _set_session_cookie(response, raw_token)
    memberships = identity_service.list_user_memberships_with_tenant(db, user.id)
    return CurrentUserResponse(
        id=user.id, email=user.email, first_name=user.first_name, last_name=user.last_name,
        email_verified=user.email_verified, is_platform_admin=user.is_platform_admin,
        active_tenant_id=invitation.tenant_id,
        memberships=[MembershipSummary(**m) for m in memberships],
    )


@router.post("/forgot-password", status_code=202)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    identity_service.request_password_reset(db, email=payload.email)
    return {"status": "ok"}


@router.post("/reset-password", status_code=204)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> None:
    identity_service.reset_password(db, token=payload.token, new_password=payload.new_password)


@router.post("/verify-email/request", status_code=202)
def request_email_verification(auth: AuthContext = Depends(get_current_auth_context), db: Session = Depends(get_db)) -> dict:
    user = UserRepository(db).get_by_id(auth.user_id)
    identity_service.request_email_verification(db, user=user)
    return {"status": "ok"}


@router.post("/verify-email", status_code=204)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> None:
    identity_service.verify_email(db, token=payload.token)
