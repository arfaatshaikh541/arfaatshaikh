from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import AuthContext
from app.core.db import get_db, set_current_user_context
from app.core.errors import UnauthorizedError
from app.modules.identity import service as identity_service
from app.modules.identity.repository import UserRepository

settings = get_settings()


def get_current_auth_context(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise UnauthorizedError("Not authenticated.", code="not_authenticated")

    session = identity_service.get_session_by_raw_token(db, raw_token)
    if session is None:
        raise UnauthorizedError("Session is invalid or has expired.", code="session_invalid")

    identity_service.touch_session(db, session)

    user = UserRepository(db).get_by_id(session.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Account is no longer active.", code="account_inactive")

    set_current_user_context(db, user_id=user.id)
    request.state.session = session
    return AuthContext(user_id=user.id, email=user.email, is_platform_admin=user.is_platform_admin, session_id=session.id)
