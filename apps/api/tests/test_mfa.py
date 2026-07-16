"""Tests for Milestone 13: MFA enrollment, login step-up challenge, and
require_step_up wired into disruptive-action approval. Real TOTP codes are
computed with pyotp in these tests, exactly as an authenticator app would
— nothing about MFA verification is mocked."""

from __future__ import annotations

import uuid

import pyotp
import pytest
from gridkeep_connector_sdk.registry import get_connector_class

from db.session import AsyncSessionLocal, set_tenant_context
from modules.assets.ingestion import ingest_sync_records
from modules.findings.engine import run_correlation
from modules.integrations import service as integrations_service
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
        "/api/auth/mfa/confirm",
        json={"code": pyotp.TOTP(secret).now()},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert confirm_resp.status_code == 200, confirm_resp.text
    return secret


async def _seed_finding(ctx: dict, provider_id: str) -> None:
    tenant_id = uuid.UUID(ctx["tenant_id"])
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        tenant_integration = await integrations_service.connect_integration(
            session,
            tenant_id=tenant_id,
            actor_user_id=uuid.UUID(ctx["user_id"]),
            provider_id=provider_id,
            label="Seed Integration",
            secret_plaintext="fake-secret",
        )
        connector = get_connector_class(provider_id)(credential_plaintext="fake-secret")
        records = [r async for r in connector.sync()]
        await ingest_sync_records(
            session,
            tenant_id=tenant_id,
            tenant_integration_id=tenant_integration.id,
            provider_id=provider_id,
            records=records,
        )
        await session.commit()
        await set_tenant_context(session, tenant_id)
        await run_correlation(session, tenant_id=tenant_id)
        await session.commit()


async def _get_finding(client, rule_key: str) -> dict:
    resp = await client.get("/api/findings")
    assert resp.status_code == 200
    return next(f for f in resp.json() if f["rule_key"] == rule_key)


async def test_enroll_and_confirm_mfa_happy_path(client, db):
    ctx = await _connected_owner(client, db, org="MFA Enroll Co", email="owner@mfa-enroll.example")

    await _enroll_and_confirm_mfa(client, ctx["csrf_token"])

    me_resp = await client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["mfa_enabled"] is True


async def test_confirm_mfa_with_wrong_code_is_rejected(client, db):
    ctx = await _connected_owner(
        client, db, org="MFA Wrong Confirm Co", email="owner@mfa-wrong-confirm.example"
    )

    enroll_resp = await client.post("/api/auth/mfa/enroll", headers={"X-CSRF-Token": ctx["csrf_token"]})
    assert enroll_resp.status_code == 200

    confirm_resp = await client.post(
        "/api/auth/mfa/confirm", json={"code": "000000"}, headers={"X-CSRF-Token": ctx["csrf_token"]}
    )
    assert confirm_resp.status_code == 422

    me_resp = await client.get("/api/auth/me")
    assert me_resp.json()["user"]["mfa_enabled"] is False


async def test_login_with_mfa_enabled_requires_a_challenge(client, db):
    ctx = await _connected_owner(client, db, org="MFA Login Co", email="owner@mfa-login.example")
    secret = await _enroll_and_confirm_mfa(client, ctx["csrf_token"])
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx["csrf_token"]})

    login_resp = await login(client, "owner@mfa-login.example", "Owner-Pass1!")
    assert login_resp.status_code == 200
    body = login_resp.json()
    assert body["mfa_required"] is True
    assert "mfa_challenge_token" in body
    assert "csrf_token" not in body

    # No session yet - a tenant-scoped call should still be unauthenticated.
    me_resp = await client.get("/api/auth/me")
    assert me_resp.status_code == 401

    verify_resp = await client.post(
        "/api/auth/mfa/verify-login",
        json={"mfa_challenge_token": body["mfa_challenge_token"], "code": pyotp.TOTP(secret).now()},
    )
    assert verify_resp.status_code == 200, verify_resp.text
    assert verify_resp.json()["csrf_token"]

    me_resp_after = await client.get("/api/auth/me")
    assert me_resp_after.status_code == 200


async def test_mfa_verify_login_with_wrong_code_is_rejected(client, db):
    ctx = await _connected_owner(client, db, org="MFA Wrong Login Co", email="owner@mfa-wrong-login.example")
    await _enroll_and_confirm_mfa(client, ctx["csrf_token"])
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx["csrf_token"]})

    login_resp = await login(client, "owner@mfa-wrong-login.example", "Owner-Pass1!")
    challenge_token = login_resp.json()["mfa_challenge_token"]

    verify_resp = await client.post(
        "/api/auth/mfa/verify-login", json={"mfa_challenge_token": challenge_token, "code": "000000"}
    )
    assert verify_resp.status_code == 401


