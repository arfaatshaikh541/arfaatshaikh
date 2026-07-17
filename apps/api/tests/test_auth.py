import pytest

from tests.helpers import csrf_headers, extract_token_from_url

pytestmark = pytest.mark.asyncio

STRONG_PASSWORD = "CorrectHorse9Battery"


async def test_register_then_verify_then_login(client, smtp_capture):
    resp = await client.post(
        "/auth/register",
        json={
            "email": "alice@example.com",
            "password": STRONG_PASSWORD,
            "full_name": "Alice Example",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert body["email_verified"] is False

    email_body = smtp_capture.latest_body_for("alice@example.com")
    token = extract_token_from_url(email_body, "token")

    verify_resp = await client.post("/auth/verify-email", json={"token": token})
    assert verify_resp.status_code == 200
    assert verify_resp.json()["email_verified"] is True

    login_resp = await client.post(
        "/auth/login", json={"email": "alice@example.com", "password": STRONG_PASSWORD}
    )
    assert login_resp.status_code == 200
    assert "gridkeep_session" in login_resp.cookies
    assert "gridkeep_csrf" in login_resp.cookies

    session_resp = await client.get("/auth/session")
    assert session_resp.status_code == 200
    session_body = session_resp.json()
    assert session_body["user"]["email"] == "alice@example.com"
    assert session_body["memberships"] == []


async def test_duplicate_registration_is_rejected(client):
    payload = {"email": "bob@example.com", "password": STRONG_PASSWORD, "full_name": "Bob Example"}
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


async def test_weak_password_is_rejected(client):
    resp = await client.post(
        "/auth/register",
        json={"email": "weak@example.com", "password": "alllowercase123", "full_name": "Weak"},
    )
    assert resp.status_code == 422


async def test_login_with_wrong_password_fails_and_does_not_leak_account_existence(client):
    await client.post(
        "/auth/register",
        json={"email": "carol@example.com", "password": STRONG_PASSWORD, "full_name": "Carol"},
    )
    wrong = await client.post(
        "/auth/login", json={"email": "carol@example.com", "password": "wrongpassword123"}
    )
    assert wrong.status_code == 401
    nonexistent = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever123"}
    )
    assert nonexistent.status_code == 401
    assert (
        wrong.json()["error"]["code"]
        == nonexistent.json()["error"]["code"]
        == "invalid_credentials"
    )


async def test_logout_revokes_session(client, smtp_capture):
    await client.post(
        "/auth/register",
        json={"email": "dave@example.com", "password": STRONG_PASSWORD, "full_name": "Dave"},
    )
    token = extract_token_from_url(smtp_capture.latest_body_for("dave@example.com"), "token")
    await client.post("/auth/verify-email", json={"token": token})
    await client.post(
        "/auth/login", json={"email": "dave@example.com", "password": STRONG_PASSWORD}
    )

    headers = csrf_headers(client)
    logout_resp = await client.post("/auth/logout", headers=headers)
    assert logout_resp.status_code == 204

    after_logout = await client.get("/auth/session")
    assert after_logout.status_code == 401


async def test_password_reset_flow_revokes_existing_sessions(client, smtp_capture):
    await client.post(
        "/auth/register",
        json={"email": "erin@example.com", "password": STRONG_PASSWORD, "full_name": "Erin"},
    )
    verify_token = extract_token_from_url(smtp_capture.latest_body_for("erin@example.com"), "token")
    await client.post("/auth/verify-email", json={"token": verify_token})
    await client.post(
        "/auth/login", json={"email": "erin@example.com", "password": STRONG_PASSWORD}
    )

    still_valid = await client.get("/auth/session")
    assert still_valid.status_code == 200

    reset_request = await client.post(
        "/auth/password-reset/request", json={"email": "erin@example.com"}
    )
    assert reset_request.status_code == 202

    reset_token = extract_token_from_url(smtp_capture.latest_body_for("erin@example.com"), "token")
    new_password = "AnotherStrongPass9"
    confirm = await client.post(
        "/auth/password-reset/confirm", json={"token": reset_token, "new_password": new_password}
    )
    assert confirm.status_code == 200

    # The old session cookie must now be rejected - password reset revokes
    # every existing session for the account.
    revoked_check = await client.get("/auth/session")
    assert revoked_check.status_code == 401

    relogin = await client.post(
        "/auth/login", json={"email": "erin@example.com", "password": new_password}
    )
    assert relogin.status_code == 200


async def test_password_reset_request_does_not_leak_account_existence(client):
    resp = await client.post(
        "/auth/password-reset/request", json={"email": "nobody-here@example.com"}
    )
    assert resp.status_code == 202
