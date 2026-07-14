from collections.abc import Generator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# Runtime engine: connects as app_runtime, subject to row-level security.
engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# Migration engine: connects as app_migrator, used only by Alembic (BYPASSRLS).
migration_engine = create_engine(settings.migration_database_url, pool_pre_ping=True)


def set_rls_context(session: Session, *, tenant_id: UUID | None, is_platform_admin: bool = False) -> None:
    """Sets the Postgres session-local variables that RLS policies key off.

    Must run inside the same transaction as the queries it protects — uses
    `set_config(..., is_local=true)` (the parameterised equivalent of
    `SET LOCAL`) so the value never leaks to other requests sharing a
    pooled connection and is never built via raw string interpolation.
    """
    session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id) if tenant_id else ""},
    )
    session.execute(
        text("SELECT set_config('app.is_platform_admin', :flag, true)"),
        {"flag": "true" if is_platform_admin else "false"},
    )


def set_current_user_context(session: Session, *, user_id: UUID | None) -> None:
    """Sets `app.current_user_id`, consulted only by the `memberships`
    table's "own rows" RLS policy. This exists because a user must be
    able to list/read their own membership rows (to discover which
    tenants they belong to, e.g. at login and tenant-switch time) before
    any tenant has been selected — i.e. before `set_rls_context` has a
    tenant_id to set. Scoping this to "rows where user_id matches me" is
    safe precisely because it can never expose another user's
    memberships, regardless of tenant.
    """
    session.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user_id) if user_id else ""},
    )


def clear_rls_context(session: Session) -> None:
    set_rls_context(session, tenant_id=None, is_platform_admin=False)
    set_current_user_context(session, user_id=None)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session.

    Does NOT set tenant/platform-admin RLS context by itself — that is set
    by the tenant-context dependency once the authenticated tenant is
    known, so routes that need no tenant context (e.g. login) get a
    session with no tenant visibility at all by default.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for use outside of FastAPI request handling (seed scripts, Celery tasks)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
