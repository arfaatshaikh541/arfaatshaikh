from tests.factories import DEFAULT_PASSWORD, login, make_tenant_with_owner


def test_login_success_sets_cookies(client, db_session):
    _tenant, owner = make_tenant_with_owner(db_session)
    resp = client.post("/api/auth/login", json={"email": owner.email, "password": DEFAULT_PASSWORD})
    assert resp.status_code == 200
    assert "access_token" in resp.cookies
    assert "refresh_token" in resp.cookies
    assert "csrf_token" in resp.cookies
    body = resp.json()
    assert body["user"]["email"] == owner.email


def test_login_wrong_password_is_generic(client, db_session):
    _tenant, owner = make_tenant_with_owner(db_session)
    resp = client.post("/api/auth/login", json={"email": owner.email, "password": "wrong-password"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password."


def test_login_unknown_email_is_generic(client, db_session):
    resp = client.post(
        "/api/auth/login", json={"email": "nobody@factory.testmail.dev", "password": "whatever123"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password."


def test_login_rate_limited_after_repeated_failures(client, db_session):
    _tenant, owner = make_tenant_with_owner(db_session)
    for _ in range(5):
        client.post("/api/auth/login", json={"email": owner.email, "password": "wrong"})
    resp = client.post("/api/auth/login", json={"email": owner.email, "password": "wrong"})
    assert resp.status_code == 429


def test_me_requires_authentication(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_memberships(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    login(client, owner.email)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    memberships = resp.json()["memberships"]
    assert len(memberships) == 1
    assert memberships[0]["tenant_slug"] == tenant.slug
    assert memberships[0]["role"]["slug"] == "owner"


def test_refresh_rotates_token_and_reuse_is_detected(client, db_session):
    _tenant, owner = make_tenant_with_owner(db_session)
    login(client, owner.email)
    old_refresh_token = client.cookies.get("refresh_token")

    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 200
    new_refresh_token = client.cookies.get("refresh_token")
    assert new_refresh_token != old_refresh_token

    # Present the old (already-rotated) refresh token again: must be rejected
    # and must revoke the whole session family (breach detection).
    client.cookies.set("refresh_token", old_refresh_token)
    reuse_resp = client.post("/api/auth/refresh")
    assert reuse_resp.status_code == 401

    # The legitimately-rotated token should now also be revoked as a result.
    client.cookies.set("refresh_token", new_refresh_token)
    after_breach_resp = client.post("/api/auth/refresh")
    assert after_breach_resp.status_code == 401


def test_logout_revokes_session(client, db_session):
    _tenant, owner = make_tenant_with_owner(db_session)
    login(client, owner.email)
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200

    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 401


def test_password_reset_flow(client, db_session, monkeypatch):
    import app.services.auth_service as auth_service_module

    captured: dict[str, str] = {}

    def fake_send(*, to: str, reset_url: str) -> None:
        captured["url"] = reset_url

    monkeypatch.setattr(auth_service_module, "send_password_reset_email", fake_send)

    _tenant, owner = make_tenant_with_owner(db_session)
    resp = client.post("/api/auth/forgot-password", json={"email": owner.email})
    assert resp.status_code == 200
    assert "url" in captured

    token = captured["url"].split("token=")[1]
    reset_resp = client.post(
        "/api/auth/reset-password", json={"token": token, "new_password": "BrandNewPassw0rd!456"}
    )
    assert reset_resp.status_code == 200

    old_login = client.post(
        "/api/auth/login", json={"email": owner.email, "password": DEFAULT_PASSWORD}
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/login", json={"email": owner.email, "password": "BrandNewPassw0rd!456"}
    )
    assert new_login.status_code == 200


def test_forgot_password_unknown_email_returns_generic_200(client, db_session):
    resp = client.post("/api/auth/forgot-password", json={"email": "nobody@factory.testmail.dev"})
    assert resp.status_code == 200


def test_mutating_request_without_csrf_header_is_rejected(client, db_session):
    _tenant, owner = make_tenant_with_owner(db_session)
    login(client, owner.email)
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "AnotherPassw0rd!789"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "CSRF validation failed."


def test_change_password_with_csrf_header_succeeds_and_revokes_sessions(client, db_session):
    _tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "AnotherPassw0rd!789"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200
    # Old access token's session should now be revoked (change-password revokes all sessions).
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 401
