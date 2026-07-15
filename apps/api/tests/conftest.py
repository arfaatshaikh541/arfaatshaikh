from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio

API_ROOT = Path(__file__).resolve().parents[1]

# Convention: any async test that touches the database must be decorated
# with `@pytest.mark.asyncio(loop_scope="session")` (not the bare
# `asyncio_mode=auto` default). The SQLAlchemy async engine's NullPool
# (see db/session.py) opens a fresh asyncpg connection per checkout in the
# test environment specifically to avoid connections leaking state across
# pytest-asyncio's per-test `run_until_complete()` calls; pairing that with
# the session-scoped loop keeps DB-touching tests fast and isolated
# without the "attached to a different loop" failure mode.

# Must happen BEFORE any app module is imported (core.config reads env at
# import time via pydantic-settings), so this runs at module import of
# conftest.py, which pytest always does before collecting test modules.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://gridkeep:gridkeep@localhost:5432/gridkeep_test"
)
os.environ.setdefault(
    "DATABASE_MIGRATION_URL", "postgresql+psycopg://gridkeep:gridkeep@localhost:5432/gridkeep_test"
)
os.environ.setdefault("VAULT_LOCAL_MASTER_KEY", "test-only-master-key-do-not-use-elsewhere-00000")

sys.path.insert(0, str(API_ROOT))

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

import main as app_main  # noqa: E402
from core.middleware import login_rate_limiter  # noqa: E402
from db import models_registry  # noqa: F401,E402
from db.session import AsyncSessionLocal, get_engine  # noqa: E402
from seed.bootstrap import run_bootstrap  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations() -> None:
    """Runs the real Alembic migration chain against gridkeep_test once per
    test session — tests exercise the same schema and RLS policies that
    ship to production, not a hand-rolled `create_all()` shortcut."""
    env = os.environ.copy()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(API_ROOT),
        env=env,
        check=True,
        capture_output=True,
    )


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _bootstrap_catalog(_apply_migrations) -> None:
    await run_bootstrap()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(_bootstrap_catalog):
    """Truncates tenant-owned/transactional tables after every test so
    tests are isolated without paying for a full migration re-run.

    `roles.tenant_id` is a nullable FK to `tenants.id` (system roles have
    it NULL, but the column exists for future per-tenant custom roles), so
    `TRUNCATE tenants ... CASCADE` also wipes `roles` and, transitively,
    `role_permissions` — the seeded catalog data. Re-running the (already
    idempotent) bootstrap seed after each truncate restores it cheaply
    rather than trying to hand-craft a CASCADE-free truncate order."""
    yield
    engine = get_engine()
    tables = [
        "audit_logs",
        "support_access_grants",
        "trial_grants",
        "tenant_feature_overrides",
        "tenant_add_ons",
        "usage_records",
        "tenant_subscriptions",
        "action_runs",
        "playbooks",
        "tenant_automation_settings",
        "findings",
        "asset_changes",
        "asset_tags",
        "asset_owners",
        "asset_relationships",
        "asset_identifiers",
        "assets",
        "integration_sync_runs",
        "integration_health",
        "tenant_integrations",
        "integration_credentials",
        "invitations",
        "memberships",
        "email_verification_tokens",
        "password_reset_tokens",
        "sessions",
        "users",
        "tenant_domains",
        "tenant_security_profiles",
        "tenant_settings",
        "tenants",
    ]
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    await run_bootstrap()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """`login_rate_limiter` is a process-wide singleton (by design — see
    core/middleware.py) so its state must not leak between tests."""
    login_rate_limiter._hits.clear()
    yield
    login_rate_limiter._hits.clear()


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app_main.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:12]}@example.com"
