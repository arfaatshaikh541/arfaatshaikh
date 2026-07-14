from app.tests.conftest import login
from app.tests.factories import create_tenant_with_owner


def test_starter_plan_does_not_include_booking_module(client, db_session):
    create_tenant_with_owner(db_session, plan_code="starter", owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    response = client.get("/api/me/entitlements")

    assert response.status_code == 200
    modules = response.json()["modules"]
    assert modules.get("lead_capture") is True
    assert modules.get("crm") is True
    assert "booking" not in modules or modules["booking"] is False


def test_disabled_module_backend_check_rejects_even_without_a_ui(client, db_session):
    """Frontend hiding is a convenience only — `assert_module_enabled` is
    the actual backend mechanism every module route depends on
    (`require_module(...)`), and it must independently reject a disabled
    module regardless of what the UI shows. Exercised directly here since
    Milestone 1 has no real booking route yet to call over HTTP — from
    Milestone 4 onward this same assertion is what `require_module`
    enforces on every request to a booking endpoint."""
    import pytest

    from app.core.errors import ModuleNotEnabledError
    from app.modules.entitlements import service as entitlements_service

    tenant, _owner = create_tenant_with_owner(
        db_session, plan_code="starter", owner_email="owner@test.internal", owner_password="OwnerPass!2345"
    )
    login(client, "owner@test.internal", "OwnerPass!2345")

    with pytest.raises(ModuleNotEnabledError):
        entitlements_service.assert_module_enabled(db_session, tenant.id, "booking")


def test_plan_upgrade_unlocks_module_without_losing_existing_data(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session, plan_code="starter", owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")
    client.patch("/api/tenant/settings", json={"currency": "USD"})

    before = client.get("/api/me/entitlements").json()
    assert not before["modules"].get("booking")

    from app.modules.subscriptions import service as subscriptions_service
    subscriptions_service.assign_plan(db_session, tenant_id=tenant.id, plan_code="growth", changed_by=None)
    db_session.commit()

    after = client.get("/api/me/entitlements").json()
    assert after["modules"]["booking"] is True
    assert after["plan_code"] == "growth"

    settings_after = client.get("/api/tenant/settings").json()
    assert settings_after["currency"] == "USD"  # existing data preserved across the plan change


def test_downgrade_preserves_data_but_removes_module_access(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session, plan_code="growth", owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    before = client.get("/api/me/entitlements").json()
    assert before["modules"]["booking"] is True

    from app.modules.subscriptions import service as subscriptions_service
    subscriptions_service.assign_plan(db_session, tenant_id=tenant.id, plan_code="starter", changed_by=None)
    db_session.commit()

    after = client.get("/api/me/entitlements").json()
    assert not after["modules"].get("booking")
    # The tenant, its users, and settings all still exist.
    assert client.get("/api/tenant/settings").status_code == 200
    assert client.get("/api/tenant/users").status_code == 200


def test_feature_override_grants_module_not_in_plan(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session, plan_code="starter", owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    before = client.get("/api/me/entitlements").json()
    assert not before["modules"].get("whatsapp")

    from app.modules.entitlements import service as entitlements_service
    entitlements_service.grant_feature_override(
        db_session, tenant_id=tenant.id, feature_code="whatsapp", config={"enabled": True}, granted_by=None
    )
    db_session.commit()

    after = client.get("/api/me/entitlements").json()
    assert after["modules"]["whatsapp"] is True


def test_add_on_grant_unlocks_module(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session, plan_code="starter", owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    from app.modules.subscriptions import service as subscriptions_service
    subscriptions_service.grant_add_on(db_session, tenant_id=tenant.id, add_on_code="whatsapp_addon", granted_by=None)
    db_session.commit()

    after = client.get("/api/me/entitlements").json()
    assert after["modules"]["whatsapp"] is True


def test_usage_limit_blocks_invitation_beyond_plan_seat_limit(client, db_session):
    """Starter plan seats limit is 5; the tenant owner already occupies
    one seat, so 4 more invitations should succeed and the 5th should be
    rejected."""
    tenant, _owner = create_tenant_with_owner(db_session, plan_code="starter", owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    from app.modules.entitlements import service as entitlements_service
    entitlements_service.increment_usage_unchecked(db_session, tenant.id, metric_code="users", amount=1)
    db_session.commit()

    roles = {r["name"]: r["id"] for r in client.get("/api/tenant/roles").json()}
    role_id = roles["Sales Agent"]

    responses = []
    for i in range(5):
        responses.append(
            client.post("/api/tenant/users/invitations", json={"email": f"agent{i}@test.internal", "role_id": role_id})
        )

    assert [r.status_code for r in responses[:4]] == [202, 202, 202, 202]
    assert responses[4].status_code == 403
    assert responses[4].json()["error"]["code"] == "usage_limit_exceeded"


def test_usage_limit_resolves_unlimited_for_enterprise_plan(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session, plan_code="enterprise", owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    roles = {r["name"]: r["id"] for r in client.get("/api/tenant/roles").json()}
    role_id = roles["Sales Agent"]

    for i in range(10):
        response = client.post("/api/tenant/users/invitations", json={"email": f"agent{i}@test.internal", "role_id": role_id})
        assert response.status_code == 202, response.text
