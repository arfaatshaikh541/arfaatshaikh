from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.core.security import constant_time_equal, hash_token
from app.db.context import set_request_user_context
from app.db.session import get_db_session
from app.models.identity import Session, User
from app.services.auth import AuthService

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_session(request: Request, db: DbSession) -> Session:
    session_token = request.cookies.get(get_settings().session_cookie_name)
    if not session_token:
        raise ApplicationError("authentication_required", "Authentication is required.", 401)
    session = await AuthService(db, get_settings()).get_session(session_token)
    if session is None:
        raise ApplicationError("authentication_required", "Authentication is required.", 401)
    return session


async def get_current_user(db: DbSession, session: Annotated[Session, Depends(get_current_session)]) -> User:
    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise ApplicationError("authentication_required", "Authentication is required.", 401)
    await set_request_user_context(db, user.id)
    return user


async def require_csrf(
    request: Request,
    session: Annotated[Session, Depends(get_current_session)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> Session:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return session
    if not csrf_token:
        raise ApplicationError("csrf_failed", "CSRF validation failed.", 403)
    expected = hash_token(csrf_token, get_settings().secret_key.get_secret_value())
    if not constant_time_equal(expected, session.csrf_token_hash):
        raise ApplicationError("csrf_failed", "CSRF validation failed.", 403)
    return session
