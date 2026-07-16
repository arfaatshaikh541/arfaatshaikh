"""Tests for Milestone 14: TenantSecurityProfile.require_mfa_for_admins
and require_step_up_for_disruptive_actions actually being enforced,
rather than stored-but-ignored as they were through Milestone 13."""

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


async def test_new_tenant_defaults_to_require_mfa_for_admins_off(client, db):
    """A default of True would lock every freshly-onboarded owner out of
    their own workspace immediately, with no way to satisfy the gate."""
    await _connected_owner(client, db, org="Default Off Co", email="owner@default-off.example")

    get_resp = await client.get("/api/tenancy/security-profile")
    assert get_resp.status_code == 200
    assert get_resp.json()["require_mfa_for_admins"] is False


async def test_admin_without_mfa_is_blocked_once_tenant_requires_it(client, db):
    ctx = await _connected_owner(client, db, org="MFA Required Co", email="owner@mfa-required.example")

    toggle_resp = await client.patch(
        "/api/tenancy/security-profile",
        json={"require_mfa_for_admins": True},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert toggle_resp.status_code == 200, toggle_resp.text

    blocked_resp = await client.get("/api/tenancy/security-profile")
    assert blocked_resp.status_code == 403
    assert blocked_resp.json()["error"]["code"] == "mfa_enrollment_required"

    # /me still works (no TenantContext involved) and surfaces the flag.
    me_resp = await client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["mfa_enrollment_required"] is True

    # Enrolling MFA is still possible while blocked - it only needs AuthContext.
    await _enroll_and_confirm_mfa(client, ctx["csrf_token"])

    unblocked_resp = await client.get("/api/tenancy/security-profile")
    assert unblocked_resp.status_code == 200
    assert unblocked_resp.json()["require_mfa_for_admins"] is True


async def test_admin_with_mfa_already_enabled_is_unaffected_by_the_toggle(client, db):
    ctx = await _connected_owner(
        client, db, org="MFA Already Enabled Co", email="owner@mfa-already-enabled.example"
    )
    await _enroll_and_confirm_mfa(client, ctx["csrf_token"])

    toggle_resp = await client.patch(
        "/api/tenancy/security-profile",
        json={"require_mfa_for_admins": True},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert toggle_resp.status_code == 200

    still_ok_resp = await client.get("/api/tenancy/security-profile")
    assert still_ok_resp.status_code == 200


async def test_non_admin_role_is_never_blocked_by_the_toggle(client, db):
    ctx = await _connected_owner(client, db, org="Non Admin Role Co", email="owner@non-admin-role.example")
    await _enroll_and_confirm_mfa(client, ctx["csrf_token"])
    await client.patch(
        "/api/tenancy/security-profile",
        json={"require_mfa_for_admins": True},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )

    await invite_and_accept_member(
        client, db,
        tenant_id=ctx["tenant_id"], inviter_csrf_token=ctx["csrf_token"],
        email="analyst@non-admin-role.example", full_name="Security Analyst",
        password="Analyst-Pass1!", role_name="security_analyst",
    )

    # security_analyst is not an admin-designated role and has no MFA - unaffected.
    resp = await client.get("/api/findings")
    assert resp.status_code == 200


async def test_login_and_me_expose_mfa_enrollment_required(client, db):
    ctx = await _connected_owner(
        client, db, org="Flag Exposure Co", email="owner@flag-exposure.example"
    )
    await client.patch(
        "/api/tenancy/security-profile",
        json={"require_mfa_for_admins": True},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )

    me_resp = await client.get("/api/auth/me")
    assert me_resp.json()["mfa_enrollment_required"] is True

    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx["csrf_token"]})
    login_resp = await login(client, "owner@flag-exposure.example", "Owner-Pass1!")
    assert login_resp.status_code == 200
    assert login_resp.json()["mfa_enrollment_required"] is True


async def test_require_step_up_toggle_off_lets_mfa_enabled_admin_approve_without_step_up(client, db):
    ctx = await _connected_owner(
        client, db, org="Step Up Opt Out Co", email="owner@step-up-opt-out.example"
    )
    secret = await _enroll_and_confirm_mfa(client, ctx["csrf_token"])
    await client.patch(
        "/api/tenancy/security-profile",
        json={"require_step_up_for_disruptive_actions": False},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    await _seed_finding(ctx, "mock_cloud")
    finding = await _get_finding(client, "publicly_exposed_cloud_storage")

    analyst = await invite_and_accept_member(
        client, db,
        tenant_id=ctx["tenant_id"], inviter_csrf_token=ctx["csrf_token"],
        email="analyst@step-up-opt-out.example", full_name="Security Analyst",
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
    owner_login = await login(client, "owner@step-up-opt-out.example", "Owner-Pass1!")
    assert owner_login.status_code == 200
    assert owner_login.json()["mfa_required"] is True
    verify_resp = await client.post(
        "/api/auth/mfa/verify-login",
        json={
            "mfa_challenge_token": owner_login.json()["mfa_challenge_token"],
            "code": pyotp.TOTP(secret).now(),
        },
    )
    assert verify_resp.status_code == 200
    owner_csrf = verify_resp.json()["csrf_token"]

    # No step-up call made at all - the tenant opted out, so this should
    # succeed directly despite the owner having MFA enabled.
    approve_resp = await client.post(
        f"/api/actions/{action_run_id}/approve", headers={"X-CSRF-Token": owner_csrf}
    )
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json()["action_run"]["status"] == "approved"
