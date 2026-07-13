import uuid
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        return self.db.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        email: str,
        hashed_password: str,
        first_name: str,
        last_name: str,
        is_platform_super_admin: bool = False,
        email_verified: bool = False,
    ) -> User:
        from datetime import datetime

        user = User(
            email=email.lower(),
            hashed_password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            is_platform_super_admin=is_platform_super_admin,
            email_verified_at=datetime.now(UTC) if email_verified else None,
        )
        self.db.add(user)
        self.db.flush()
        return user
