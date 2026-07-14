from app.tests.conftest import login
from app.tests.factories import add_member, create_tenant_with_owner


def test_viewer_role_cannot_manage_users(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    add_member(db_session, tenant=tenant, email="viewer@test.internal", password="ViewerPass!2345", role_name="Viewer")

    login(client, "viewer@test.internal", "ViewerPass!2345")
    response = client.get("/api/tenant/users")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_viewer_role_can_view_leads_permission_reflected_in_entitlements(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    add_member(db_session, tenant=tenant, email="viewer@test.internal", password="ViewerPass!2345", role_name="Viewer")

    login(client, "viewer@test.internal", "ViewerPass!2345")
    response = client.get("/api/me/entitlements")

    assert response.status_code == 200
    permissions = response.json()["permissions"]
    assert "leads.view" in permissions
    assert "users.manage" not in permissions
    assert "roles.manage" not in permissions


def test_tenant_role_creation_rejects_platform_permission(client, db_session):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    response = client.post(
        "/api/tenant/roles",
        json={"name": "Rogue Admin", "permission_codes": ["platform.tenants.manage"]},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "platform_permission_not_assignable"


def test_permission_catalog_never_exposes_platform_permissions(client, db_session):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    response = client.get("/api/tenant/roles/permission-catalog")

    assert response.status_code == 200
    codes = response.json().keys()
    assert all(not code.startswith("platform.") for code in codes)


def test_non_platform_admin_cannot_access_platform_routes(client, db_session):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    response = client.get("/api/platform/tenants")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "platform_admin_required"


def test_system_role_permissions_cannot_be_modified(client, db_session):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")
    roles = {r["name"]: r["id"] for r in client.get("/api/tenant/roles").json()}

    response = client.patch(
        f"/api/tenant/roles/{roles['Viewer']}/permissions", json={"permission_codes": ["leads.view", "leads.delete"]}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "system_role_immutable"


def test_cross_role_action_is_rejected_direct_object_reference(client, db_session):
    """A Sales Agent (no leads.delete) must not be able to reach an
    action reserved for a higher-privileged role, even indirectly."""
    tenant, _owner = create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")

    login(client, "agent@test.internal", "AgentPass!2345")
    response = client.get("/api/tenant/roles")

    assert response.status_code == 403
