"""Hardening-programme Milestone 2: tests for the account-recovery flow
that closes the self-service MFA-lockout gap Milestone 24's backup codes
don't fully cover — a user who has lost their authenticator device AND
every backup code. Real TOTP codes are computed with pyotp, exactly as an
authenticator app would."""

from __future__ import annotations

import uuid as uuid_module

import pyotp
import pytest

from core.errors import ValidationAppError
from db.session import AsyncSessionLocal, set_tenant_context
from modules.identity import recovery_service
from tests.helpers import invite_and_accept_member, login, onboard_verified_owner

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _connected_owner(client, db, *, org: str, email: str, password: str = "Owner-Pass1!"):
    await onboard_verified_owner(client, db, org_name=org, full_name="Owner", email=email, password=password)
    resp = await login(client, email, password)
    assert resp.status_code == 200
    body = resp.json()
    return {
        "tenant_id": body["memberships"][0]["tenant_id"],
        "csrf_token": body["csrf_token"],
        "user_id": body["user"]["id"],
    }


async def _enroll_and_confirm_mfa(client, csrf_token: str) -> str:
    enroll_resp = await client.post("/api/auth/mfa/enroll", headers={"X-CSRF-Token": csrf_token})
    assert enroll_resp.status_code == 200, enroll_resp.text
    secret = enroll_resp.json()["secret"]
    confirm_resp = await client.post(
        "/api/auth/mfa/confirm", json={"code": pyotp.TOTP(secret).now()}, headers={"X-CSRF-Token": csrf_token}
    )
    assert confirm_resp.status_code == 200, confirm_resp.text
    return secret


async def _locked_out_owner_challenge_token(client, db, *, org: str, email: str) -> dict:
    """Onboards an owner, enrolls MFA, logs out, and logs back in far
    enough to get a real MFA challenge token — simulating "lost the
    authenticator and every backup code" without actually needing to burn
    all ten backup codes in every test that needs this starting state."""
    ctx = await _connected_owner(client, db, org=org, email=email)
    await _enroll_and_confirm_mfa(client, ctx["csrf_token"])
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx["csrf_token"]})
    login_resp = await login(client, email, "Owner-Pass1!")
    assert login_resp.status_code == 200
    return {**ctx, "mfa_challenge_token": login_resp.json()["mfa_challenge_token"]}


async def _tenant_with_locked_out_owner_and_second_admin(
    client, db, *, org: str, owner_email: str, admin_email: str
) -> dict:
    """Invites the second admin BEFORE the owner enables MFA — the owner
    needs a normal, working session to send that invitation, and by
    construction won't have one anymore once they're locked out. Mirrors
    a real deployment's actual order of events: teams are built out first,
    lockouts happen later.

    `invite_and_accept_member` leaves the client authenticated as the
    newly-accepted second admin (accepting an invitation issues a fresh
    session, overwriting the inviter's cookies in the shared client), so
    the owner logs back in afterward to enroll their own MFA."""
    owner_ctx = await _connected_owner(client, db, org=org, email=owner_email)
    tenant_id = owner_ctx["tenant_id"]

    await invite_and_accept_member(
        client,
        db,
        tenant_id=tenant_id,
        inviter_csrf_token=owner_ctx["csrf_token"],
        email=admin_email,
        full_name="Second Admin",
        password="Second-Admin-Pass1!",
        role_name="security_administrator",
    )

    owner_login = await login(client, owner_email, "Owner-Pass1!")
    assert owner_login.status_code == 200
    owner_csrf = owner_login.json()["csrf_token"]
    await _enroll_and_confirm_mfa(client, owner_csrf)
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": owner_csrf})

    challenge_resp = await login(client, owner_email, "Owner-Pass1!")
    assert challenge_resp.status_code == 200
    assert challenge_resp.json()["mfa_required"] is True

    return {
        "tenant_id": tenant_id,
        "owner_email": owner_email,
        "admin_email": admin_email,
        "mfa_challenge_token": challenge_resp.json()["mfa_challenge_token"],
    }


async def test_account_recovery_request_requires_a_valid_challenge_token(client, db):
    resp = await client.post(
        "/api/auth/recovery/request",
        json={"mfa_challenge_token": "not-a-real-token", "reason": "Lost my phone and my backup codes."},
    )
    assert resp.status_code == 401


async def test_account_recovery_request_is_idempotent_when_already_pending(client, db):
    locked_out = await _locked_out_owner_challenge_token(
        client, db, org="Recovery Idempotent Co", email="owner@recovery-idempotent.example"
    )

    first = await client.post(
        "/api/auth/recovery/request",
        json={"mfa_challenge_token": locked_out["mfa_challenge_token"], "reason": "Lost my phone."},
    )
    assert first.status_code == 200, first.text

    second = await client.post(
        "/api/auth/recovery/request",
        json={
            "mfa_challenge_token": locked_out["mfa_challenge_token"],
            "reason": "Still lost, trying again.",
        },
    )
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


