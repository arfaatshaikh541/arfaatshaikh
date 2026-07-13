"""Authorization tests: for each default role, verify permitted vs
forbidden actions match docs/architecture/authorization-model.md. This is
the guard-rail against a future route missing a require_permission(...)
dependency."""

import pytest

from tests.factories import add_member, login, make_tenant_with_owner


@pytest.fixture()
def tenant_with_all_roles(db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    users = {"owner": owner}
    for slug in ("administrator", "manager", "sales_agent", "support_agent", "viewer"):
        user, _membership = add_member(db_session, tenant, role_slug=slug)
        users[slug] = user
    return tenant, users


SETTINGS_MANAGE_ALLOWED = {"owner", "administrator"}
USERS_MANAGE_ALLOWED = {"owner", "administrator"}
ROLES_MANAGE_ALLOWED = {"owner", "administrator"}


@pytest.mark.parametrize(
    "role_slug", ["owner", "administrator", "manager", "sales_agent", "support_agent", "viewer"]
)
def test_update_tenant_settings_permission(client, db_session, tenant_with_all_roles, role_slug):
    tenant, users = tenant_with_all_roles
    csrf = login(client, users[role_slug].email)
    resp = client.patch(
        "/api/tenants/me/settings",
        json={"contact_phone": "+971500000000"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    if role_slug in SETTINGS_MANAGE_ALLOWED:
        assert resp.status_code == 200, resp.text
    else:
        assert resp.status_code == 403


@pytest.mark.parametrize(
    "role_slug", ["owner", "administrator", "manager", "sales_agent", "support_agent", "viewer"]
)
def test_list_members_permission(client, db_session, tenant_with_all_roles, role_slug):
    tenant, users = tenant_with_all_roles
    login(client, users[role_slug].email)
    resp = client.get("/api/tenants/me/members", headers={"X-Tenant-Id": str(tenant.id)})
    if role_slug in USERS_MANAGE_ALLOWED:
        assert resp.status_code == 200
    else:
        assert resp.status_code == 403


@pytest.mark.parametrize(
    "role_slug", ["owner", "administrator", "manager", "sales_agent", "support_agent", "viewer"]
)
def test_create_role_permission(client, db_session, tenant_with_all_roles, role_slug):
    tenant, users = tenant_with_all_roles
    csrf = login(client, users[role_slug].email)
    resp = client.post(
        "/api/tenants/me/roles",
        json={"name": f"Custom Role {role_slug}", "permission_codes": ["leads.view"]},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    if role_slug in ROLES_MANAGE_ALLOWED:
        assert resp.status_code == 201, resp.text
    else:
        assert resp.status_code == 403


def test_all_roles_can_view_their_own_tenant(client, db_session, tenant_with_all_roles):
    tenant, users = tenant_with_all_roles
    for role_slug, user in users.items():
        login(client, user.email)
        resp = client.get("/api/tenants/me", headers={"X-Tenant-Id": str(tenant.id)})
        assert resp.status_code == 200, f"{role_slug} should be able to view its own tenant"


def test_system_role_permissions_cannot_be_edited(client, db_session, tenant_with_all_roles):
    tenant, users = tenant_with_all_roles
    csrf = login(client, users["owner"].email)

    from app.repositories.role import RoleRepository

    manager_role = RoleRepository(db_session).get_by_slug_for_tenant(tenant.id, "manager")
    resp = client.patch(
        f"/api/tenants/me/roles/{manager_role.id}",
        json={"permission_codes": ["leads.view"]},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422


def test_platform_super_admin_route_rejects_regular_user(client, db_session, tenant_with_all_roles):
    _tenant, users = tenant_with_all_roles
    login(client, users["owner"].email)
    resp = client.get("/api/platform/tenants")
    assert resp.status_code == 403


def test_platform_super_admin_can_list_and_view_tenants_and_it_is_audited(client, db_session):
    from app.core.security import hash_password
    from app.models.audit import AuditLog
    from app.repositories.user import UserRepository

    admin = UserRepository(db_session).create(
        email="admin@factory.testmail.dev",
        hashed_password=hash_password("AdminPassw0rd!123"),
        first_name="Platform",
        last_name="Admin",
        is_platform_super_admin=True,
        email_verified=True,
    )
    db_session.commit()

    tenant, _owner = make_tenant_with_owner(db_session)
    login(client, admin.email, "AdminPassw0rd!123")

    list_resp = client.get("/api/platform/tenants")
    assert list_resp.status_code == 200
    assert any(t["id"] == str(tenant.id) for t in list_resp.json())

    detail_resp = client.get(f"/api/platform/tenants/{tenant.id}")
    assert detail_resp.status_code == 200

    audit_entries = (
        db_session.query(AuditLog)
        .filter_by(tenant_id=tenant.id, event_type="super_admin.tenant.viewed")
        .all()
    )
    assert len(audit_entries) == 1
    assert audit_entries[0].actor_user_id == admin.id
