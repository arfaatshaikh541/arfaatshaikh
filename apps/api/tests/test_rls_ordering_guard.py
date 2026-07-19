"""Milestone 11 (ADR-0019): the RLS *ordering* guard - the runtime
complement to Milestone 10's schema-level *coverage* check
(`test_rls_coverage.py`). ADR-0007 named this gap explicitly: a query
against an RLS-protected table on a session that never had
`set_tenant_context`/`set_platform_bypass` called on it doesn't error -
Postgres's own RLS policy just silently returns zero rows, indistinguishable
from "no data yet." `app.core.db`'s `do_orm_execute`/`after_transaction_end`
listeners on `_AppSession` (the class `AsyncSessionLocal` - the only
session factory anywhere in this codebase's production code - is built
on) instead fail loudly and immediately, in every environment.

These tests exercise the real `AsyncSessionLocal` (not a mocked
substitute) against the real test database, proving each property the
prototype this guard was designed from was checked against by hand
before being trusted: blocks a context-less query, permits one after
either context function, re-blocks after the transaction that set
context ends, and does NOT re-block across a nested SAVEPOINT (the CSV
import per-row pattern).
"""

import uuid

import pytest
from app.core.db import AsyncSessionLocal, set_platform_bypass, set_tenant_context
from app.modules.leads.models import Lead
from sqlalchemy import select, text

pytestmark = pytest.mark.asyncio


async def test_query_against_rls_table_with_no_context_raises():
    async with AsyncSessionLocal() as session:
        with pytest.raises(RuntimeError, match="RLS ordering violation"):
            await session.execute(select(Lead).limit(1))
        await session.rollback()


async def test_set_tenant_context_permits_the_query():
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, uuid.uuid4())
        result = await session.execute(select(Lead).limit(1))
        assert result.first() is None  # a random tenant id genuinely has no leads
        await session.rollback()


async def test_set_platform_bypass_permits_the_query():
    async with AsyncSessionLocal() as session:
        await set_platform_bypass(session)
        await session.execute(select(Lead).limit(1))
        await session.rollback()


async def test_marker_is_cleared_after_commit_and_the_next_query_is_reblocked():
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, uuid.uuid4())
        await session.execute(select(Lead).limit(1))
        await session.commit()  # SET LOCAL's own transaction just ended

        with pytest.raises(RuntimeError, match="RLS ordering violation"):
            await session.execute(select(Lead).limit(1))
        await session.rollback()


async def test_marker_survives_a_nested_savepoint_rollback():
    """The exact shape `worker.csv_import_tasks` relies on: one
    `set_tenant_context` call at the top of a task, then a per-row
    `session.begin_nested()` SAVEPOINT that may roll back without
    ending the outer transaction `SET LOCAL` is scoped to."""
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, uuid.uuid4())
        await session.execute(select(Lead).limit(1))

        with pytest.raises(ValueError, match="simulated per-row failure"):
            async with session.begin_nested():
                await session.execute(select(Lead).limit(1))
                raise ValueError("simulated per-row failure")

        # Outer transaction never ended - context must still be live.
        await session.execute(select(Lead).limit(1))
        await session.rollback()


async def test_guard_does_not_false_positive_on_platform_audit_logs():
    """Regression test for the exact bug found on this guard's first
    real run: `platform_audit_logs` is a substring collision risk for
    the (guarded) `audit_logs` table name - `list_platform_audit_logs`'s
    query (no context needed - platform_audit_logs is application-layer
    gated, never RLS-protected) must not be blocked."""
    from app.modules.audit.models import PlatformAuditLog

    async with AsyncSessionLocal() as session:
        await session.execute(select(PlatformAuditLog).limit(1))
        await session.rollback()


async def test_guard_does_not_false_positive_on_roles_or_role_permissions():
    """`roles`/`role_permissions` have a deliberately more permissive RLS
    policy (`... OR tenant_id IS NULL`) for platform-role catalog rows
    that must be readable with no tenant context - the guard excludes
    them for exactly this reason (see app.core.db's own comment)."""
    from app.modules.permissions.models import Role, RolePermission

    async with AsyncSessionLocal() as session:
        await session.execute(select(Role).limit(1))
        await session.execute(select(RolePermission).limit(1))
        await session.rollback()


async def test_guard_does_not_apply_to_a_session_outside_asyncsessionlocal():
    """Scoping proof: an ad-hoc sessionmaker (the pattern this test suite's
    own service-level tests use throughout, e.g. `test_lead_workspace.py`'s
    `_session_factory()`, connecting as the migrator role) must not be
    affected by this guard - those sessions connect as a role with
    BYPASSRLS, so the Python-level marker genuinely doesn't matter there,
    and guarding them would be a pure false positive."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from tests.helpers import migrator_asyncpg_url

    engine = create_async_engine(migrator_asyncpg_url())
    try:
        OtherSession = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with OtherSession() as session:
            # No set_tenant_context/set_platform_bypass call at all - would
            # raise under _AppSession, must not raise here.
            await session.execute(select(Lead).limit(1))
    finally:
        await engine.dispose()


async def test_raw_text_query_against_a_protected_table_is_also_guarded():
    """The guard hooks `do_orm_execute`, which fires for `session.execute
    (text(...))` too, not only ORM-constructed statements - every raw-SQL
    query in this codebase's repositories goes through `session.execute`,
    so this is the realistic shape, not just `select()`."""
    async with AsyncSessionLocal() as session:
        with pytest.raises(RuntimeError, match="RLS ordering violation"):
            await session.execute(text("SELECT 1 FROM leads LIMIT 1"))
        await session.rollback()
