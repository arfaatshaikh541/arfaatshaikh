from typing import Annotated

from fastapi import Depends
from sqlalchemy import select

from app.api.dependencies.auth import DbSession, get_current_user
from app.core.errors import ApplicationError
from app.models.identity import User
from app.models.tenancy import PlatformAdministrator


async def require_platform_administrator(
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    administrator = await db.scalar(
        select(PlatformAdministrator.id).where(
            PlatformAdministrator.user_id == user.id,
            PlatformAdministrator.active.is_(True),
        )
    )
    if administrator is None:
        raise ApplicationError("platform_admin_required", "Platform administrator access is required.", 403)
    return user
