from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_config
from .models import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        url = get_config().database_url
        _engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, future=True)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def reset_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on any exception."""
    s = session_factory()()
    try:
        yield s
        s.commit()
    except BaseException:
        s.rollback()
        raise
    finally:
        s.close()


def init_db() -> None:
    """Create tables (idempotent) and register the static connector registry."""
    engine = get_engine()
    from sqlalchemy import text

    with engine.begin() as c:  # serialise schema creation across processes starting together
        c.execute(text("SELECT pg_advisory_xact_lock(4242000)"))
        Base.metadata.create_all(c)
    from .migrations import run_migrations

    run_migrations(engine)
    from .connectors.registry import sync_platform_registry

    with session_scope() as s:
        sync_platform_registry(s)


def check_db() -> tuple[bool, str]:
    try:
        with get_engine().connect() as c:
            c.execute(text("SELECT 1"))
        return True, "HEALTHY"
    except Exception as e:  # pragma: no cover - depends on infra
        return False, f"UNREACHABLE: {type(e).__name__}"
