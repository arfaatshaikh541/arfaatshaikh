"""Database engine, session factory, and declarative base.

Tenant isolation is enforced in two independent layers:
  1. Application layer: every tenant-owned repository method takes an
     explicit tenant_id derived server-side and filters by it.
  2. Database layer: PostgreSQL Row Level Security policies (see the
     Alembic migrations) reject any row whose tenant_id does not match
     the `app.current_tenant_id` session variable set by
     `set_tenant_context` below.

The application's runtime database role (APP_DB_USER) has NOBYPASSRLS,
so layer 2 holds even if layer 1 has a bug. Only the migration role
(MIGRATOR_DB_USER) bypasses RLS, and it is never used to serve requests.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, pool_pre_ping=True, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Plain (non-tenant-scoped) session dependency. Used for endpoints that
    operate on non-tenant-owned data (identity, platform admin, catalog
    tables). Tenant-scoped endpoints use `get_tenant_db` in dependencies.py,
    which layers `set_tenant_context` on top of this session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def set_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Sets the PostgreSQL session variable RLS policies key off of.

    Uses SET LOCAL so the value is scoped to the current transaction only
    and never leaks to a subsequent request that reuses a pooled connection.

    PostgreSQL's SET command does not accept bind parameters ($1) - the
    value must be a literal in the statement text. This is still injection
    -safe because `tenant_id` is required to be a `uuid.UUID` instance (not
    a raw string), so `str(tenant_id)` can only ever produce the fixed
    8-4-4-4-12 hex-and-hyphen UUID form, never attacker-controlled text.
    """
    if not isinstance(tenant_id, uuid.UUID):
        raise TypeError("tenant_id must be a uuid.UUID instance")
    await session.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'"))


async def set_platform_bypass(session: AsyncSession) -> None:
    """Enables the RLS bypass clause for the current transaction only.

    Every caller of this function MUST be an already-permission-checked
    platform-admin service method that writes a `platform_audit_logs` row
    in the same transaction - this is a deliberate, audited escape hatch,
    not a general-purpose way to skip tenant filtering.
    """
    await session.execute(text("SET LOCAL app.platform_bypass = 'true'"))
