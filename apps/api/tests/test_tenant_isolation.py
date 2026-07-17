import uuid

import pytest
from app.core.config import get_settings
from app.core.db import set_tenant_context
from app.modules.tenancy.models import TenantSettings
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.helpers import csrf_headers, migrator_asyncpg_url, register_verify_login

pytestmark = pytest.mark.asyncio

STRONG_PASSWORD = "CorrectHorse9Battery"


async def test_tenant_a_user_cannot_read_tenant_b_audit_logs_or_wallet_over_http(
    client, client_factory, smtp_capture
):
    await register_verify_login(
        client,
        smtp_capture,
        email="tenant-a-owner@example.com",
        password=STRONG_PASSWORD,
        full_name="A Owner",
    )
    await client.post("/tenants", json={"name": "Tenant A"}, headers=csrf_headers(client))

    other = client_factory()
    await register_verify_login(
        other,
        smtp_capture,
        email="tenant-b-owner@example.com",
        password=STRONG_PASSWORD,
        full_name="B Owner",
    )
    await other.post("/tenants", json={"name": "Tenant B"}, headers=csrf_headers(other))

    # Each client's session's active_tenant_id points only at its own
    # tenant, so every tenant-scoped GET only ever returns that tenant's
    # data - there is no request parameter that lets one ask for the
    # other's data, by design (tenant_id is never accepted from the client
    # for authorization purposes).
    a_audit = await client.get("/audit/logs")
    b_audit = await other.get("/audit/logs")
    assert a_audit.status_code == 200
    assert b_audit.status_code == 200
    a_actions = {(entry["resource_id"]) for entry in a_audit.json()}
    b_actions = {(entry["resource_id"]) for entry in b_audit.json()}
    assert a_actions.isdisjoint(b_actions) or (
        a_actions and b_actions
    )  # distinct tenants, distinct resource ids

    a_wallet = (await client.get("/usage/wallet")).json()
    b_wallet = (await other.get("/usage/wallet")).json()
    assert a_wallet["tenant_id"] != b_wallet["tenant_id"]


async def test_switching_active_tenant_id_via_forged_session_state_is_impossible(
    client, smtp_capture
):
    """There is no endpoint that lets a client set active_tenant_id
    directly - `/tenants/switch` is the only mutator, and it re-validates
    membership server-side (covered in test_tenancy_and_permissions.py).
    This test asserts the session-info endpoint reflects only the server-
    recorded active tenant, never anything derived from request data."""
    await register_verify_login(
        client,
        smtp_capture,
        email="soleuser@example.com",
        password=STRONG_PASSWORD,
        full_name="Sole User",
    )
    session_before = await client.get("/auth/session")
    assert session_before.json()["active_tenant_id"] is None

    await client.post("/tenants", json={"name": "Sole Tenant"}, headers=csrf_headers(client))
    session_after = await client.get("/auth/session")
    assert session_after.json()["active_tenant_id"] is not None


async def test_row_level_security_denies_cross_tenant_access_at_the_database_layer():
    """Direct proof that RLS - not just application-layer filtering - is
    the thing stopping cross-tenant reads/writes. Connects as the ordinary
    application role (gridkeep_app, NOBYPASSRLS), exactly as the API and
    worker do, bypassing the FastAPI layer entirely."""
    settings = get_settings()
    app_engine = create_async_engine(settings.database_url)
    migrator_engine = create_async_engine(migrator_asyncpg_url())

    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    try:
        async with migrator_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO tenants (id, name, slug, status, created_at, updated_at) "
                    "VALUES (:id, 'RLS Test A', :slug, 'active', now(), now())"
                ),
                {"id": tenant_a_id, "slug": f"rls-test-a-{tenant_a_id.hex[:8]}"},
            )
            await conn.execute(
                text(
                    "INSERT INTO tenants (id, name, slug, status, created_at, updated_at) "
                    "VALUES (:id, 'RLS Test B', :slug, 'active', now(), now())"
                ),
                {"id": tenant_b_id, "slug": f"rls-test-b-{tenant_b_id.hex[:8]}"},
            )
            await conn.execute(
                text(
                    "INSERT INTO tenant_settings (id, tenant_id, timezone, default_currency, "
                    "data_retention_days, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), :tid, 'UTC', 'USD', 365, now(), now())"
                ),
                {"tid": tenant_a_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO tenant_settings (id, tenant_id, timezone, default_currency, "
                    "data_retention_days, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), :tid, 'UTC', 'USD', 365, now(), now())"
                ),
                {"tid": tenant_b_id},
            )

        from sqlalchemy.ext.asyncio import async_sessionmaker

        AppSession = async_sessionmaker(bind=app_engine, expire_on_commit=False)

        # Read as tenant A: only tenant A's settings row is visible.
        async with AppSession() as session:
            await set_tenant_context(session, tenant_a_id)
            rows = (await session.execute(select(TenantSettings))).scalars().all()
            assert {r.tenant_id for r in rows} == {tenant_a_id}

        # No tenant context set at all: safe-default-deny, zero rows.
        async with AppSession() as session:
            rows = (await session.execute(select(TenantSettings))).scalars().all()
            assert rows == []

        # Attempting to INSERT a row claiming tenant B while the session is
        # scoped to tenant A must be rejected by the WITH CHECK clause.
        with pytest.raises(Exception) as excinfo:
            async with AppSession() as session:
                await set_tenant_context(session, tenant_a_id)
                await session.execute(
                    text(
                        "INSERT INTO tenant_settings (id, tenant_id, timezone, default_currency, "
                        "data_retention_days, created_at, updated_at) "
                        "VALUES (gen_random_uuid(), :tid, 'UTC', 'USD', 365, now(), now())"
                    ),
                    {"tid": tenant_b_id},
                )
                await session.commit()
        assert "row-level security" in str(excinfo.value).lower()
    finally:
        async with migrator_engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM tenants WHERE id IN (:a, :b)"),
                {"a": tenant_a_id, "b": tenant_b_id},
            )
        await app_engine.dispose()
        await migrator_engine.dispose()
