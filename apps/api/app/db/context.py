from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_request_user_context(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


async def set_request_tenant_context(session: AsyncSession, organisation_id: UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.current_organisation_id', :organisation_id, true)"),
        {"organisation_id": str(organisation_id)},
    )
