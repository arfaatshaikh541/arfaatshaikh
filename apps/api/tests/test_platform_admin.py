
import pytest
from sqlalchemy import select

from core.security import hash_password
from modules.identity.models import User
from modules.permissions.models import Role
from tests.helpers import login, onboard_verified_owner

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _create_platform_admin(db, email: str) -> None:
    role = (
        await db.execute(
            select(Role).where(Role.name == "platform_super_admin", Role.is_platform_role.is_(True))
        )
    ).scalar_one()
    db.add(
        User(
            email=email,
            password_hash=hash_password("Platform-Pass1!"),
            full_name="Platform Admin",
            email_verified=True,
            is_platform_user=True,
            platform_role_id=role.id,
        )
    )
    await db.commit()


async def test_platform_admin_can_grant_and_revoke_support_access(client, db):
    tenant_body = await onboard_verified_owner(
        client, db, org_name="Support Target Co", full_name="Owner", email="owner@support-target.example",
        password="Owner-Pass1!",
    )
    tenant_id = tenant_body["tenant_id"]

    await _create_platform_admin(db, "platform-admin@gridkeep-platform.example")
    platform_login = await login(client, "platform-admin@gridkeep-platform.example", "Platform-Pass1!")
    assert platform_login.status_code == 200
    platform_csrf = platform_login.json()["csrf_token"]

    grant_resp = await client.post(
        "/api/platform/support-access-grants",
        json={
            "tenant_id": tenant_id,
            "reason": "Investigating a customer-reported billing issue",
            "duration_hours": 2,
        },
        headers={"X-CSRF-Token": platform_csrf},
    )
    assert grant_resp.status_code == 200, grant_resp.text
    grant = grant_resp.json()
    assert grant["status"] == "active"
    assert grant["tenant_id"] == tenant_id

    revoke_resp = await client.post(
        f"/api/platform/support-access-grants/{grant['id']}/revoke",
        params={"tenant_id": tenant_id},
        headers={"X-CSRF-Token": platform_csrf},
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "revoked"


async def test_non_platform_user_cannot_grant_support_access(client, db):
    await onboard_verified_owner(
        client, db, org_name="Not Platform Co", full_name="Owner", email="owner@not-platform.example",
        password="Owner-Pass1!",
    )
    owner_login = await login(client, "owner@not-platform.example", "Owner-Pass1!")
    csrf = owner_login.json()["csrf_token"]
    tenant_id = owner_login.json()["memberships"][0]["tenant_id"]

    resp = await client.post(
        "/api/platform/support-access-grants",
        json={"tenant_id": tenant_id, "reason": "Trying to self-grant platform access", "duration_hours": 2},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 403


async def test_tenant_can_see_support_access_grants_against_it(client, db):
    tenant_body = await onboard_verified_owner(
        client, db, org_name="Visible Grant Co", full_name="Owner", email="owner@visible-grant.example",
        password="Owner-Pass1!",
    )
    tenant_id = tenant_body["tenant_id"]

    await _create_platform_admin(db, "platform-admin2@gridkeep-platform.example")
    platform_login = await login(client, "platform-admin2@gridkeep-platform.example", "Platform-Pass1!")
    platform_csrf = platform_login.json()["csrf_token"]

    await client.post(
        "/api/platform/support-access-grants",
        json={
            "tenant_id": tenant_id,
            "reason": "Routine access-log audit for compliance review",
            "duration_hours": 1,
        },
        headers={"X-CSRF-Token": platform_csrf},
    )
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": platform_csrf})

    await login(client, "owner@visible-grant.example", "Owner-Pass1!")

    grants_resp = await client.get("/api/support-access-grants")
    assert grants_resp.status_code == 200
    grants = grants_resp.json()
    assert len(grants) == 1
    assert grants[0]["tenant_id"] == tenant_id
