from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session, get_current_user, require_csrf
from app.core.config import get_settings
from app.core.rate_limit import rate_limiter
from app.db.session import get_db_session
from app.models.identity import Session, User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    TokenRequest,
    UserResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])
settings = get_settings()


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=settings.cookie_path,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=settings.cookie_path,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, db: Annotated[AsyncSession, Depends(get_db_session)]) -> User:
    await rate_limiter.check(request, "register", settings.auth_rate_limit, 60)
    service = AuthService(db, settings)
    user = await service.register(str(payload.email), payload.password, payload.display_name)
    await db.commit()
    return user


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, request: Request, response: Response, db: Annotated[AsyncSession, Depends(get_db_session)]) -> AuthResponse:
    await rate_limiter.check(request, "login", settings.auth_rate_limit, 60)
    service = AuthService(db, settings)
    user = await service.authenticate(str(payload.email), payload.password)
    _, raw_token, csrf_token = await service.create_session(
        user,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    await db.commit()
    set_session_cookie(response, raw_token)
    return AuthResponse(user=UserResponse.model_validate(user), csrf_token=csrf_token)


@router.get("/csrf", response_model=AuthResponse)
async def csrf_session(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    session: Annotated[Session, Depends(get_current_session)],
) -> AuthResponse:
    service = AuthService(db, settings)
    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        from app.core.errors import ApplicationError
        raise ApplicationError("authentication_required", "Authentication is required.", 401)
    csrf_token = await service.rotate_csrf_token(session)
    await db.commit()
    return AuthResponse(user=UserResponse.model_validate(user), csrf_token=csrf_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response, db: Annotated[AsyncSession, Depends(get_db_session)], session: Annotated[Session, Depends(require_csrf)]) -> MessageResponse:
    await AuthService(db, settings).revoke_session(session, "logout")
    await db.commit()
    clear_session_cookie(response)
    return MessageResponse(message="Signed out.")


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@router.post("/verify-email", response_model=UserResponse)
async def verify_email(payload: TokenRequest, db: Annotated[AsyncSession, Depends(get_db_session)]) -> User:
    user = await AuthService(db, settings).verify_email(payload.token)
    await db.commit()
    return user


@router.post("/password-reset/request", response_model=MessageResponse)
async def request_reset(payload: PasswordResetRequest, request: Request, db: Annotated[AsyncSession, Depends(get_db_session)]) -> MessageResponse:
    await rate_limiter.check(request, "password-reset", settings.auth_rate_limit, 60)
    await AuthService(db, settings).request_password_reset(str(payload.email))
    await db.commit()
    return MessageResponse(message="If the account exists, reset instructions have been queued.")


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_reset(payload: PasswordResetConfirmRequest, db: Annotated[AsyncSession, Depends(get_db_session)]) -> MessageResponse:
    await AuthService(db, settings).confirm_password_reset(payload.token, payload.new_password)
    await db.commit()
    return MessageResponse(message="Password updated. Sign in again on all devices.")


@router.post("/sessions/revoke-all", response_model=MessageResponse)
async def revoke_all(db: Annotated[AsyncSession, Depends(get_db_session)], session: Annotated[Session, Depends(require_csrf)]) -> MessageResponse:
    await AuthService(db, settings).revoke_all_user_sessions(session.user_id, "user_requested")
    await db.commit()
    return MessageResponse(message="All sessions revoked.")