async def test_account_recovery_full_approval_flow_disables_mfa_and_allows_plain_login(client, db):
    setup = await _tenant_with_locked_out_owner_and_second_admin(
        client,
        db,
        org="Recovery Approve Co",
        owner_email="owner@recovery-approve.example",
        admin_email="second-admin@recovery-approve.example",
    )
    request_resp = await client.post(
        "/api/auth/recovery/request",
        json={"mfa_challenge_token": setup["mfa_challenge_token"], "reason": "Lost my phone."},
    )
    assert request_resp.status_code == 200
    request_id = request_resp.json()["id"]

    admin_login = await login(client, setup["admin_email"], "Second-Admin-Pass1!")
    assert admin_login.status_code == 200
    admin_csrf = admin_login.json()["csrf_token"]

    pending_resp = await client.get("/api/auth/recovery/pending")
    assert pending_resp.status_code == 200
    assert request_id in {r["id"] for r in pending_resp.json()}

    approve_resp = await client.post(
        f"/api/auth/recovery/{request_id}/approve", headers={"X-CSRF-Token": admin_csrf}
    )
    assert approve_resp.status_code == 200, approve_resp.text

    # The recovered user can now log in with just their password — no MFA
    # challenge — and re-enroll fresh afterward.
    plain_login = await login(client, setup["owner_email"], "Owner-Pass1!")
    assert plain_login.status_code == 200
    assert plain_login.json()["user"]["mfa_enabled"] is False


async def test_account_recovery_cannot_be_approved_by_the_requester_themselves(client, db):
    """Even a still-valid session belonging to the SAME account must never
    be able to approve that account's own recovery request — approving it
    disables MFA, so self-approval (via any session, not just the one
    that's currently locked out) would turn this into a way to strip your
    own MFA without ever proving you lost your second factor. Exercised
    directly against the service boundary, which is the actual enforcement
    point regardless of which route or session reaches it."""
    ctx = await _connected_owner(
        client, db, org="Recovery Self Approve Co", email="owner@recovery-self-approve.example"
    )
    await invite_and_accept_member(
        client,
        db,
        tenant_id=ctx["tenant_id"],
        inviter_csrf_token=ctx["csrf_token"],
        email="analyst@recovery-self-approve.example",
        full_name="Analyst",
        password="Analyst-Pass1!",
        role_name="security_administrator",
    )
    analyst_login = await login(client, "analyst@recovery-self-approve.example", "Analyst-Pass1!")
    assert analyst_login.status_code == 200
    analyst_csrf = analyst_login.json()["csrf_token"]

    await _enroll_and_confirm_mfa(client, analyst_csrf)
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": analyst_csrf})
    analyst_relogin = await login(client, "analyst@recovery-self-approve.example", "Analyst-Pass1!")
    challenge_token = analyst_relogin.json()["mfa_challenge_token"]

    request_resp = await client.post(
        "/api/auth/recovery/request",
        json={"mfa_challenge_token": challenge_token, "reason": "Lost my phone."},
    )
    request_id = request_resp.json()["id"]

    analyst_user_id = uuid_module.UUID(analyst_login.json()["user"]["id"])
    async with AsyncSessionLocal() as session:
        # Milestone 31 (finding C-01): the real HTTP route reaches this
        # service function through `get_tenant_db`, which always sets
        # `app.current_tenant_id` before the handler runs — RLS now actually
        # enforces that on the Membership join this function's visibility
        # check depends on, so a direct service-layer call (as this test
        # makes) must set the same context to see the row at all, exactly
        # like the real request flow already does.
        await set_tenant_context(session, uuid_module.UUID(ctx["tenant_id"]))
        with pytest.raises(ValidationAppError):
            await recovery_service.approve_recovery_request(
                session,
                request_id=uuid_module.UUID(request_id),
                approver_user_id=analyst_user_id,
                tenant_id=uuid_module.UUID(ctx["tenant_id"]),
            )


async def test_account_recovery_request_not_visible_to_admin_of_an_unrelated_tenant(client, db):
    locked_out = await _locked_out_owner_challenge_token(
        client, db, org="Recovery Unrelated A Co", email="owner@recovery-unrelated-a.example"
    )
    await client.post(
        "/api/auth/recovery/request",
        json={"mfa_challenge_token": locked_out["mfa_challenge_token"], "reason": "Lost my phone."},
    )

    await client.post("/api/auth/logout", headers={"X-CSRF-Token": locked_out["csrf_token"]})
    await _connected_owner(
        client, db, org="Recovery Unrelated B Co", email="owner@recovery-unrelated-b.example"
    )

    pending_resp = await client.get("/api/auth/recovery/pending")
    assert pending_resp.status_code == 200
    assert pending_resp.json() == []


async def test_account_recovery_deny_leaves_mfa_enabled(client, db):
    setup = await _tenant_with_locked_out_owner_and_second_admin(
        client,
        db,
        org="Recovery Deny Co",
        owner_email="owner@recovery-deny.example",
        admin_email="second-admin@recovery-deny.example",
    )
    request_resp = await client.post(
        "/api/auth/recovery/request",
        json={"mfa_challenge_token": setup["mfa_challenge_token"], "reason": "Lost my phone."},
    )
    request_id = request_resp.json()["id"]

    admin_login = await login(client, setup["admin_email"], "Second-Admin-Pass1!")
    admin_csrf = admin_login.json()["csrf_token"]

    deny_resp = await client.post(
        f"/api/auth/recovery/{request_id}/deny",
        json={"reason": "Could not verify identity over the phone."},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert deny_resp.status_code == 200, deny_resp.text

    # MFA is still required — the account was never recovered.
    login_resp = await login(client, setup["owner_email"], "Owner-Pass1!")
    assert login_resp.status_code == 200
    assert login_resp.json()["mfa_required"] is True
