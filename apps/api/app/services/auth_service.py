from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_csrf_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)
from app.db.base import utcnow
from app.models.session import AuthSession
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.session import SessionRepository
from app.repositories.tokens import (
    EmailVerificationTokenRepository,
    LoginAttemptRepository,
    PasswordResetTokenRepository,
)
from app.repositories.user import UserRepository
from app.services.email_service import send_password_reset_email, send_verification_email
from app.services.errors import RateLimitedError, UnauthorizedError, ValidationError

GENERIC_LOGIN_ERROR = "Invalid email or password."


@dataclass
class IssuedTokens:
    access_token: str
    refresh_token: str
    csrf_token: str
    session: AuthSession
    user: User


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.users = UserRepository(db)
        self.sessions = SessionRepository(db)
        self.login_attempts = LoginAttemptRepository(db)
        self.email_tokens = EmailVerificationTokenRepository(db)
        self.reset_tokens = PasswordResetTokenRepository(db)
        self.audit = AuditLogRepository(db)

    def _issue_tokens(
        self, user: User, *, user_agent: str | None, ip_address: str | None
    ) -> IssuedTokens:
        refresh_token = generate_opaque_token()
        session = self.sessions.create(
            user_id=user.id,
            refresh_token_hash=hash_opaque_token(refresh_token),
            expires_at=utcnow() + timedelta(days=self.settings.refresh_token_expire_days),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        access_token = create_access_token(user_id=str(user.id), session_id=str(session.id))
        return IssuedTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=generate_csrf_token(),
            session=session,
            user=user,
        )

    def login(
        self, *, email: str, password: str, ip_address: str, user_agent: str | None
    ) -> IssuedTokens:
        window = self.settings.login_rate_limit_window_minutes
        max_attempts = self.settings.login_rate_limit_attempts
        recent_failures = self.login_attempts.count_recent_failures(
            email=email, ip_address=ip_address, window_minutes=window
        )
        if recent_failures >= max_attempts:
            raise RateLimitedError("Too many login attempts. Please try again later.")

        user = self.users.get_by_email(email)
        valid = (
            user is not None and user.is_active and verify_password(password, user.hashed_password)
        )
        locked = user is not None and user.locked_until is not None and user.locked_until > utcnow()

        if not valid or locked:
            self.login_attempts.record(email=email, ip_address=ip_address, success=False)
            if user is not None:
                user.failed_login_count += 1
                if user.failed_login_count >= max_attempts:
                    user.locked_until = utcnow() + timedelta(minutes=15)
                self.db.flush()
            raise UnauthorizedError(GENERIC_LOGIN_ERROR)

        assert user is not None  # `valid` above is False when user is None
        user.failed_login_count = 0
        user.locked_until = None
        self.login_attempts.record(email=email, ip_address=ip_address, success=True)
        self.db.flush()

        return self._issue_tokens(user, user_agent=user_agent, ip_address=ip_address)

    def refresh(
        self, *, refresh_token: str, ip_address: str | None, user_agent: str | None
    ) -> IssuedTokens:
        token_hash = hash_opaque_token(refresh_token)
        session = self.sessions.get_by_refresh_token_hash(token_hash)
        if session is None:
            raise UnauthorizedError("Invalid session.")

        if session.revoked_at is not None:
            # Reuse of an already-rotated refresh token: treat as compromise,
            # revoke the whole session family for this user.
            self.sessions.revoke_all_for_user(session.user_id)
            self.audit.record(
                event_type="auth.refresh_token_reuse_detected",
                actor_user_id=session.user_id,
                metadata={"session_id": str(session.id)},
            )
            raise UnauthorizedError("Session invalid. Please log in again.")

        if session.expires_at < utcnow():
            raise UnauthorizedError("Session expired. Please log in again.")

        user = self.users.get_by_id(session.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("Account unavailable.")

        new_tokens = self._issue_tokens(user, user_agent=user_agent, ip_address=ip_address)
        self.sessions.revoke(session, replaced_by_id=new_tokens.session.id)
        return new_tokens

    def logout(self, *, session_id: uuid.UUID) -> None:
        session = self.sessions.get_by_id(session_id)
        if session is not None and session.revoked_at is None:
            self.sessions.revoke(session)

    def list_sessions(self, user_id: uuid.UUID) -> list[AuthSession]:
        return self.sessions.list_active_for_user(user_id)

    def revoke_session(self, *, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
        session = self.sessions.get_by_id(session_id)
        if session is None or session.user_id != user_id:
            raise UnauthorizedError("Session not found.")
        if session.revoked_at is None:
            self.sessions.revoke(session)

    def change_password(self, *, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise ValidationError("Current password is incorrect.")
        user.hashed_password = hash_password(new_password)
        self.db.flush()
        self.sessions.revoke_all_for_user(user.id)

    # --- Email verification -------------------------------------------------

    def start_email_verification(self, user: User) -> str:
        token = generate_opaque_token()
        self.email_tokens.create(
            user_id=user.id,
            token_hash=hash_opaque_token(token),
            expires_at=utcnow() + timedelta(hours=24),
        )
        verify_url = f"{self.settings.web_base_url}/verify-email?token={token}"
        send_verification_email(to=user.email, verify_url=verify_url)
        return token

    def verify_email(self, token: str) -> User:
        record = self.email_tokens.get_valid_by_hash(hash_opaque_token(token))
        if record is None:
            raise ValidationError("Invalid or expired verification link.")
        user = self.users.get_by_id(record.user_id)
        if user is None:
            raise ValidationError("Invalid or expired verification link.")
        user.email_verified_at = utcnow()
        self.email_tokens.consume(record)
        self.db.flush()
        return user

    # --- Password reset -------------------------------------------------

    def request_password_reset(self, email: str) -> None:
        user = self.users.get_by_email(email)
        if user is None:
            return  # generic success response regardless, to prevent enumeration
        token = generate_opaque_token()
        self.reset_tokens.create(
            user_id=user.id,
            token_hash=hash_opaque_token(token),
            expires_at=utcnow() + timedelta(hours=1),
        )
        reset_url = f"{self.settings.web_base_url}/reset-password?token={token}"
        send_password_reset_email(to=user.email, reset_url=reset_url)

    def reset_password(self, *, token: str, new_password: str) -> None:
        record = self.reset_tokens.get_valid_by_hash(hash_opaque_token(token))
        if record is None:
            raise ValidationError("Invalid or expired reset link.")
        user = self.users.get_by_id(record.user_id)
        if user is None:
            raise ValidationError("Invalid or expired reset link.")
        user.hashed_password = hash_password(new_password)
        user.failed_login_count = 0
        user.locked_until = None
        self.reset_tokens.consume(record)
        self.db.flush()
        self.sessions.revoke_all_for_user(user.id)
