import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.session import AuthSession


class SessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: uuid.UUID,
        refresh_token_hash: str,
        expires_at: datetime,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthSession:
        session = AuthSession(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def get_by_id(self, session_id: uuid.UUID) -> AuthSession | None:
        return self.db.get(AuthSession, session_id)

    def get_by_refresh_token_hash(self, token_hash: str) -> AuthSession | None:
        stmt = select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_active_for_user(self, user_id: uuid.UUID) -> list[AuthSession]:
        stmt = select(AuthSession).where(
            AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)
        )
        return list(self.db.execute(stmt).scalars().all())

    def revoke(
        self, session: AuthSession, *, replaced_by_id: uuid.UUID | None = None
    ) -> AuthSession:
        from app.db.base import utcnow

        session.revoked_at = utcnow()
        if replaced_by_id:
            session.replaced_by_id = replaced_by_id
        self.db.flush()
        return session

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        for session in self.list_active_for_user(user_id):
            self.revoke(session)
