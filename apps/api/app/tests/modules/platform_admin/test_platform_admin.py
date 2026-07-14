from app.tests.conftest import login
from app.tests.factories import create_platform_admin


def _login_platform_admin(client, db_session, email="platform-admin@test.internal", password="PlatformAdmin!2345"):
    create_platform_admin(db_session, email=email, password=password)
    return login(client, email, password)


def test_platform_admin_can_create_tenant_with_owner(client, db_session, fake_email):
    _login_platform_admin(client, db_session)

    response = client.post(
        "/api/platform/tenants",
        json={
            "name": "New Client Co",
            "plan_code": "starter",
            "owner_email": "owner@newclient.internal",
            "owner_first_name": "New",
            "owner_last_name": "Owner",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "active"
    assert fake_email.last_token_for("owner@newclient.internal")  # welcome/set-password email was sent


def test_platform_admin_can_suspend_and_restore_tenant(client, db_session):
    _login_platform_admin(client, db_session)
    create_response = client.post(
        "/api/platform/tenants",
        json={
            "name": "Suspend Co",
            "plan_code": "starter",
            "owner_email": "owner@suspendco.internal",
            "owner_first_name": "S",
            "owner_last_name": "Owner",
        },
    )
    tenant_id = create_response.json()["id"]

    suspend_response = client.post(f"/api/platform/tenants/{tenant_id}/status", json={"status": "suspended"})
    assert suspend_response.status_code == 200
    assert suspend_response.json()["status"] == "suspended"

    restore_response = client.post(f"/api/platform/tenants/{tenant_id}/status", json={"status": "active"})
    assert restore_response.status_code == 200
    assert restore_response.json()["status"] == "active"


def test_platform_admin_can_assign_plan(client, db_session):
    _login_platform_admin(client, db_session)
    create_response = client.post(
        "/api/platform/tenants",
        json={
            "name": "Plan Co",
            "plan_code": "starter",
            "owner_email": "owner@planco.internal",
            "owner_first_name": "P",
            "owner_last_name": "Owner",
        },
    )
    tenant_id = create_response.json()["id"]

    assign_response = client.post(f"/api/platform/tenants/{tenant_id}/plan", json={"plan_code": "professional"})
    assert assign_response.status_code == 200

    entitlements = client.get(f"/api/platform/tenants/{tenant_id}/entitlements").json()
    assert entitlements["plan_code"] == "professional"
    assert entitlements["modules"]["document_collection"] is True


def test_platform_roles_stay_separate_from_tenant_roles(client, db_session):
    """A tenant Administrator, however privileged within their tenant,
    must never be able to reach platform-admin-only endpoints."""
    from app.tests.factories import add_member, create_tenant_with_owner

    tenant, _owner = create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    add_member(db_session, tenant=tenant, email="admin@test.internal", password="AdminPass!2345", role_name="Administrator")

    login(client, "admin@test.internal", "AdminPass!2345")
    response = client.get("/api/platform/tenants")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "platform_admin_required"


def test_tenant_list_only_visible_to_platform_admin(client, db_session):
    from app.tests.factories import create_tenant_with_owner

    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    response = client.get("/api/platform/tenants")

    assert response.status_code == 403
