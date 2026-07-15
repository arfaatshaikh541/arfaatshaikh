"""Tenant-isolation tests — the highest-priority security surface for a
multi-tenant platform (architecture §6-7, Rule 19)."""

import uuid

import pytest
from sqlalchemy import select, text

from db.session import AsyncSessionLocal, set_tenant_context
from modules.permissions.models import Membership, Role
from tests.helpers import login, onboard_verified_owner

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _new_tenant_owner(client, db, *, org: str, email: str, password: str = "Tenant-Pass1!"):
    await onboard_verified_owner(
        client, db, org_name=org, full_name="Owner", email=email, password=password
    )
    resp = await login(client, email, password)
    assert resp.status_code == 200
    payload = resp.json()
    return {
        "tenant_id": payload["memberships"][0]["tenant_id"],
        "membership_id": payload["memberships"][0]["membership_id"],
        "csrf_token": payload["csrf_token"],
        "user_id": payload["user"]["id"],
    }


async def test_cannot_rotate_another_tenants_credential(client, db):
    tenant_a = await _new_tenant_owner(client, db, org="Tenant A Co", email="ownerA@tenant-a.example")
    create_resp = await client.post(
        "/api/integrations/credentials",
        json={"provider_key": "mock_identity", "label": "A's secret", "secret": "a-secret-value"},
        headers={"X-CSRF-Token": tenant_a["csrf_token"]},
    )
    assert create_resp.status_code == 200
    credential_id = create_resp.json()["id"]
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": tenant_a["csrf_token"]})

    tenant_b_client = client
    tenant_b = await _new_tenant_owner(
        tenant_b_client, db, org="Tenant B Co", email="ownerB@tenant-b.example"
    )

    rotate_resp = await tenant_b_client.post(
        f"/api/integrations/credentials/{credential_id}/rotate",
        json={"secret": "hijacked-value"},
        headers={"X-CSRF-Token": tenant_b["csrf_token"]},
    )
    assert rotate_resp.status_code == 404

    list_resp = await tenant_b_client.get("/api/integrations/credentials")
    assert list_resp.status_code == 200
    assert all(c["id"] != credential_id for c in list_resp.json())


async def test_cannot_switch_to_another_tenants_membership(client, db):
    tenant_a = await _new_tenant_owner(client, db, org="Switch A Co", email="ownerA@switch-a.example")
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": tenant_a["csrf_token"]})

    tenant_b = await _new_tenant_owner(client, db, org="Switch B Co", email="ownerB@switch-b.example")

    switch_resp = await client.post(
        "/api/auth/tenant-switch",
        json={"membership_id": tenant_a["membership_id"]},
        headers={"X-CSRF-Token": tenant_b["csrf_token"]},
    )
    assert switch_resp.status_code == 403


async def test_users_list_scoped_to_own_tenant(client, db):
    tenant_a = await _new_tenant_owner(client, db, org="Scope A Co", email="ownerA@scope-a.example")
    users_a = await client.get("/api/users")
    assert users_a.status_code == 200
    emails_a = {u["email"] for u in users_a.json()}
    assert emails_a == {"ownerA@scope-a.example"}
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": tenant_a["csrf_token"]})

    await _new_tenant_owner(client, db, org="Scope B Co", email="ownerB@scope-b.example")
    users_b = await client.get("/api/users")
    emails_b = {u["email"] for u in users_b.json()}
    assert emails_b == {"ownerB@scope-b.example"}
    assert "ownerA@scope-a.example" not in emails_b


async def test_credential_tenant_id_is_never_taken_from_client_body(client, db):
    """Even if a client sends a `tenant_id` field, the created row's tenant
    must be the server-derived one from the session, never the client's."""
    tenant_a = await _new_tenant_owner(client, db, org="Inject A Co", email="ownerA@inject-a.example")
    foreign_tenant_id = str(uuid.uuid4())

    resp = await client.post(
        "/api/integrations/credentials",
        json={
            "provider_key": "mock_identity",
            "label": "Injection attempt",
            "secret": "value",
            "tenant_id": foreign_tenant_id,  # not part of the schema — must be ignored
        },
        headers={"X-CSRF-Token": tenant_a["csrf_token"]},
    )
    assert resp.status_code == 200

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, uuid.UUID(tenant_a["tenant_id"]))
        from modules.credential_vault.models import IntegrationCredential

        cred = (
            await session.execute(
                select(IntegrationCredential).where(IntegrationCredential.id == uuid.UUID(resp.json()["id"]))
            )
        ).scalar_one()
        assert str(cred.tenant_id) == tenant_a["tenant_id"]
        assert str(cred.tenant_id) != foreign_tenant_id


async def test_rls_blocks_membership_read_without_any_session_context(db):
    """Direct DB-layer proof: with FORCE ROW LEVEL SECURITY and no
    app.current_tenant_id / app.current_user_id set at all on this
    connection, membership rows are invisible even though they exist."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Membership))
        assert result.scalars().all() == []


async def test_rls_rejects_cross_tenant_membership_insert(db):
    """A membership INSERT whose tenant_id doesn't match the session's
    app.current_tenant_id is rejected by the database itself (WITH CHECK),
    not just by application code."""
    async with AsyncSessionLocal() as session:
        tenant_a_id = uuid.uuid4()
        tenant_b_id = uuid.uuid4()
        from modules.tenancy.models import Tenant

        slug_a = f"rls-a-{tenant_a_id.hex[:8]}"
        slug_b = f"rls-b-{tenant_b_id.hex[:8]}"
        session.add(Tenant(id=tenant_a_id, name="RLS A", slug=slug_a, status="active"))
        session.add(Tenant(id=tenant_b_id, name="RLS B", slug=slug_b, status="active"))
        await session.commit()

        role = (await session.execute(select(Role).where(Role.name == "tenant_owner"))).scalar_one()

        await set_tenant_context(session, tenant_a_id)
        with pytest.raises(Exception):
            await session.execute(
                text(
                    "INSERT INTO memberships "
                    "(id, tenant_id, user_id, role_id, status, created_at, updated_at) "
                    "VALUES (:id, :tenant_id, :user_id, :role_id, 'active', now(), now())"
                ),
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant_b_id,  # mismatched — violates WITH CHECK for tenant_a's session
                    "user_id": uuid.uuid4(),
                    "role_id": role.id,
                },
            )
            await session.commit()
