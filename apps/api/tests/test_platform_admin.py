
import pytest
from sqlalchemy import select

from core.security import hash_password
from modules.identity.models import User
from modules.permissions.models import Role
from tests.helpers import login, onboard_verified_owner

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _create_platform_admin(db, email: str, role_name: str = "platform_super_admin") -> None:
    role = (
        await db.execute(select(Role).where(Role.name == role_name, Role.is_platform_role.is_(True)))
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


async def test_login_response_exposes_platform_role_for_a_platform_user(client, db):
    await _create_platform_admin(db, "platform-role-check@gridkeep-platform.example", "platform_auditor")

    resp = await login(client, "platform-role-check@gridkeep-platform.example", "Platform-Pass1!")

    assert resp.status_code == 200
    user = resp.json()["user"]
    assert user["is_platform_user"] is True
    assert user["platform_role_name"] == "platform_auditor"


async def test_login_response_shows_is_platform_user_false_for_a_tenant_user(client, db):
    await onboard_verified_owner(
        client, db, org_name="Not A Platform User Co", full_name="Owner",
        email="owner@not-platform-user.example", password="Owner-Pass1!",
    )

    resp = await login(client, "owner@not-platform-user.example", "Owner-Pass1!")

    assert resp.status_code == 200
    user = resp.json()["user"]
    assert user["is_platform_user"] is False
    assert user["platform_role_name"] is None


async def test_platform_admin_can_list_and_view_tenants(client, db):
    tenant_body = await onboard_verified_owner(
        client, db, org_name="Listed Tenant Co", full_name="Owner",
        email="owner@listed-tenant.example", password="Owner-Pass1!",
    )
    tenant_id = tenant_body["tenant_id"]

    await _create_platform_admin(db, "platform-lister@gridkeep-platform.example")
    platform_login = await login(client, "platform-lister@gridkeep-platform.example", "Platform-Pass1!")
    assert platform_login.status_code == 200

    list_resp = await client.get("/api/platform/tenants")
    assert list_resp.status_code == 200
    tenants = list_resp.json()
    assert any(t["id"] == tenant_id for t in tenants)

    detail_resp = await client.get(f"/api/platform/tenants/{tenant_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["name"] == "Listed Tenant Co"
    assert detail_resp.json()["status"] == "trial"

    missing_resp = await client.get("/api/platform/tenants/00000000-0000-0000-0000-000000000000")
    assert missing_resp.status_code == 404


async def test_platform_admin_can_transition_tenant_status(client, db):
    tenant_body = await onboard_verified_owner(
        client, db, org_name="Status Transition Co", full_name="Owner",
        email="owner@status-transition.example", password="Owner-Pass1!",
    )
    tenant_id = tenant_body["tenant_id"]

    await _create_platform_admin(db, "platform-status@gridkeep-platform.example")
    platform_login = await login(client, "platform-status@gridkeep-platform.example", "Platform-Pass1!")
    platform_csrf = platform_login.json()["csrf_token"]

    resp = await client.post(
        f"/api/platform/tenants/{tenant_id}/status",
        json={"status": "suspended", "reason": "Non-payment for 30 days, per collections policy"},
        headers={"X-CSRF-Token": platform_csrf},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "suspended"


async def test_invalid_tenant_status_transition_is_rejected(client, db):
    tenant_body = await onboard_verified_owner(
        client, db, org_name="Bad Transition Co", full_name="Owner",
        email="owner@bad-transition.example", password="Owner-Pass1!",
    )
    tenant_id = tenant_body["tenant_id"]

    await _create_platform_admin(db, "platform-bad-transition@gridkeep-platform.example")
    platform_login = await login(
        client, "platform-bad-transition@gridkeep-platform.example", "Platform-Pass1!"
    )
    platform_csrf = platform_login.json()["csrf_token"]

    # trial -> read_only is not a defined transition (only active/read_only
    # can reach read_only in this state machine).
    resp = await client.post(
        f"/api/platform/tenants/{tenant_id}/status",
        json={"status": "read_only", "reason": "Attempting an undefined transition on purpose"},
        headers={"X-CSRF-Token": platform_csrf},
    )
    assert resp.status_code == 422


async def test_archived_tenant_status_is_terminal(client, db):
    tenant_body = await onboard_verified_owner(
        client, db, org_name="Terminal Status Co", full_name="Owner",
        email="owner@terminal-status.example", password="Owner-Pass1!",
    )
    tenant_id = tenant_body["tenant_id"]

    await _create_platform_admin(db, "platform-terminal@gridkeep-platform.example")
    platform_login = await login(client, "platform-terminal@gridkeep-platform.example", "Platform-Pass1!")
    platform_csrf = platform_login.json()["csrf_token"]

    archive_resp = await client.post(
        f"/api/platform/tenants/{tenant_id}/status",
        json={"status": "archived", "reason": "Customer requested full account closure"},
        headers={"X-CSRF-Token": platform_csrf},
    )
    assert archive_resp.status_code == 200
    assert archive_resp.json()["status"] == "archived"

    reactivate_resp = await client.post(
        f"/api/platform/tenants/{tenant_id}/status",
        json={"status": "active", "reason": "Attempting to reactivate an archived tenant"},
        headers={"X-CSRF-Token": platform_csrf},
    )
    assert reactivate_resp.status_code == 422


async def test_tenant_status_change_is_audit_logged_and_visible_platform_wide(client, db):
    tenant_body = await onboard_verified_owner(
        client, db, org_name="Audited Status Co", full_name="Owner",
        email="owner@audited-status.example", password="Owner-Pass1!",
    )
    tenant_id = tenant_body["tenant_id"]

    await _create_platform_admin(db, "platform-audited@gridkeep-platform.example")
    platform_login = await login(client, "platform-audited@gridkeep-platform.example", "Platform-Pass1!")
    platform_csrf = platform_login.json()["csrf_token"]

    await client.post(
        f"/api/platform/tenants/{tenant_id}/status",
        json={"status": "suspended", "reason": "Investigating a suspected ToS violation"},
        headers={"X-CSRF-Token": platform_csrf},
    )

    logs_resp = await client.get("/api/platform/audit-logs", params={"tenant_id": tenant_id})
    assert logs_resp.status_code == 200
    logs = logs_resp.json()
    status_change = next(log for log in logs if log["action"] == "platform.tenant_status_changed")
    assert status_change["context"]["from"] == "trial"
    assert status_change["context"]["to"] == "suspended"
    assert status_change["target_id"] == tenant_id


async def test_platform_wide_audit_log_shows_entries_from_multiple_tenants(client, db):
    """The whole point of Milestone 12's widened `audit_logs_select` RLS
    policy: a platform-admin session must see rows across every tenant,
    not just its own or NULL-tenant platform events. This is the test
    that actually exercises that widening, not just the application code
    on top of it."""
    tenant_a = await onboard_verified_owner(
        client, db, org_name="Multi Tenant Audit A Co", full_name="Owner",
        email="owner@multi-audit-a.example", password="Owner-Pass1!",
    )
    tenant_b = await onboard_verified_owner(
        client, db, org_name="Multi Tenant Audit B Co", full_name="Owner",
        email="owner@multi-audit-b.example", password="Owner-Pass1!",
    )

    await _create_platform_admin(db, "platform-multi-audit@gridkeep-platform.example")
    platform_login = await login(client, "platform-multi-audit@gridkeep-platform.example", "Platform-Pass1!")
    platform_csrf = platform_login.json()["csrf_token"]

    for tenant_body in (tenant_a, tenant_b):
        await client.post(
            f"/api/platform/tenants/{tenant_body['tenant_id']}/status",
            json={"status": "suspended", "reason": "Part of a cross-tenant audit-visibility test"},
            headers={"X-CSRF-Token": platform_csrf},
        )

    logs_resp = await client.get(
        "/api/platform/audit-logs", params={"action": "platform.tenant_status_changed", "limit": 200}
    )
    assert logs_resp.status_code == 200
    seen_tenant_ids = {log["tenant_id"] for log in logs_resp.json()}
    assert tenant_a["tenant_id"] in seen_tenant_ids
    assert tenant_b["tenant_id"] in seen_tenant_ids


async def test_platform_auditor_can_view_audit_logs_but_not_manage_tenants(client, db):
    tenant_body = await onboard_verified_owner(
        client, db, org_name="Auditor Scope Co", full_name="Owner",
        email="owner@auditor-scope.example", password="Owner-Pass1!",
    )
    tenant_id = tenant_body["tenant_id"]

    await _create_platform_admin(db, "platform-auditor-only@gridkeep-platform.example", "platform_auditor")
    platform_login = await login(client, "platform-auditor-only@gridkeep-platform.example", "Platform-Pass1!")
    platform_csrf = platform_login.json()["csrf_token"]

    audit_resp = await client.get("/api/platform/audit-logs")
    assert audit_resp.status_code == 200

    manage_resp = await client.post(
        f"/api/platform/tenants/{tenant_id}/status",
        json={"status": "suspended", "reason": "An auditor should not be able to do this"},
        headers={"X-CSRF-Token": platform_csrf},
    )
    assert manage_resp.status_code == 403

    list_resp = await client.get("/api/platform/tenants")
    assert list_resp.status_code == 403


async def test_platform_support_engineer_cannot_view_audit_logs_or_manage_tenants(client, db):
    await _create_platform_admin(
        db, "platform-support-only@gridkeep-platform.example", "platform_support_engineer"
    )
    platform_login = await login(client, "platform-support-only@gridkeep-platform.example", "Platform-Pass1!")
    assert platform_login.status_code == 200

    audit_resp = await client.get("/api/platform/audit-logs")
    assert audit_resp.status_code == 403

    tenants_resp = await client.get("/api/platform/tenants")
    assert tenants_resp.status_code == 403
