from app.models.audit import AuditLog
from tests.factories import login, make_platform_admin, make_tenant_with_owner


def test_plan_crud(client, db_session):
    admin = make_platform_admin(db_session)
    csrf = login(client, admin.email)

    create_resp = client.post(
        "/api/platform/plans",
        json={"code": "starter", "name": "Starter", "price_cents": 4900, "currency": "AED"},
        headers={"X-CSRF-Token": csrf},
    )
    assert create_resp.status_code == 201
    plan = create_resp.json()
    assert plan["is_active"] is True

    duplicate_resp = client.post(
        "/api/platform/plans",
        json={"code": "starter", "name": "Starter Again", "price_cents": 100, "currency": "AED"},
        headers={"X-CSRF-Token": csrf},
    )
    assert duplicate_resp.status_code == 409

    update_resp = client.patch(
        f"/api/platform/plans/{plan['id']}",
        json={"is_active": False},
        headers={"X-CSRF-Token": csrf},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["is_active"] is False

    list_resp = client.get("/api/platform/plans")
    assert any(p["code"] == "starter" for p in list_resp.json())


def test_assign_subscription_is_audited(client, db_session):
    admin = make_platform_admin(db_session)
    tenant, _owner = make_tenant_with_owner(db_session)
    csrf = login(client, admin.email)

    plan_resp = client.post(
        "/api/platform/plans",
        json={"code": "growth-test", "name": "Growth", "price_cents": 9900, "currency": "AED"},
        headers={"X-CSRF-Token": csrf},
    )
    plan_id = plan_resp.json()["id"]

    assign_resp = client.post(
        f"/api/platform/tenants/{tenant.id}/subscription",
        json={"plan_id": plan_id, "status": "active"},
        headers={"X-CSRF-Token": csrf},
    )
    assert assign_resp.status_code == 200
    body = assign_resp.json()
    assert body["plan_id"] == plan_id
    assert body["status"] == "active"

    get_resp = client.get(f"/api/platform/tenants/{tenant.id}/subscription")
    assert get_resp.status_code == 200
    assert get_resp.json()["plan_id"] == plan_id

    audit_entries = (
        db_session.query(AuditLog)
        .filter_by(tenant_id=tenant.id, event_type="super_admin.subscription.changed")
        .all()
    )
    assert len(audit_entries) == 1
    metadata = audit_entries[0].event_metadata
    assert metadata["to_plan"] == "growth-test"
    assert metadata["to_status"] == "active"
    # TenantService.create_tenant_with_owner doesn't create a subscription
    # itself (only app.seed.py does, for the demo tenant) - a freshly
    # created test tenant has none until this call.
    assert metadata["from_plan"] is None
    assert metadata["from_status"] is None


def test_assign_subscription_rejects_unknown_plan(client, db_session):
    admin = make_platform_admin(db_session)
    tenant, _owner = make_tenant_with_owner(db_session)
    csrf = login(client, admin.email)

    resp = client.post(
        f"/api/platform/tenants/{tenant.id}/subscription",
        json={"plan_id": "00000000-0000-0000-0000-000000000000", "status": "active"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422


def test_assign_subscription_rejects_unknown_status(client, db_session):
    admin = make_platform_admin(db_session)
    tenant, _owner = make_tenant_with_owner(db_session)
    csrf = login(client, admin.email)

    plan_resp = client.post(
        "/api/platform/plans",
        json={"code": "bad-status-test", "name": "Plan", "price_cents": 100, "currency": "AED"},
        headers={"X-CSRF-Token": csrf},
    )
    plan_id = plan_resp.json()["id"]

    resp = client.post(
        f"/api/platform/tenants/{tenant.id}/subscription",
        json={"plan_id": plan_id, "status": "not_a_real_status"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422


def test_platform_overview_aggregates_across_tenants(client, db_session):
    admin = make_platform_admin(db_session)
    tenant_a, owner_a = make_tenant_with_owner(db_session)
    tenant_b, owner_b = make_tenant_with_owner(db_session)

    csrf_a = login(client, owner_a.email)
    client.post(
        "/api/tenants/me/leads",
        json={"first_name": "LeadA"},
        headers={"X-Tenant-Id": str(tenant_a.id), "X-CSRF-Token": csrf_a},
    )
    csrf_b = login(client, owner_b.email)
    client.post(
        "/api/tenants/me/leads",
        json={"first_name": "LeadB1"},
        headers={"X-Tenant-Id": str(tenant_b.id), "X-CSRF-Token": csrf_b},
    )
    client.post(
        "/api/tenants/me/leads",
        json={"first_name": "LeadB2"},
        headers={"X-Tenant-Id": str(tenant_b.id), "X-CSRF-Token": csrf_b},
    )

    login(client, admin.email)
    resp = client.get("/api/platform/overview")
    assert resp.status_code == 200
    overview = resp.json()

    assert overview["total_tenants"] >= 2
    assert overview["total_leads"] >= 3
    status_counts = {s["status"]: s["count"] for s in overview["tenants_by_status"]}
    assert status_counts.get("active", 0) >= 2


def test_platform_routes_require_super_admin(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    login(client, owner.email)

    assert client.get("/api/platform/plans").status_code == 403
    assert client.get("/api/platform/overview").status_code == 403
    assert client.get(f"/api/platform/tenants/{tenant.id}/subscription").status_code == 403
