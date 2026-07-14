from tests.factories import login, make_tenant_with_owner


def test_update_settings_happy_path(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    resp = client.patch(
        "/api/tenants/me/settings",
        json={
            "brand_primary_color": "#123ABC",
            "contact_email": "hello@factory.testmail.dev",
            "business_hours": {"mon": {"open": "09:00", "close": "18:00"}},
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["brand_primary_color"] == "#123ABC"
    assert body["business_hours"]["mon"]["open"] == "09:00"


def test_update_settings_rejects_invalid_hex_color(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    resp = client.patch(
        "/api/tenants/me/settings",
        json={"brand_primary_color": "not-a-color"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422


def test_default_currency_and_timezone(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    login(client, owner.email)
    resp = client.get("/api/tenants/me", headers={"X-Tenant-Id": str(tenant.id)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["currency"] == "AED"
    assert body["timezone"] == "Asia/Dubai"


def test_complete_onboarding_sets_timestamp_once(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    headers = {"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf}

    get_resp = client.get("/api/tenants/me/settings", headers=headers)
    assert get_resp.json()["onboarding_completed_at"] is None

    first = client.post("/api/tenants/me/onboarding/complete", headers=headers)
    assert first.status_code == 200
    completed_at = first.json()["onboarding_completed_at"]
    assert completed_at is not None

    second = client.post("/api/tenants/me/onboarding/complete", headers=headers)
    assert second.status_code == 200
    assert second.json()["onboarding_completed_at"] == completed_at


def test_duplicate_tenant_slug_rejected(db_session):
    from tests.factories import make_tenant_with_owner as make

    tenant, _owner = make(db_session, slug="dupe-slug-co")
    import pytest

    from app.services.errors import ConflictError
    from app.services.tenant_service import TenantService

    with pytest.raises(ConflictError):
        TenantService(db_session).create_tenant_with_owner(
            name="Another Co",
            slug="dupe-slug-co",
            legal_name=None,
            timezone="Asia/Dubai",
            currency="AED",
            owner_email="another@factory.testmail.dev",
            owner_first_name="A",
            owner_last_name="B",
            owner_password="Passw0rd!12345",
        )
