from app.tests.conftest import login
from app.tests.factories import create_tenant_with_owner


def test_login_success_sets_session_cookie_and_returns_user(client, db_session):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")

    response = client.post("/api/auth/login", json={"email": "owner@test.internal", "password": "OwnerPass!2345"})

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "owner@test.internal"
    assert body["active_tenant_id"] is not None
    assert response.cookies.get("cops_session") is not None


def test_login_wrong_password_returns_generic_error(client, db_session):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")

    response = client.post("/api/auth/login", json={"email": "owner@test.internal", "password": "wrong-password"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_unknown_email_returns_same_generic_error_as_wrong_password(client, db_session):
    """No user enumeration: an unknown email must fail identically to a
    known email with the wrong password."""
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")

    response = client.post("/api/auth/login", json={"email": "nobody@test.internal", "password": "whatever12345"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_throttled_after_repeated_failures(client, db_session):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")

    for _ in range(8):
        client.post("/api/auth/login", json={"email": "owner@test.internal", "password": "wrong-password"})

    response = client.post("/api/auth/login", json={"email": "owner@test.internal", "password": "wrong-password"})

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "login_rate_limited"


def test_logout_revokes_session_so_subsequent_requests_are_unauthenticated(client, db_session):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    assert client.get("/api/auth/me").status_code == 200

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 204

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 401
    assert me_response.json()["error"]["code"] in {"not_authenticated", "session_invalid"}


def test_unauthenticated_request_is_rejected(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_forgot_password_and_reset_flow(client, db_session, fake_email):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OldPassword!123")

    forgot_response = client.post("/api/auth/forgot-password", json={"email": "owner@test.internal"})
    assert forgot_response.status_code == 202

    token = fake_email.last_token_for("owner@test.internal")

    reset_response = client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewPassword!456"})
    assert reset_response.status_code == 204

    old_password_login = client.post("/api/auth/login", json={"email": "owner@test.internal", "password": "OldPassword!123"})
    assert old_password_login.status_code == 401

    new_password_login = client.post("/api/auth/login", json={"email": "owner@test.internal", "password": "NewPassword!456"})
    assert new_password_login.status_code == 200


def test_forgot_password_for_unknown_email_returns_generic_accepted(client, db_session):
    """Must not reveal whether the email exists."""
    response = client.post("/api/auth/forgot-password", json={"email": "nobody@test.internal"})
    assert response.status_code == 202


def test_password_reset_revokes_existing_sessions(client, db_session, fake_email):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OldPassword!123")
    login(client, "owner@test.internal", "OldPassword!123")
    assert client.get("/api/auth/me").status_code == 200

    client.post("/api/auth/forgot-password", json={"email": "owner@test.internal"})
    token = fake_email.last_token_for("owner@test.internal")
    client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewPassword!456"})

    # The original session cookie must no longer work after a password reset.
    stale_session_response = client.get("/api/auth/me")
    assert stale_session_response.status_code == 401


def test_reset_password_with_invalid_token_is_rejected(client, db_session):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OldPassword!123")

    response = client.post("/api/auth/reset-password", json={"token": "not-a-real-token", "new_password": "NewPassword!456"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "reset_invalid"
