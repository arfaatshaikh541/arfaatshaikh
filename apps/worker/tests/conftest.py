"""Test configuration for the worker package.

Points at the same real, separate `gridkeep_test` PostgreSQL database and
test Redis logical databases as `apps/api/tests/conftest.py` (this package
depends on `gridkeep-api` and shares its models/migrations, so there is
only one schema to keep in sync). Migrations are applied once per session;
the platform catalog is reseeded and both Postgres and the relevant Redis
logical databases are reset between tests, mirroring the API's own test
isolation strategy.
"""

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://gridkeep_app:gridkeep_app_dev_password@localhost:5432/gridkeep_test",
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg://gridkeep_migrator:gridkeep_migrator_dev_password@localhost:5432/gridkeep_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/14")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
os.environ.setdefault(
    "SESSION_SECRET", "test-secret-not-for-production-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
)
os.environ.setdefault(
    "CSRF_SECRET", "test-secret-not-for-production-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
)
os.environ.setdefault("SMTP_HOST", "localhost")
os.environ.setdefault("SMTP_PORT", "1025")

import pathlib

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# API_ROOT: alembic.ini and the migration scripts live in apps/api, not
# apps/worker - this package only runs migrations in tests to get a schema
# to run task-chain logic against, it never authors its own migrations.
API_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent / "api"


@pytest.fixture(scope="session", autouse=True)
def apply_migrations():
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    command.upgrade(cfg, "head")
    yield


def _migrator_asyncpg_url() -> str:
    from app.core.config import get_settings

    settings = get_settings()
    return settings.database_url_sync.replace("postgresql+psycopg", "postgresql+asyncpg")


@pytest_asyncio.fixture(autouse=True)
async def reset_database():
    from app.seed.seed_data import seed_permissions, seed_platform_roles, seed_subscription_plans

    engine = create_async_engine(_migrator_asyncpg_url())
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE tenants, users RESTART IDENTITY CASCADE"))

    Session = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with Session() as session:
        permissions_by_key = await seed_permissions(session)
        await seed_platform_roles(session, permissions_by_key)
        await seed_subscription_plans(session)
        await session.commit()
    await engine.dispose()

    from app.core.rate_limit import get_redis

    await get_redis().flushdb()
    yield


@pytest_asyncio.fixture
async def migrator_session():
    """A raw, RLS-bypassing session for setting up fixture data (creating
    tenants/campaigns/jobs/tasks directly) the same way the API's own tests
    do - the worker's task-processing coroutines are exercised directly in
    these tests, not through HTTP, so there is no request-scoped session to
    borrow tenant context from."""
    engine = create_async_engine(_migrator_asyncpg_url())
    Session = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()
