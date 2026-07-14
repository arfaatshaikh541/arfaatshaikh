from app.core.config import get_settings
from app.repositories.pipeline import PipelineStageRepository
from app.repositories.service import ServiceRepository
from app.repositories.tenant import TenantRepository
from tests.factories import make_tenant_with_owner, unique_slug


def _signup_payload(**overrides: object) -> dict:
    slug = overrides.pop("slug", None) or unique_slug("signup")
    payload = {
        "name": f"Signup Co {slug}",
        "slug": slug,
        "owner_email": f"{slug}@factory.testmail.dev",
        "owner_first_name": "New",
        "owner_last_name": "Owner",
        "owner_password": "SignupPassw0rd!123",
    }
    payload.update(overrides)
    return payload


def test_signup_creates_tenant_and_auto_logs_in(client, db_session):
    payload = _signup_payload()
    resp = client.post("/api/auth/signup", json=payload)
    assert resp.status_code == 201, resp.text
    assert "access_token" in resp.cookies
    assert "refresh_token" in resp.cookies
    assert "csrf_token" in resp.cookies

    body = resp.json()
    assert body["user"]["email"] == payload["owner_email"]
    assert body["user"]["email_verified"] is False
    memberships = body["user"]["memberships"]
    assert len(memberships) == 1
    assert memberships[0]["tenant_slug"] == payload["slug"]
    assert memberships[0]["role"]["slug"] == "owner"

    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == payload["owner_email"]


def test_signup_defaults_match_platform_admin_created_tenant(client, db_session):
    admin_tenant, _owner = make_tenant_with_owner(db_session)

    payload = _signup_payload()
    resp = client.post("/api/auth/signup", json=payload)
    assert resp.status_code == 201, resp.text
    signup_tenant = TenantRepository(db_session).get_by_slug(payload["slug"])
    assert signup_tenant is not None

    admin_stages = {
        s.slug for s in PipelineStageRepository(db_session).list_for_tenant(admin_tenant.id)
    }
    signup_stages = {
        s.slug for s in PipelineStageRepository(db_session).list_for_tenant(signup_tenant.id)
    }
    assert admin_stages == signup_stages
    assert len(signup_stages) > 0

    admin_services = {
        s.name for s in ServiceRepository(db_session).list_for_tenant(admin_tenant.id)
    }
    signup_services = {
        s.name for s in ServiceRepository(db_session).list_for_tenant(signup_tenant.id)
    }
    assert admin_services == signup_services
    assert len(signup_services) > 0

    settings = TenantRepository(db_session).get_settings(signup_tenant.id)
    assert settings is not None
    assert settings.onboarding_completed_at is None


def test_signup_sends_verification_email(client, db_session, monkeypatch):
    import app.services.auth_service as auth_service_module

    captured: dict[str, str] = {}

    def fake_send(*, to: str, verify_url: str) -> None:
        captured["to"] = to
        captured["url"] = verify_url

    monkeypatch.setattr(auth_service_module, "send_verification_email", fake_send)

    payload = _signup_payload()
    resp = client.post("/api/auth/signup", json=payload)
    assert resp.status_code == 201, resp.text
    assert captured["to"] == payload["owner_email"]
    assert "token=" in captured["url"]


def test_signup_duplicate_slug_rejected(client, db_session):
    payload = _signup_payload()
    first = client.post("/api/auth/signup", json=payload)
    assert first.status_code == 201, first.text

    second = _signup_payload(slug=payload["slug"])
    resp = client.post("/api/auth/signup", json=second)
    assert resp.status_code == 409


def test_signup_rate_limited_by_ip(client, db_session):
    settings = get_settings()
    max_attempts = settings.signup_rate_limit_attempts

    for _ in range(max_attempts):
        resp = client.post("/api/auth/signup", json=_signup_payload())
        assert resp.status_code == 201, resp.text

    over_limit = client.post("/api/auth/signup", json=_signup_payload())
    assert over_limit.status_code == 429


def test_signup_rejects_invalid_email(client, db_session):
    payload = _signup_payload(owner_email="not-an-email")
    resp = client.post("/api/auth/signup", json=payload)
    assert resp.status_code == 422


def test_signup_rejects_short_password(client, db_session):
    payload = _signup_payload(owner_password="short")
    resp = client.post("/api/auth/signup", json=payload)
    assert resp.status_code == 422


def test_signup_rejects_invalid_slug(client, db_session):
    payload = _signup_payload(slug="Not A Valid Slug!")
    resp = client.post("/api/auth/signup", json=payload)
    assert resp.status_code == 422
