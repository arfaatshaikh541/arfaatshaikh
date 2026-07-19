"""Test configuration.

Points the app at a real, separate PostgreSQL database (gridkeep_test) and
a separate Redis logical database (15) - these are genuine Postgres/Redis
instances, not mocks. Migrations are applied once per test session; the
platform catalog (permissions, platform roles, subscription plans) is
seeded once per session; and tenant/user data created by each test is
truncated and the catalog re-seeded between tests so tests don't leak
state into each other.
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
os.environ.setdefault(
    "CREDENTIAL_ENCRYPTION_MASTER_KEY",
    "test-secret-not-for-production-cccccccccccccccccccccccccccccccc",
)
os.environ.setdefault("SMTP_HOST", "localhost")
os.environ.setdefault("SMTP_PORT", "1025")

import pathlib

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from app.seed.seed_data import seed_permissions, seed_platform_roles, seed_subscription_plans
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.helpers import migrator_asyncpg_url

API_ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def apply_migrations():
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    command.upgrade(cfg, "head")
    yield


async def _reseed_catalog_and_reset(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE tenants, users RESTART IDENTITY CASCADE"))

    from sqlalchemy.ext.asyncio import async_sessionmaker

    Session = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with Session() as session:
        permissions_by_key = await seed_permissions(session)
        await seed_platform_roles(session, permissions_by_key)
        await seed_subscription_plans(session)
        await session.commit()


@pytest_asyncio.fixture(autouse=True)
async def reset_database():
    """Runs before every test: truncates tenant/user data and re-seeds the
    platform catalog, using a migrator-privileged connection (bypasses RLS,
    has TRUNCATE rights - the ordinary app role deliberately does not).
    Also flushes the test Redis logical database, since rate-limit counters
    persist independently of Postgres state and would otherwise leak
    between tests (and between separate pytest invocations)."""
    engine = create_async_engine(migrator_asyncpg_url())
    await _reseed_catalog_and_reset(engine)
    await engine.dispose()

    from app.core.rate_limit import get_redis

    await get_redis().flushdb()
    yield


@pytest_asyncio.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def moto_s3(monkeypatch):
    """A real local S3-API server (`moto.server.ThreadedMotoServer`) - no
    MinIO binary is installable in this sandbox (no Docker daemon, no
    internet access to fetch one; see docs/adr/0015). Needed here (unlike
    most API-level tests) because CSV import's upload/preview endpoint
    uploads the file synchronously from the request handler itself (see
    `csv_import.services.preview_csv`), not only from a background
    Celery task the way exports' upload does."""
    import boto3
    from app.core.config import get_settings
    from moto.server import ThreadedMotoServer

    server = ThreadedMotoServer(port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    endpoint_url = f"http://{host}:{port}"

    monkeypatch.setenv("S3_ENDPOINT_URL", endpoint_url)
    get_settings.cache_clear()

    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name=get_settings().s3_region,
    )
    client.create_bucket(Bucket=get_settings().s3_bucket_name)

    try:
        yield client
    finally:
        server.stop()
        get_settings.cache_clear()


@pytest_asyncio.fixture
async def client_factory():
    """Yields a factory for creating additional independent AsyncClient
    instances (separate cookie jars) against the same app - needed for
    tests that simulate two different logged-in users concurrently."""
    from app.main import app

    transport = ASGITransport(app=app)
    created: list[AsyncClient] = []

    def _make() -> AsyncClient:
        ac = AsyncClient(transport=transport, base_url="http://test")
        created.append(ac)
        return ac

    yield _make

    for ac in created:
        await ac.aclose()


@pytest.fixture(scope="session", autouse=True)
def smtp_capture():
    from tests.helpers import SMTPCapture

    capture = SMTPCapture()
    capture.start()
    yield capture
    capture.stop()


@pytest.fixture(autouse=True)
def _clear_smtp_capture(smtp_capture):
    smtp_capture.clear()
    yield
