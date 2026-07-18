import pytest

from tests.helpers import login, onboard_verified_owner

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_executive_viewer_cannot_manage_users(client, db, sent_emails):
    """Executive Viewer only has reporting/view permissions — verifies the
    default role-permission mapping actually withholds `users.manage`."""
    await onboard_verified_owner(
        client, db, org_name="RBAC Co", full_name="Owner",
        email="owner@rbac-co.example", password="Owner-Pass1!",
    )
    owner_login = await login(client, "owner@rbac-co.example", "Owner-Pass1!")
    owner_csrf = owner_login.json()["csrf_token"]
    tenant_id = owner_login.json()["memberships"][0]["tenant_id"]

    import uuid

    from db.session import AsyncSessionLocal, set_tenant_context

    sent_emails.clear()  # discard the onboarding verification email
    invite_resp = await client.post(
        "/api/users/invitations",
        json={"email": "exec@rbac-co.example", "role_name": "executive_viewer"},
        headers={"X-CSRF-Token": owner_csrf},
    )
    assert invite_resp.status_code == 200

    assert len(sent_emails) == 1  # Milestone 28: real invitation email, not a log line
    assert sent_emails[0]["To"] == "exec@rbac-co.example"
    assert "http://localhost:3000/accept-invitation?token=" in sent_emails[0].get_content()

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, uuid.UUID(tenant_id))
        from sqlalchemy import select

        from modules.permissions.models import Invitation

        invitation = (
            await session.execute(
                select(Invitation).where(Invitation.email == "exec@rbac-co.example")
            )
        ).scalar_one()
        # Re-issue a known raw token since the real one was only "emailed".
        from core.security import generate_opaque_token, hash_token

        raw_token = generate_opaque_token()
        invitation.token_hash = hash_token(raw_token)
        await session.commit()

    await client.post("/api/auth/logout", headers={"X-CSRF-Token": owner_csrf})

    accept_resp = await client.post(
        "/api/auth/accept-invitation",
        json={"token": raw_token, "full_name": "Exec Viewer", "password": "Exec-Viewer-Pass1!"},
    )
    assert accept_resp.status_code == 200, accept_resp.text
    exec_csrf = accept_resp.json()["csrf_token"]

    denied = await client.get("/api/users")
    assert denied.status_code == 403
    assert denied.json()["error"]["details"]["required_permission"] == "users.manage"

    invite_denied = await client.post(
        "/api/users/invitations",
        json={"email": "another@rbac-co.example", "role_name": "security_analyst"},
        headers={"X-CSRF-Token": exec_csrf},
    )
    assert invite_denied.status_code == 403

    reports_allowed = await client.get("/api/subscriptions/entitlements")
    assert reports_allowed.status_code == 200


async def test_tenant_owner_has_full_tenant_permissions(client, db):
    await onboard_verified_owner(
        client, db, org_name="Owner Perms Co", full_name="Owner", email="owner@owner-perms.example",
        password="Owner-Pass1!",
    )
    await login(client, "owner@owner-perms.example", "Owner-Pass1!")

    assert (await client.get("/api/users")).status_code == 200
    assert (await client.get("/api/roles")).status_code == 200
    assert (await client.get("/api/tenancy/current")).status_code == 200
