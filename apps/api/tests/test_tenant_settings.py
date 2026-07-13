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
