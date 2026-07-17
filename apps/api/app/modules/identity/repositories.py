import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import EmailVerificationToken, PasswordResetToken, Session, User


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email.lower())
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    stmt = select(User).where(User.id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password_hash: str,
    full_name: str,
    email_verified: bool = False,
) -> User:
    user = User(
        email=email.lower(),
        password_hash=password_hash,
        full_name=full_name,
        email_verified=email_verified,
    )
    session.add(user)
    await session.flush()
    return user


async def create_email_verification_token(
    session: AsyncSession, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
) -> EmailVerificationToken:
    token = EmailVerificationToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    session.add(token)
    await session.flush()
    return token


async def get_valid_email_verification_token(
    session: AsyncSession, token_hash: str
) -> EmailVerificationToken | None:
    stmt = select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_password_reset_token(
    session: AsyncSession, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
) -> PasswordResetToken:
    token = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    session.add(token)
    await session.flush()
    return token


async def get_valid_password_reset_token(
    session: AsyncSession, token_hash: str
) -> PasswordResetToken | None:
    stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_session(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
    active_tenant_id: uuid.UUID | None,
    ip_address: str | None,
    user_agent: str | None,
) -> Session:
    session_row = Session(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        active_tenant_id=active_tenant_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(session_row)
    await session.flush()
    return session_row


async def revoke_all_sessions_for_user(
    session: AsyncSession, user_id: uuid.UUID, *, now: datetime
) -> None:
    stmt = select(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None))
    rows = (await session.execute(stmt)).scalars().all()
    for row in rows:
        row.revoked_at = now
