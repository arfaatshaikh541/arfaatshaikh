"""Test harness: runs against a real PostgreSQL database (JOBAP_TEST_DATABASE_URL).

Tests create their own rows and truncate every table between tests. They never
touch the production database and never create fake records in it.
"""
from __future__ import annotations

import base64
import os

import pytest

TEST_DB = os.environ.get("JOBAP_TEST_DATABASE_URL", "")
if not TEST_DB:
    raise RuntimeError("Set JOBAP_TEST_DATABASE_URL to a dedicated, empty PostgreSQL test database "
                       "(it is truncated between tests)")


@pytest.fixture(scope="session", autouse=True)
def _env(tmp_path_factory):
    os.environ["JOBAP_DATABASE_URL"] = TEST_DB
    os.environ["JOBAP_MASTER_KEY"] = base64.urlsafe_b64encode(os.urandom(32)).decode()
    os.environ["JOBAP_DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    os.environ["JOBAP_SECURE_COOKIES"] = "false"
    from autopilot.config import reset_config_cache
    from autopilot.db import reset_engine

    reset_config_cache()
    reset_engine()
    from autopilot.db import get_engine
    from autopilot.models import Base

    Base.metadata.drop_all(get_engine())
    from autopilot.db import init_db

    init_db()
    yield


@pytest.fixture(autouse=True)
def clean_db():
    from sqlalchemy import text

    from autopilot.db import get_engine, session_scope
    from autopilot.models import Base
    from autopilot.connectors.registry import sync_platform_registry

    names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with get_engine().begin() as c:
        c.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    with session_scope() as s:
        sync_platform_registry(s)
    yield


@pytest.fixture
def s():
    from autopilot.db import session_factory

    sess = session_factory()()
    yield sess
    sess.rollback()
    sess.close()


@pytest.fixture
def user(s):
    from autopilot.models import User
    from autopilot.security.passwords import hash_password

    u = User(email="owner@test.invalid", password_hash=hash_password("correct horse battery"))
    s.add(u)
    s.commit()
    return u


@pytest.fixture
def profile(s, user):
    from autopilot.profile.service import get_or_create_profile

    p = get_or_create_profile(s, user.id)
    s.commit()
    return p
