from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.core.security import generate_token, hash_password, hash_token, utcnow, verify_password
from app.models.identity import EmailOutbox, EmailVerificationToken, PasswordResetToken, Session, User


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.pepper = settings.secret_key.get_secret_value()

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().casefold()

    async def register(self, email: str, password: str, display_name: str) -> User:
        normalized = self.normalize_email(email)
        existing = await self.session.scalar(select(User.id).where(User.email == normalized))
        if existing:
            raise ApplicationError("email_unavailable", "An account cannot be created with this email.", 409)

        now = utcnow()
        user = User(
            email=normalized,
            password_hash=hash_password(password),
            display_name=display_name,
            password_changed_at=now,
        )
        self.session.add(user)
        await self.session.flush()
        await self.issue_email_verification(user)
        return user

    async def authenticate(self, email: str, password: str) -> User:
        normalized = self.normalize_email(email)
        user = await self.session.scalar(select(User).where(User.email == normalized))
        if user is None or not verify_password(user.password_hash if user else "", password):
            raise ApplicationError("invalid_credentials", "Invalid email or password.", 401)
        if not user.is_active:
            raise ApplicationError("account_inactive", "This account is not active.", 403)
        return user

    async def create_session(self, user: User, ip_address: str | None, user_agent: str | None) -> tuple[Session, str, str]:
        raw_token = generate_token()
        csrf_token = generate_token()
        now = utcnow()
        session = Session(
            user_id=user.id,
            token_hash=hash_token(raw_token, self.pepper),
            csrf_token_hash=hash_token(csrf_token, self.pepper),
            expires_at=now + timedelta(seconds=self.settings.session_ttl_seconds),
            last_seen_at=now,
            ip_address=ip_address,
            user_agent=(user_agent or "")[:512] or None,
        )
        self.session.add(session)
        await self.session.flush()
        return session, raw_token, csrf_token

    async def get_session(self, raw_token: str) -> Session | None:
        now = utcnow()
        return await self.session.scalar(
            select(Session)
            .where(
                Session.token_hash == hash_token(raw_token, self.pepper),
                Session.revoked_at.is_(None),
                Session.expires_at > now,
            )
        )

    async def rotate_csrf_token(self, session: Session) -> str:
        csrf_token = generate_token()
        session.csrf_token_hash = hash_token(csrf_token, self.pepper)
        session.last_seen_at = utcnow()
        await self.session.flush()
        return csrf_token

    async def revoke_session(self, session: Session, reason: str) -> None:
        if session.revoked_at is None:
            session.revoked_at = utcnow()
            session.revocation_reason = reason
            await self.session.flush()

    async def revoke_all_user_sessions(self, user_id, reason: str) -> None:
        await self.session.execute(
            update(Session)
            .where(Session.user_id == user_id, Session.revoked_at.is_(None))
            .values(revoked_at=utcnow(), revocation_reason=reason)
        )

    async def issue_email_verification(self, user: User) -> str:
        raw = generate_token()
        now = utcnow()
        self.session.add(EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(raw, self.pepper),
            expires_at=now + timedelta(seconds=self.settings.email_verification_ttl_seconds),
        ))
        self.session.add(EmailOutbox(
            kind="email_verification",
            recipient=user.email,
            template_id="verify-email-v1",
            payload_json=json.dumps({"token": raw}, separators=(",", ":")),
            available_at=now,
        ))
        await self.session.flush()
        return raw

    async def verify_email(self, raw_token: str) -> User:
        now = utcnow()
        token = await self.session.scalar(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token_hash == hash_token(raw_token, self.pepper),
                EmailVerificationToken.consumed_at.is_(None),
                EmailVerificationToken.expires_at > now,
            )
        )
        if token is None:
            raise ApplicationError("invalid_verification_token", "Verification token is invalid or expired.", 400)
        user = await self.session.get(User, token.user_id)
        if user is None:
            raise ApplicationError("invalid_verification_token", "Verification token is invalid or expired.", 400)
        token.consumed_at = now
        user.email_verified_at = user.email_verified_at or now
        await self.session.flush()
        return user

    async def request_password_reset(self, email: str) -> None:
        user = await self.session.scalar(select(User).where(User.email == self.normalize_email(email), User.is_active.is_(True)))
        if user is None:
            return
        raw = generate_token()
        now = utcnow()
        self.session.add(PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw, self.pepper),
            expires_at=now + timedelta(seconds=self.settings.password_reset_ttl_seconds),
        ))
        self.session.add(EmailOutbox(
            kind="password_reset",
            recipient=user.email,
            template_id="password-reset-v1",
            payload_json=json.dumps({"token": raw}, separators=(",", ":")),
            available_at=now,
        ))
        await self.session.flush()

    async def confirm_password_reset(self, raw_token: str, new_password: str) -> User:
        now = utcnow()
        token = await self.session.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == hash_token(raw_token, self.pepper),
                PasswordResetToken.consumed_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
        )
        if token is None:
            raise ApplicationError("invalid_reset_token", "Password reset token is invalid or expired.", 400)
        user = await self.session.get(User, token.user_id)
        if user is None or not user.is_active:
            raise ApplicationError("invalid_reset_token", "Password reset token is invalid or expired.", 400)
        user.password_hash = hash_password(new_password)
        user.password_changed_at = now
        token.consumed_at = now
        await self.revoke_all_user_sessions(user.id, "password_reset")
        await self.session.flush()
        return user
