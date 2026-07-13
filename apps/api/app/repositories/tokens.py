import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.tokens import EmailVerificationToken, LoginAttempt, PasswordResetToken


class EmailVerificationTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> EmailVerificationToken:
        token = EmailVerificationToken(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )
        self.db.add(token)
        self.db.flush()
        return token

    def get_valid_by_hash(self, token_hash: str) -> EmailVerificationToken | None:
        stmt = select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.consumed_at.is_(None),
            EmailVerificationToken.expires_at > utcnow(),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def consume(self, token: EmailVerificationToken) -> None:
        token.consumed_at = utcnow()
        self.db.flush()


class PasswordResetTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> PasswordResetToken:
        token = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.db.add(token)
        self.db.flush()
        return token

    def get_valid_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.consumed_at.is_(None),
            PasswordResetToken.expires_at > utcnow(),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def consume(self, token: PasswordResetToken) -> None:
        token.consumed_at = utcnow()
        self.db.flush()


class LoginAttemptRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(self, *, email: str, ip_address: str, success: bool) -> LoginAttempt:
        attempt = LoginAttempt(
            email=email.lower(), ip_address=ip_address, success=success, created_at=utcnow()
        )
        self.db.add(attempt)
        self.db.flush()
        return attempt

    def count_recent_failures(self, *, email: str, ip_address: str, window_minutes: int) -> int:
        since = utcnow() - timedelta(minutes=window_minutes)
        stmt = (
            select(func.count())
            .select_from(LoginAttempt)
            .where(
                LoginAttempt.email == email.lower(),
                LoginAttempt.ip_address == ip_address,
                LoginAttempt.success.is_(False),
                LoginAttempt.created_at >= since,
            )
        )
        return int(self.db.execute(stmt).scalar_one())
