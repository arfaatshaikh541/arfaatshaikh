"""Milestone 10: platform-wide rate limiting and double-submit CSRF
protection — both implemented as router-level dependencies in
`app/dependencies/security.py`, on top of (not instead of) the
tighter, action-specific login throttles already covered by
`app/tests/modules/identity/test_auth.py`.
"""
import app.dependencies.security as security_module
from app.tests.conftest import login
from app.tests.factories import create_capture_token, create_tenant_with_owner

# --- CSRF protection -------------------------------------------------


def test_mutating_request_missing_csrf_header_is_rejected(client, db_session):
    """Simulates a forged cross-site request: it rides on the victim's
    ambient session cookie (the browser attaches that automatically)
    but never read the CSRF cookie's value, so it cannot echo it as a
    header — exactly the case double-submit protection exists to catch.
    """
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")
    assert "X-CSRF-Token" in client.headers  # the test client auto-synced it, like a real frontend would

    del client.headers["X-CSRF-Token"]  # ...but this forged request never did

    response = client.post("/api/auth/logout")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_token_invalid"
    # The session must still be valid — the rejected logout never ran.
    assert client.get("/api/auth/me").status_code == 200


def test_mutating_request_wrong_csrf_header_is_rejected(client, db_session):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    response = client.post("/api/auth/logout", headers={"X-CSRF-Token": "not-the-real-token"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_token_invalid"


def test_mutating_request_with_matching_csrf_header_succeeds(client, db_session):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    response = client.post("/api/auth/logout")

    assert response.status_code == 204


def test_safe_methods_are_never_csrf_checked(client, db_session):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")
    del client.headers["X-CSRF-Token"]

    response = client.get("/api/auth/me")

    assert response.status_code == 200


def test_csrf_check_is_skipped_when_no_session_cookie_present(client, db_session):
    """An anonymous visitor has never logged in, so there is nothing to
    forge a session out of — the public, unauthenticated capture route
    must keep working with no CSRF header at all."""
    tenant, _owner = create_tenant_with_owner(db_session)
    token = create_capture_token(db_session, tenant.id)

    response = client.post(
        f"/api/public/capture/{token}/enquiry",
        json={"first_name": "Ahmed", "last_name": "Khalid", "email": "ahmed@testclient.internal", "consent_given": True},
    )

    assert response.status_code == 201


def test_public_route_ignores_csrf_even_with_an_unrelated_ambient_session_cookie(client, db_session):
    """A staff member logged into the tenant admin, testing the public
    enquiry form in the same browser, must not get a false-positive 403
    — the public routers are unconditionally exempt from the CSRF
    check, not just exempt-when-no-cookie, precisely to avoid this."""
    tenant, _owner = create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    token = create_capture_token(db_session, tenant.id)
    login(client, "owner@test.internal", "OwnerPass!2345")
    del client.headers["X-CSRF-Token"]

    response = client.post(
        f"/api/public/capture/{token}/enquiry",
        json={"first_name": "Sara", "last_name": "Ali", "email": "sara@testclient.internal", "consent_given": True},
    )

    assert response.status_code == 201


# --- Global rate limiting ---------------------------------------------


def test_global_rate_limit_trips_after_max_attempts(client, db_session, monkeypatch):
    monkeypatch.setattr(security_module.settings, "global_rate_limit_max_attempts", 3)
    monkeypatch.setattr(security_module.settings, "global_rate_limit_window_seconds", 60)

    for _ in range(3):
        response = client.post("/api/public/capture/does-not-exist/enquiry", json={"first_name": "X"})
        assert response.status_code == 404

    limited_response = client.post("/api/public/capture/does-not-exist/enquiry", json={"first_name": "X"})

    assert limited_response.status_code == 429
    assert limited_response.json()["error"]["code"] == "rate_limited"


def test_global_rate_limit_can_be_disabled(client, db_session, monkeypatch):
    monkeypatch.setattr(security_module.settings, "global_rate_limit_max_attempts", 1)
    monkeypatch.setattr(security_module.settings, "global_rate_limit_enabled", False)

    for _ in range(5):
        response = client.post("/api/public/capture/does-not-exist/enquiry", json={"first_name": "X"})
        assert response.status_code == 404
