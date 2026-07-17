import pytest
from app.modules.identity.models import User
from app.modules.permissions.models import PlatformRoleAssignment, Role
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.helpers import csrf_headers, migrator_asyncpg_url, register_verify_login

pytestmark = pytest.mark.asyncio

STRONG_PASSWORD = "CorrectHorse9Battery"


async def _promote_to_platform_super_admin(email: str) -> None:
    """Simulates what an out-of-band platform provisioning process (not a
    public API - there is deliberately no self-service way to become a
    platform user) would do: flip is_platform_user and assign the
    Platform Super Admin role directly against the database, bypassing RLS
    with the migrator role."""
    engine = create_async_engine(migrator_asyncpg_url())
    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        user.is_platform_user = True

        role = (
            await session.execute(
                select(Role).where(Role.name == "Platform Super Admin", Role.tenant_id.is_(None))
            )
        ).scalar_one()
        session.add(PlatformRoleAssignment(user_id=user.id, role_id=role.id))
        await session.commit()
    await engine.dispose()


async def test_non_platform_user_is_denied_platform_endpoints(client, smtp_capture):
    await register_verify_login(
        client,
        smtp_capture,
        email="regular-user@example.com",
        password=STRONG_PASSWORD,
        full_name="Regular User",
    )
    resp = await client.get("/platform/tenants")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "permission_denied"


async def test_platform_super_admin_can_list_tenants_across_the_whole_platform(
    client, client_factory, smtp_capture
):
    await register_verify_login(
        client,
        smtp_capture,
        email="tenant-owner-x@example.com",
        password=STRONG_PASSWORD,
        full_name="Owner X",
    )
    await client.post(
        "/tenants", json={"name": "Visible To Platform Co"}, headers=csrf_headers(client)
    )

    platform_client = client_factory()
    await register_verify_login(
        platform_client,
        smtp_capture,
        email="platform-tester@example.com",
        password=STRONG_PASSWORD,
        full_name="Platform Tester",
    )
    await _promote_to_platform_super_admin("platform-tester@example.com")

    resp = await platform_client.get("/platform/tenants")
    assert resp.status_code == 200
    names = {t["name"] for t in resp.json()}
    assert "Visible To Platform Co" in names


async def test_support_access_grant_lifecycle_is_audited(client, client_factory, smtp_capture):
    await register_verify_login(
        client,
        smtp_capture,
        email="tenant-owner-y@example.com",
        password=STRONG_PASSWORD,
        full_name="Owner Y",
    )
    tenant_resp = await client.post(
        "/tenants", json={"name": "Support Target Co"}, headers=csrf_headers(client)
    )
    tenant_id = tenant_resp.json()["id"]

    platform_client = client_factory()
    await register_verify_login(
        platform_client,
        smtp_capture,
        email="support-eng@example.com",
        password=STRONG_PASSWORD,
        full_name="Support Engineer",
    )
    await _promote_to_platform_super_admin("support-eng@example.com")

    session_resp = await platform_client.get("/auth/session")
    platform_user_id = session_resp.json()["user"]["id"]

    grant_resp = await platform_client.post(
        "/platform/support-access-grants",
        json={
            "tenant_id": tenant_id,
            "platform_user_id": platform_user_id,
            "reason": "Investigating a customer-reported export bug",
            "duration_hours": 4,
        },
        headers=csrf_headers(platform_client),
    )
    assert grant_resp.status_code == 200, grant_resp.text
    grant = grant_resp.json()
    assert grant["revoked_at"] is None

    audit_resp = await platform_client.get("/platform/audit-logs")
    assert audit_resp.status_code == 200
    actions = [a["action"] for a in audit_resp.json()]
    assert "support_access.granted" in actions

    revoke_resp = await platform_client.post(
        f"/platform/support-access-grants/{grant['id']}/revoke",
        headers=csrf_headers(platform_client),
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["revoked_at"] is not None

    audit_resp_after = await platform_client.get("/platform/audit-logs")
    actions_after = [a["action"] for a in audit_resp_after.json()]
    assert "support_access.revoked" in actions_after

    # The tenant itself can see, in its own audit log, that platform support
    # accessed its data - support access is not a silent backdoor.
    tenant_audit = await client.get("/audit/logs")
    tenant_actions = [a["action"] for a in tenant_audit.json()]
    assert "support_access.granted_by_platform" in tenant_actions


async def test_revoking_an_already_revoked_grant_is_rejected(client, client_factory, smtp_capture):
    await register_verify_login(
        client,
        smtp_capture,
        email="tenant-owner-z@example.com",
        password=STRONG_PASSWORD,
        full_name="Owner Z",
    )
    tenant_resp = await client.post(
        "/tenants", json={"name": "Support Target Two"}, headers=csrf_headers(client)
    )

    platform_client = client_factory()
    await register_verify_login(
        platform_client,
        smtp_capture,
        email="support-eng-2@example.com",
        password=STRONG_PASSWORD,
        full_name="Support Engineer Two",
    )
    await _promote_to_platform_super_admin("support-eng-2@example.com")
    platform_user_id = (await platform_client.get("/auth/session")).json()["user"]["id"]

    grant_resp = await platform_client.post(
        "/platform/support-access-grants",
        json={
            "tenant_id": tenant_resp.json()["id"],
            "platform_user_id": platform_user_id,
            "reason": "Second grant test",
            "duration_hours": 2,
        },
        headers=csrf_headers(platform_client),
    )
    grant_id = grant_resp.json()["id"]

    first_revoke = await platform_client.post(
        f"/platform/support-access-grants/{grant_id}/revoke", headers=csrf_headers(platform_client)
    )
    assert first_revoke.status_code == 200

    second_revoke = await platform_client.post(
        f"/platform/support-access-grants/{grant_id}/revoke", headers=csrf_headers(platform_client)
    )
    assert second_revoke.status_code == 409
