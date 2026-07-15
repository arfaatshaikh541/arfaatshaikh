import pytest

from modules.identity import service as identity_service
from modules.permissions import service as permissions_service
from tests.helpers import get_user_by_email, login, onboard_verified_owner

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_onboarding_creates_trial_owner(client, db):
    body = await onboard_verified_owner(
        client,
        db,
        org_name="Riverside Clinic",
        full_name="Sam Rivera",
        email="sam@riverside-clinic.example",
        password="Riverside-Owner-Pass1!",
    )
    assert body["tenant_slug"] == "riverside-clinic"


async def test_login_before_verification_is_rejected(client, db):
    resp = await client.post(
        "/api/tenancy/onboarding",
        json={
            "organisation_name": "Unverified Co",
            "full_name": "Unver Ified",
            "email": "unverified@example.com",
            "password": "Unverified-Pass1!",
        },
    )
    assert resp.status_code == 200

    login_resp = await login(client, "unverified@example.com", "Unverified-Pass1!")
    assert login_resp.status_code == 401
    assert login_resp.json()["error"]["code"] == "authentication_required"


async def test_login_logout_and_me(client, db):
    await onboard_verified_owner(
        client, db, org_name="Acme Trading", full_name="Owner One",
        email="owner@acme-trading.example", password="Acme-Owner-Pass1!",
    )
    login_resp = await login(client, "owner@acme-trading.example", "Acme-Owner-Pass1!")
    assert login_resp.status_code == 200
    body = login_resp.json()
    assert body["active_membership_id"] is not None
    csrf = body["csrf_token"]

    me_resp = await client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["email"] == "owner@acme-trading.example"

    logout_no_csrf = await client.post("/api/auth/logout")
    assert logout_no_csrf.status_code == 403

    logout_resp = await client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout_resp.status_code == 200

    me_after_logout = await client.get("/api/auth/me")
    assert me_after_logout.status_code == 401


async def test_wrong_password_rejected(client, db):
    await onboard_verified_owner(
        client, db, org_name="Wrongpw Co", full_name="Owner Two",
        email="owner@wrongpw.example", password="Correct-Pass1!",
    )
    resp = await login(client, "owner@wrongpw.example", "not-the-password")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


async def test_password_reset_flow(client, db):
    await onboard_verified_owner(
        client, db, org_name="Reset Co", full_name="Owner Reset",
        email="owner@reset-co.example", password="Old-Password1!",
    )
    user = await get_user_by_email(db, "owner@reset-co.example")
    raw_token = await identity_service.issue_password_reset_token(db, user)
    await db.commit()

    resp = await client.post(
        "/api/auth/reset-password", json={"token": raw_token, "new_password": "New-Password1!"}
    )
    assert resp.status_code == 200

    old_login = await login(client, "owner@reset-co.example", "Old-Password1!")
    assert old_login.status_code == 401

    new_login = await login(client, "owner@reset-co.example", "New-Password1!")
    assert new_login.status_code == 200


async def test_forgot_password_does_not_leak_account_existence(client, db):
    resp_existing = await client.post(
        "/api/auth/forgot-password", json={"email": "nobody-registered@example.com"}
    )
    assert resp_existing.status_code == 200
    assert resp_existing.json() == {"status": "ok"}


async def test_invitation_accept_flow(client, db):
    await onboard_verified_owner(
        client, db, org_name="Invite Co", full_name="Owner Invite",
        email="owner@invite-co.example", password="Owner-Pass1!",
    )
    owner_login = await login(client, "owner@invite-co.example", "Owner-Pass1!")
    tenant_id = owner_login.json()["memberships"][0]["tenant_id"]

    owner = await get_user_by_email(db, "owner@invite-co.example")
    import uuid as _uuid

    from db.session import set_tenant_context

    await set_tenant_context(db, _uuid.UUID(tenant_id))
    invitation, raw_token = await permissions_service.create_invitation(
        db,
        tenant_id=_uuid.UUID(tenant_id),
        invited_by_user_id=owner.id,
        email="analyst@invite-co.example",
        role_name="security_analyst",
    )
    await db.commit()

    accept_resp = await client.post(
        "/api/auth/accept-invitation",
        json={"token": raw_token, "full_name": "New Analyst", "password": "Analyst-Pass1!"},
    )
    assert accept_resp.status_code == 200, accept_resp.text
    body = accept_resp.json()
    assert body["memberships"][0]["role_name"] == "security_analyst"

    # accepting the same invitation twice must fail
    accept_again = await client.post(
        "/api/auth/accept-invitation",
        json={"token": raw_token, "full_name": "New Analyst", "password": "Analyst-Pass1!"},
    )
    assert accept_again.status_code == 401


async def test_rate_limiting_on_login(client, db):
    await onboard_verified_owner(
        client, db, org_name="RateLimit Co", full_name="Owner RL",
        email="owner@ratelimit.example", password="Owner-Pass1!",
    )
    responses = []
    for _ in range(15):
        responses.append(await login(client, "owner@ratelimit.example", "wrong-password"))
    assert any(r.status_code == 429 for r in responses)