async def test_disable_mfa_requires_the_correct_code(client, db):
    ctx = await _connected_owner(client, db, org="MFA Disable Co", email="owner@mfa-disable.example")
    secret = await _enroll_and_confirm_mfa(client, ctx["csrf_token"])

    wrong_resp = await client.post(
        "/api/auth/mfa/disable", json={"code": "000000"}, headers={"X-CSRF-Token": ctx["csrf_token"]}
    )
    assert wrong_resp.status_code == 422

    right_resp = await client.post(
        "/api/auth/mfa/disable",
        json={"code": pyotp.TOTP(secret).now()},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert right_resp.status_code == 200

    me_resp = await client.get("/api/auth/me")
    assert me_resp.json()["user"]["mfa_enabled"] is False


async def test_step_up_requires_mfa_enabled_first(client, db):
    ctx = await _connected_owner(client, db, org="Step Up No MFA Co", email="owner@step-up-no-mfa.example")

    resp = await client.post(
        "/api/auth/step-up", json={"code": "000000"}, headers={"X-CSRF-Token": ctx["csrf_token"]}
    )
    assert resp.status_code == 422


async def test_approve_action_run_requires_step_up_when_mfa_enabled(client, db):
    ctx = await _connected_owner(
        client, db, org="Step Up Approve Co", email="owner@step-up-approve.example"
    )
    secret = await _enroll_and_confirm_mfa(client, ctx["csrf_token"])
    await _seed_finding(ctx, "mock_cloud")
    finding = await _get_finding(client, "publicly_exposed_cloud_storage")

    analyst = await invite_and_accept_member(
        client, db,
        tenant_id=ctx["tenant_id"], inviter_csrf_token=ctx["csrf_token"],
        email="analyst@step-up-approve.example", full_name="Security Analyst",
        password="Analyst-Pass1!", role_name="security_analyst",
    )
    request_resp = await client.post(
        "/api/actions/execute",
        json={
            "asset_id": finding["asset_id"],
            "action_key": "disable_public_sharing",
            "finding_id": finding["id"],
        },
        headers={"X-CSRF-Token": analyst["csrf_token"]},
    )
    action_run_id = request_resp.json()["action_run"]["id"]

    await client.post("/api/auth/logout", headers={"X-CSRF-Token": analyst["csrf_token"]})
    owner_login = await login(client, "owner@step-up-approve.example", "Owner-Pass1!")
    assert owner_login.status_code == 200
    assert owner_login.json()["mfa_required"] is True  # the owner has MFA enabled now

    verify_resp = await client.post(
        "/api/auth/mfa/verify-login",
        json={
            "mfa_challenge_token": owner_login.json()["mfa_challenge_token"],
            "code": pyotp.TOTP(secret).now(),
        },
    )
    assert verify_resp.status_code == 200
    owner_csrf = verify_resp.json()["csrf_token"]

    without_step_up_resp = await client.post(
        f"/api/actions/{action_run_id}/approve", headers={"X-CSRF-Token": owner_csrf}
    )
    assert without_step_up_resp.status_code == 403
    assert without_step_up_resp.json()["error"]["details"]["step_up_required"] is True

    step_up_resp = await client.post(
        "/api/auth/step-up",
        json={"code": pyotp.TOTP(secret).now()},
        headers={"X-CSRF-Token": owner_csrf},
    )
    assert step_up_resp.status_code == 200, step_up_resp.text

    approve_resp = await client.post(
        f"/api/actions/{action_run_id}/approve", headers={"X-CSRF-Token": owner_csrf}
    )
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json()["action_run"]["status"] == "approved"


async def test_security_profile_get_update_round_trip_and_permission_gating(client, db):
    ctx = await _connected_owner(
        client, db, org="Security Profile Co", email="owner@security-profile.example"
    )

    get_resp = await client.get("/api/tenancy/security-profile")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["require_mfa_for_admins"] is False
    assert body["require_step_up_for_disruptive_actions"] is True

    patch_resp = await client.patch(
        "/api/tenancy/security-profile",
        json={"require_step_up_for_disruptive_actions": False},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["require_step_up_for_disruptive_actions"] is False
    assert patch_resp.json()["require_mfa_for_admins"] is False  # untouched field preserved

    await invite_and_accept_member(
        client, db,
        tenant_id=ctx["tenant_id"], inviter_csrf_token=ctx["csrf_token"],
        email="analyst@security-profile.example", full_name="Security Analyst",
        password="Analyst-Pass1!", role_name="security_analyst",
    )
    forbidden_resp = await client.get("/api/tenancy/security-profile")
    assert forbidden_resp.status_code == 403
