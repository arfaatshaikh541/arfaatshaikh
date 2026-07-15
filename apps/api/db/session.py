from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from core.config import settings

# Both pytest and the Celery worker call `asyncio.run()`/
# `loop.run_until_complete()` once per test/task rather than running the
# whole process inside a single top-level asyncio.run() the way uvicorn
# does. asyncpg's connection objects carry internal Task/Future bookkeeping
# that doesn't survive being checked out again in a *later* such call —
# a pooled connection combined with `pool_pre_ping` then fails with
# "attached to a different loop" on the second test/task that touches the
# database in that process. NullPool sidesteps this by opening a fresh
# connection per checkout. `apps/worker/celery_app.py` sets
# GRIDKEEP_WORKER_PROCESS=1 before this module is ever imported.
_NEEDS_NULLPOOL = settings.environment == "test" or os.environ.get("GRIDKEEP_WORKER_PROCESS") == "1"

if _NEEDS_NULLPOOL:
    _engine: AsyncEngine = create_async_engine(settings.database_url, poolclass=NullPool, echo=False)
else:
    _engine = create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        echo=False,
    )

AsyncSessionLocal = async_sessionmaker(bind=_engine, expire_on_commit=False, autoflush=False)


def get_engine() -> AsyncEngine:
    return _engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Plain DB session with no tenant context set. Only platform-scoped
    code paths (platform_admin routes, migrations, seed scripts) may use
    this directly — everything tenant-facing must go through
    `tenant_scoped_session` so Postgres RLS has a tenant to check against."""
    async with AsyncSessionLocal() as session:
        yield session


async def set_user_context(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Sets `app.current_user_id`, used only by the narrow `memberships`
    RLS policy that lets an authenticated user list their OWN membership
    rows across tenants before they've picked one (needed at login /
    `/auth/me` time). This does not grant visibility into any other
    tenant-owned table — every other RLS policy keys on
    `app.current_tenant_id` alone."""
    await session.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"), {"uid": str(user_id)}
    )


async def set_tenant_context(
    session: AsyncSession, tenant_id: uuid.UUID, *, is_platform_admin: bool = False
) -> None:
    """Sets the RLS session variables on an already-open session/transaction
    — used by flows (like tenant onboarding) that must create the tenant
    and its first tenant-owned rows atomically in a single transaction."""
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_id)}
    )
    await session.execute(
        text("SELECT set_config('app.is_platform_admin', :flag, true)"),
        {"flag": "true" if is_platform_admin else "false"},
    )


@asynccontextmanager
async def tenant_scoped_session(
    tenant_id: uuid.UUID, *, is_platform_admin: bool = False
) -> AsyncGenerator[AsyncSession, None]:
    """Opens a transaction and sets the Postgres session variables that
    Row-Level-Security policies key on. `SET LOCAL` scopes the setting to
    the current transaction only, so it can never leak onto a pooled
    connection reused by a different tenant's request."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )
            await session.execute(
                text("SELECT set_config('app.is_platform_admin', :flag, true)"),
                {"flag": "true" if is_platform_admin else "false"},
            )
            yield session
