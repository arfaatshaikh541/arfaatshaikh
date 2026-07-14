from __future__ import annotations

import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_current_user
from app.api.serializers import build_current_user_out
from app.core.config import get_settings
from app.core.cookies import ACCESS_TOKEN_COOKIE, CSRF_COOKIE, REFRESH_TOKEN_COOKIE
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    ResetPasswordRequest,
    SessionOut,
    VerifyEmailRequest,
)
from app.schemas.common import MessageResponse
from app.schemas.tenant import TenantCreate
from app.schemas.user import ChangePasswordRequest, CurrentUserOut
from app.services.auth_service import AuthService, IssuedTokens
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/auth", tags=["auth"])


def set_auth_cookies(response: Response, tokens: IssuedTokens) -> None:
    settings = get_settings()
    domain = settings.cookie_domain or None
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        tokens.access_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=domain,
        path="/",
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        tokens.refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=domain,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        tokens.csrf_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=domain,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    for name in (ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, domain=settings.cookie_domain or None, path="/")


@router.post("/signup", response_model=LoginResponse, status_code=201)
def signup(
    payload: TenantCreate,
    response: Response,
    db: Session = Depends(get_db),
    ip: str = Depends(client_ip),
) -> LoginResponse:
    TenantService(db).self_signup(
        name=payload.name,
        slug=payload.slug,
        legal_name=payload.legal_name,
        timezone=payload.timezone,
        currency=payload.currency,
        owner_email=payload.owner_email,
        owner_first_name=payload.owner_first_name,
        owner_last_name=payload.owner_last_name,
        owner_password=payload.owner_password,
        ip_address=ip,
    )
    db.commit()

    auth_service = AuthService(db)
    tokens = auth_service.login(
        email=payload.owner_email,
        password=payload.owner_password,
        ip_address=ip,
        user_agent=None,
    )
    auth_service.start_email_verification(tokens.user)
    db.commit()

    set_auth_cookies(response, tokens)
    return LoginResponse(user=build_current_user_out(db, tokens.user))


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    ip: str = Depends(client_ip),
) -> LoginResponse:
    tokens = AuthService(db).login(
        email=payload.email, password=payload.password, ip_address=ip, user_agent=None
    )
    db.commit()
    set_auth_cookies(response, tokens)
    return LoginResponse(user=build_current_user_out(db, tokens.user))


@router.post("/refresh", response_model=LoginResponse)
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    ip: str = Depends(client_ip),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE),
) -> LoginResponse:
    if refresh_token is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    tokens = AuthService(db).refresh(refresh_token=refresh_token, ip_address=ip, user_agent=None)
    db.commit()
    set_auth_cookies(response, tokens)
    return LoginResponse(user=build_current_user_out(db, tokens.user))


@router.get("/me", response_model=CurrentUserOut)
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> CurrentUserOut:
    return build_current_user_out(db, user)


@router.post("/logout", response_model=MessageResponse)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    access_token: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE),
) -> MessageResponse:
    if access_token is not None:
        from app.core.security import decode_access_token

        try:
            payload = decode_access_token(access_token)
            AuthService(db).logout(session_id=uuid.UUID(payload["sid"]))
            db.commit()
        except Exception:
            pass
    clear_auth_cookies(response)
    return MessageResponse(message="Logged out.")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    AuthService(db).request_password_reset(payload.email)
    db.commit()
    return MessageResponse(message="If that email exists, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    AuthService(db).reset_password(token=payload.token, new_password=payload.new_password)
    db.commit()
    return MessageResponse(message="Password has been reset. Please log in again.")


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> MessageResponse:
    AuthService(db).verify_email(payload.token)
    db.commit()
    return MessageResponse(message="Email verified.")


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MessageResponse:
    AuthService(db).change_password(
        user=user, current_password=payload.current_password, new_password=payload.new_password
    )
    db.commit()
    return MessageResponse(message="Password changed. Other sessions have been signed out.")


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[SessionOut]:
    sessions = AuthService(db).list_sessions(user.id)
    return [SessionOut.model_validate(s) for s in sessions]


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
def revoke_session(
    session_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> MessageResponse:
    AuthService(db).revoke_session(user_id=user.id, session_id=session_id)
    db.commit()
    return MessageResponse(message="Session revoked.")
