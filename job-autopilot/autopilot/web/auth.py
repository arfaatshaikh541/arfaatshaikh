"""Server-side sessions, CSRF and login throttling."""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_config
from ..models import User, WebSession, utcnow
from ..security.passwords import verify_password

COOKIE = "jap_session"
MAX_FAILED = 5
LOCK_MINUTES = 15


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(s: Session, user: User, request: Request) -> str:
    token = secrets.token_urlsafe(32)
    s.add(WebSession(user_id=user.id, token_hash=_h(token), csrf_token=secrets.token_urlsafe(32),
                     expires_at=utcnow() + dt.timedelta(hours=get_config().session_hours),
                     ip=request.client.host if request.client else None,
                     user_agent=(request.headers.get("user-agent") or "")[:500]))
    return token


def get_session(s: Session, request: Request) -> tuple[User, WebSession] | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    ws = s.scalar(select(WebSession).where(WebSession.token_hash == _h(token)))
    if ws is None or ws.expires_at < utcnow():
        return None
    u = s.get(User, ws.user_id)
    if u is None or not u.is_active:
        return None
    return u, ws


def destroy_session(s: Session, request: Request) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        ws = s.scalar(select(WebSession).where(WebSession.token_hash == _h(token)))
        if ws:
            s.delete(ws)


def authenticate(s: Session, email: str, password: str) -> tuple[User | None, str]:
    u = s.scalar(select(User).where(User.email == email.strip().lower()))
    if u is None:
        verify_password(password, "scrypt$32768$8$1$AAAAAAAAAAAAAAAAAAAAAA==$AAAA")  # equalise timing
        return None, "Invalid email or password"
    if u.locked_until and u.locked_until > utcnow():
        return None, "Account temporarily locked after repeated failures"
    if not verify_password(password, u.password_hash):
        u.failed_logins += 1
        if u.failed_logins >= MAX_FAILED:
            u.locked_until = utcnow() + dt.timedelta(minutes=LOCK_MINUTES)
            u.failed_logins = 0
        return None, "Invalid email or password"
    u.failed_logins = 0
    u.locked_until = None
    return u, "ok"


def check_csrf(ws: WebSession, submitted: str | None) -> None:
    if not submitted or not hmac.compare_digest(ws.csrf_token, submitted):
        raise HTTPException(status_code=403, detail="CSRF token invalid")
