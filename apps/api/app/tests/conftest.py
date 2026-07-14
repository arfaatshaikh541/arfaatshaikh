"""Test fixtures.

Every test runs inside a real transaction against a real PostgreSQL test
database (RLS enabled, both app_migrator and app_runtime roles
provisioned identically to production) — no mocked database, no SQLite
substitution. Each test's transaction is rolled back afterward so tests
never leak state into one another, using SQLAlchemy's savepoint-join
pattern: the app's own `db.commit()` calls (inside `get_db`) release a
savepoint rather than the real transaction, and the fixture's final
rollback discards everything.
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://app_runtime:app_runtime_dev_only@127.0.0.1:5432/cops_test")
os.environ.setdefault("MIGRATION_DATABASE_URL", "postgresql+psycopg://app_migrator:app_migrator_dev_only@127.0.0.1:5432/cops_test")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
os.environ.setdefault("RATE_LIMIT_REDIS_URL", "redis://127.0.0.1:6379/9")
os.environ.setdefault("CELERY_BROKER_URL", "redis://127.0.0.1:6379/1")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/2")
os.environ.setdefault("SMTP_HOST", "127.0.0.1")
os.environ.setdefault("SMTP_PORT", "1025")

import app.core.email as email_module  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.core.rate_limit import get_redis  # noqa: E402
from app.main import app  # noqa: E402
from app.tests.factories import seed_catalog  # noqa: E402
from app.tests.fakes import FakeEmailProvider  # noqa: E402

settings = get_settings()
_test_engine = create_engine(settings.database_url, pool_pre_ping=True)


@pytest.fixture(autouse=True)
def _flush_rate_limit_redis():
    """Login throttling uses a dedicated Redis DB (index 9 by default in
    tests) — flush it before every test so one test's failed-login
    attempts never throttle another test."""
    get_redis().flushdb()
    yield


@pytest.fixture()
def fake_email(monkeypatch) -> FakeEmailProvider:
    provider = FakeEmailProvider()
    monkeypatch.setattr(email_module, "_provider", provider)
    monkeypatch.setattr(email_module, "get_email_provider", lambda: provider)
    return provider


@pytest.fixture()
def db_session(fake_email):
    connection = _test_engine.connect()
    outer_transaction = connection.begin()

    session_factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session: Session = session_factory()

    seed_catalog(session)
    session.commit()  # releases the savepoint so seeded catalog rows are visible to subsequent queries

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def login(client: TestClient, email: str, password: str) -> TestClient:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return client
