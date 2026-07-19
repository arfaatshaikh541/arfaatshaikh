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

import re
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, SessionTransaction, mapped_column

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, pool_pre_ping=True, echo=False)

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


# --- RLS ordering guard (ADR-0007's named gap, closed in Milestone 11 /
# ADR-0019) -------------------------------------------------------------
#
# Milestone 10 automated *coverage* (every tenant-owned table genuinely
# has RLS) but left *ordering* (every query preceded by a
# set_tenant_context/set_platform_bypass call on the same session) as a
# manual-discipline risk - the exact class of bug that hit
# worker.campaign_tasks and worker.csv_import_tasks once each already.
# Without this, a forgotten context call doesn't error - Postgres's own
# RLS policy just silently returns zero rows, which is indistinguishable
# from "no data yet" during ordinary testing/manual verification. This
# listener instead fails loudly, immediately, in every environment
# (there is no settings flag gating it - the whole point is that it
# can't be silently skipped), the moment a query against an
# RLS-protected table runs on a session that never had either function
# called on it.
#
# Scoped to `_AppSession` (below), not the global `Session` class:
# attaching it globally would also fire for the ad-hoc, migrator-role
# sessions test setup code constructs directly (e.g. `async_sessionmaker
# (bind=create_async_engine(migrator_asyncpg_url()))` throughout this
# test suite) - those connect as a role with BYPASSRLS, so lacking this
# Python-level marker is genuinely harmless there, and guarding them
# anyway would be a pure false positive, not a real risk caught.
# `AsyncSessionLocal` (the only session factory anywhere in this
# codebase's production code - both the API and the worker import it
# directly from here) is built with `sync_session_class=_AppSession`
# specifically so this guard protects every real request/task session
# without touching unrelated test-only sessions.
_RLS_CONTEXT_MARKER = "rls_context_set"
_rls_protected_table_names_cache: frozenset[str] | None = None


# Tables this guard deliberately does not check, even though they carry
# a `tenant_id` column:
#
#   platform_audit_logs - `tenant_id` is an informational nullable FK
#   ("which tenant did this platform action target"), not an ownership
#   column - the table is intentionally platform-only, gated entirely by
#   application-layer permission checks, never by RLS at all.
#
#   roles, role_permissions - genuinely RLS-protected, but with a policy
#   shape the other ~44 tables don't share: `tenant_id = current_tenant_id
#   OR tenant_id IS NULL OR platform_bypass` (confirmed directly from
#   pg_policies). The extra `tenant_id IS NULL` clause is deliberate -
#   platform-role catalog rows must be readable with no tenant context at
#   all (e.g. `require_platform_permission` in app/dependencies.py checks
#   a platform admin's own role permissions before any tenant is
#   selected, by design). Excluding them here trades away this guard's
#   protection for the *tenant-scoped* half of these two tables (a
#   context-less query for a real tenant's own custom role would still
#   silently return zero rows, exactly the failure mode this guard exists
#   to catch) - accepted as the same class of scoping tradeoff as the
#   platform_audit_logs exception, since a real per-query-aware check
#   would need actual SQL parsing, not a cheap substring scan.
_GUARD_EXCLUDED_TABLES = frozenset({"platform_audit_logs", "roles", "role_permissions"})


def _rls_protected_table_names() -> frozenset[str]:
    """Every table with a `tenant_id` column, computed once from the ORM
    metadata (populated by `app.core.model_registry`) rather than a
    hardcoded list - so a future tenant-owned table is covered
    automatically, the same reasoning `test_rls_coverage.py` (Milestone
    10) already used for the schema-introspecting coverage check. See
    `_GUARD_EXCLUDED_TABLES` above for the deliberate exceptions."""
    global _rls_protected_table_names_cache
    if _rls_protected_table_names_cache is None:
        _rls_protected_table_names_cache = frozenset(
            table.name
            for table in Base.metadata.tables.values()
            if "tenant_id" in table.columns and table.name not in _GUARD_EXCLUDED_TABLES
        )
    return _rls_protected_table_names_cache


_rls_protected_table_pattern_cache: re.Pattern[str] | None = None


def _rls_protected_table_pattern() -> re.Pattern[str]:
    """A single compiled `\\b(table1|table2|...)\\b` pattern, word-
    boundary-delimited - a naive substring check would false-positive on
    e.g. `audit_logs` matching inside `platform_audit_logs` (confirmed:
    this happened on the very first real run of this guard, against
    `list_platform_audit_logs`'s query - `"_"` is a `\\w` character, so
    there is no word boundary between `platform` and `audit_logs`,
    exactly the property `\\b` relies on here)."""
    global _rls_protected_table_pattern_cache
    if _rls_protected_table_pattern_cache is None:
        names = sorted(_rls_protected_table_names(), key=len, reverse=True)
        _rls_protected_table_pattern_cache = re.compile(
            r"\b(?:" + "|".join(re.escape(name) for name in names) + r")\b"
        )
    return _rls_protected_table_pattern_cache


class _AppSession(Session):
    """The sync `Session` class `AsyncSessionLocal` is built on - exists
    solely to give the RLS ordering guard below a specific event target,
    distinct from the plain `Session` class ad-hoc test sessions use."""


@event.listens_for(_AppSession, "do_orm_execute")
def _guard_rls_context_before_execute(orm_execute_state) -> None:  # noqa: ANN001
    session = orm_execute_state.session
    if session.info.get(_RLS_CONTEXT_MARKER):
        return
    statement_text = str(orm_execute_state.statement)
    match = _rls_protected_table_pattern().search(statement_text)
    if match is not None:
        table_name = match.group(0)
        raise RuntimeError(
            f"RLS ordering violation: a query against tenant-owned table "
            f"{table_name!r} ran on a session that never had "
            "set_tenant_context() or set_platform_bypass() called on it. "
            "Postgres's own RLS policy would have silently returned zero "
            "rows here - indistinguishable from 'no data yet' - which is "
            "exactly the failure mode this check exists to catch loudly "
            "and immediately instead. Call set_tenant_context(session, "
            "tenant_id) (or set_platform_bypass(session), for the narrow, "
            "justified cases in docs/adr/0007) before this query. See "
            "docs/adr/0019."
        )


@event.listens_for(_AppSession, "after_transaction_end")
def _clear_rls_context_marker_on_outer_transaction_end(
    session: Session, transaction: SessionTransaction
) -> None:
    # SET LOCAL is scoped to the outermost transaction, not to a
    # SAVEPOINT - a nested transaction (session.begin_nested(), used by
    # e.g. CSV import's per-row isolation) ending must NOT clear the
    # marker, or every row after the first would be wrongly re-blocked.
    if transaction.parent is None:
        session.info.pop(_RLS_CONTEXT_MARKER, None)


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    sync_session_class=_AppSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
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
    session.info[_RLS_CONTEXT_MARKER] = True


async def set_platform_bypass(session: AsyncSession) -> None:
    """Enables the RLS bypass clause for the current transaction only.

    Every caller of this function MUST be an already-permission-checked
    platform-admin service method that writes a `platform_audit_logs` row
    in the same transaction - this is a deliberate, audited escape hatch,
    not a general-purpose way to skip tenant filtering.
    """
    await session.execute(text("SET LOCAL app.platform_bypass = 'true'"))
    session.info[_RLS_CONTEXT_MARKER] = True
