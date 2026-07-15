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


# --- Milestone 9: catalog management -------------------------------------


def test_platform_admin_can_create_and_update_module(client, db_session):
    _login_platform_admin(client, db_session)

    create_response = client.post(
        "/api/platform/modules", json={"code": "compliance", "name": "Compliance", "description": "Regulatory filings."}
    )
    assert create_response.status_code == 201
    module = create_response.json()
    assert module["code"] == "compliance"

    update_response = client.put(
        f"/api/platform/modules/{module['id']}", json={"name": "Compliance Tracking", "description": "Updated."}
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Compliance Tracking"
    assert update_response.json()["code"] == "compliance"  # code is immutable


def test_duplicate_module_code_is_rejected(client, db_session):
    _login_platform_admin(client, db_session)

    client.post("/api/platform/modules", json={"code": "dup_mod", "name": "First", "description": ""})
    response = client.post("/api/platform/modules", json={"code": "dup_mod", "name": "Second", "description": ""})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "module_code_taken"


def test_platform_admin_can_create_and_update_feature(client, db_session):
    _login_platform_admin(client, db_session)

    module = client.post(
        "/api/platform/modules", json={"code": "compliance2", "name": "Compliance 2", "description": ""}
    ).json()

    create_response = client.post(
        "/api/platform/features",
        json={"module_id": module["id"], "code": "compliance2", "name": "Compliance 2", "feature_type": "boolean"},
    )
    assert create_response.status_code == 201
    feature = create_response.json()
    assert feature["module_code"] == "compliance2"

    limit_feature = client.post(
        "/api/platform/features",
        json={"module_id": module["id"], "code": "filings_per_month", "name": "Filings / month", "feature_type": "limit"},
    ).json()
    assert limit_feature["feature_type"] == "limit"

    update_response = client.put(f"/api/platform/features/{feature['id']}", json={"name": "Compliance access"})
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Compliance access"


def test_duplicate_feature_code_within_module_is_rejected(client, db_session):
    _login_platform_admin(client, db_session)

    module = client.post(
        "/api/platform/modules", json={"code": "compliance3", "name": "Compliance 3", "description": ""}
    ).json()
    client.post(
        "/api/platform/features",
        json={"module_id": module["id"], "code": "dup_feat", "name": "First", "feature_type": "boolean"},
    )
    response = client.post(
        "/api/platform/features",
        json={"module_id": module["id"], "code": "dup_feat", "name": "Second", "feature_type": "boolean"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "feature_code_taken"


def test_platform_admin_can_create_update_and_deactivate_plan(client, db_session):
    _login_platform_admin(client, db_session)

    create_response = client.post(
        "/api/platform/plans", json={"code": "boutique", "name": "Boutique", "description": "A small custom plan.", "is_custom": True}
    )
    assert create_response.status_code == 201
    plan = create_response.json()
    assert plan["is_active"] is True

    update_response = client.put(f"/api/platform/plans/{plan['id']}", json={"name": "Boutique Plus", "description": "Updated."})
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Boutique Plus"

    deactivate_response = client.post(f"/api/platform/plans/{plan['id']}/active", json={"is_active": False})
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    active_plans = client.get("/api/platform/plans").json()
    assert not any(p["code"] == "boutique" for p in active_plans)

    all_plans = client.get("/api/platform/plans?all_plans=true").json()
    assert any(p["code"] == "boutique" for p in all_plans)


def test_platform_admin_can_manage_plan_feature_grants(client, db_session):
    _login_platform_admin(client, db_session)

    plan = client.post(
        "/api/platform/plans", json={"code": "grant_test_plan", "name": "Grant Test Plan", "description": "", "is_custom": True}
    ).json()

    set_boolean_response = client.put(
        f"/api/platform/plans/{plan['id']}/features", json={"feature_code": "crm", "enabled": True}
    )
    assert set_boolean_response.status_code == 200

    set_limit_response = client.put(
        f"/api/platform/plans/{plan['id']}/features", json={"feature_code": "leads", "enabled": True, "limit": 50}
    )
    assert set_limit_response.status_code == 200

    grants = client.get(f"/api/platform/plans/{plan['id']}/features").json()
    grants_by_code = {g["feature_code"]: g for g in grants}
    assert grants_by_code["crm"]["config"] == {"enabled": True}
    assert grants_by_code["leads"]["config"] == {"limit": 50}

    remove_response = client.request(
        "DELETE", f"/api/platform/plans/{plan['id']}/features", params={"feature_code": "leads"}
    )
    assert remove_response.status_code == 200

    grants_after = client.get(f"/api/platform/plans/{plan['id']}/features").json()
    assert "leads" not in {g["feature_code"] for g in grants_after}


def test_platform_admin_can_create_and_update_add_on(client, db_session):
    _login_platform_admin(client, db_session)

    create_response = client.post(
        "/api/platform/add-ons",
        json={"code": "extra_storage", "name": "Extra Storage", "grants": {"features": [{"feature_code": "document_storage_mb", "config": {"limit": 5000}}]}},
    )
    assert create_response.status_code == 201
    add_on = create_response.json()

    update_response = client.put(
        f"/api/platform/add-ons/{add_on['id']}",
        json={"name": "Extra Storage Pack", "grants": {"features": [{"feature_code": "document_storage_mb", "config": {"limit": 10000}}]}},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Extra Storage Pack"
    assert update_response.json()["grants"]["features"][0]["config"]["limit"] == 10000


def test_platform_admin_can_create_and_update_usage_metric(client, db_session):
    _login_platform_admin(client, db_session)

    create_response = client.post(
        "/api/platform/usage-metrics", json={"code": "filings_submitted", "name": "Filings submitted", "unit": "count"}
    )
    assert create_response.status_code == 201

    metric = create_response.json()
    update_response = client.put(
        f"/api/platform/usage-metrics/{metric['id']}", json={"name": "Filings submitted / month", "unit": "count"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Filings submitted / month"


def test_non_platform_admin_cannot_manage_catalog(client, db_session):
    from app.tests.factories import create_tenant_with_owner

    create_tenant_with_owner(db_session, owner_email="owner2@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner2@test.internal", "OwnerPass!2345")

    response = client.post("/api/platform/modules", json={"code": "hacker_mod", "name": "Nope", "description": ""})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "platform_admin_required"
