from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import uuid
from email import message_from_bytes
from email import policy as email_policy
from email.message import EmailMessage
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
# Milestone 31 (finding C-01): the app's own runtime connection is the
# least-privilege gridkeep_app role (created by migration 34016597f04f,
# which runs below via `_apply_migrations`) — never the superuser
# DATABASE_MIGRATION_URL still uses. GRIDKEEP_APP_DB_PASSWORD is read by
# that migration when creating the role and must match the password
# embedded in DATABASE_URL, same pattern as docker-compose.yml/ci.yml.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://gridkeep_app:gridkeep-app-dev-only-insecure-do-not-use-in-production@localhost:5432/gridkeep_test",
)
os.environ.setdefault(
    "DATABASE_MIGRATION_URL", "postgresql+psycopg://gridkeep:gridkeep@localhost:5432/gridkeep_test"
)
os.environ.setdefault(
    "GRIDKEEP_APP_DB_PASSWORD", "gridkeep-app-dev-only-insecure-do-not-use-in-production"
)
os.environ.setdefault("VAULT_LOCAL_MASTER_KEY", "test-only-master-key-do-not-use-elsewhere-00000")
os.environ.setdefault("EVIDENCE_STORAGE_ROOT", tempfile.mkdtemp(prefix="gridkeep-evidence-test-"))
# Milestone 29: cookies are Secure-by-default now (core/config.py); the
# `client` fixture below talks to the app over a plain `http://testserver`
# ASGI transport, where a Secure cookie would never round-trip back to the
# server on a subsequent request, breaking every test that logs in once and
# makes further authenticated calls. This is the same explicit, narrowly
# named opt-out `docker-compose.yml` sets for local dev — not a weakening
# of what's actually being tested.
os.environ.setdefault("ALLOW_INSECURE_COOKIES_FOR_LOCAL_DEV", "true")

sys.path.insert(0, str(API_ROOT))

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

import main as app_main  # noqa: E402
from core.config import settings  # noqa: E402
from core.middleware import login_rate_limiter  # noqa: E402
from db import models_registry  # noqa: F401,E402
from db.session import AsyncSessionLocal  # noqa: E402
from seed.bootstrap import run_bootstrap  # noqa: E402

# Milestone 31 (finding C-01): TRUNCATE is a DDL-adjacent, administrative
# operation the application's own gridkeep_app role deliberately does NOT
# hold (only SELECT/INSERT/UPDATE/DELETE — see migration 34016597f04f) since
# real request handling never needs it. `_clean_tables` below still needs
# it for fast inter-test isolation, so it connects with the superuser
# migration credentials instead of `db.session.get_engine()` — never
# widening the app role's own grants just to make test cleanup convenient.
_migration_engine = create_async_engine(
    settings.database_migration_url.replace("postgresql+psycopg://", "postgresql+asyncpg://"),
    poolclass=NullPool,
    echo=False,
)


class _CapturingSMTPHandler:
    """Real SMTP handler (aiosmtpd) that records every message it receives.

    Milestone 28 replaced the `email_dispatch_simulated` log-line stand-in
    with a genuine `smtplib` client (`core/email.py`). Rather than mock
    that client in tests, this starts one real local SMTP server for the
    whole test session — bound to the same `mail_capture_host`/
    `mail_capture_port` production would point at Mailhog — so every route
    that sends email (onboarding, invitations, password reset) is exercised
    against a real wire-protocol SMTP exchange, same pattern as the local
    HTTP (M11) and DNS (M27) test servers."""

    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    async def handle_DATA(self, server, session, envelope):  # noqa: N802
        self.messages.append(message_from_bytes(envelope.content, policy=email_policy.default))
        return "250 Message accepted for delivery"


@pytest.fixture(scope="session", autouse=True)
def _smtp_capture():
    from aiosmtpd.controller import Controller

    handler = _CapturingSMTPHandler()
    controller = Controller(handler, hostname=settings.mail_capture_host, port=settings.mail_capture_port)
    controller.start()
    yield handler
    controller.stop()


@pytest.fixture(autouse=True)
def _clear_sent_emails(_smtp_capture):
    _smtp_capture.messages.clear()
    yield


@pytest.fixture
def sent_emails(_smtp_capture) -> list[EmailMessage]:
    return _smtp_capture.messages


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
        "trust_passport_settings",
        "evidence_records",
        "tenant_control_statuses",
        "incident_findings",
        "incident_assets",
        "incidents",
        "findings",
        "threat_indicators",
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
        "mfa_challenge_tokens",
        "sessions",
        "users",
        "tenant_domains",
        "tenant_security_profiles",
        "tenant_settings",
        "tenants",
    ]
    async with _migration_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    await run_bootstrap()


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limiter():
    """`login_rate_limiter` is a process-wide singleton backed by Redis
    (Milestone 23) so its state must not leak between tests."""
    await login_rate_limiter.reset_all()
    yield
    await login_rate_limiter.reset_all()


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
