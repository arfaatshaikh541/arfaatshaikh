import uuid

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


async def test_action_catalog_lists_provider_actions_for_asset(client, db):
    ctx = await _connected_owner(client, db, org="Catalog Co", email="owner@actions-catalog.example")
    await _seed_finding(ctx, "mock_backup")
    finding = await _get_finding(client, "backup_job_failed")

    resp = await client.get("/api/actions/catalog", params={"asset_id": finding["asset_id"]})
    assert resp.status_code == 200, resp.text
    keys = {entry["action_key"] for entry in resp.json()}
    assert "trigger_restore_test" in keys


async def test_execute_action_safety_class_1_runs_immediately(client, db):
    ctx = await _connected_owner(client, db, org="Execute Safe Co", email="owner@execute-safe.example")
    await _seed_finding(ctx, "mock_backup")
    finding = await _get_finding(client, "backup_job_failed")

    resp = await client.post(
        "/api/actions/execute",
        json={
            "asset_id": finding["asset_id"],
            "action_key": "trigger_restore_test",
            "finding_id": finding["id"],
        },
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["action_run"]["status"] == "approved"
    assert body["task_id"]


async def test_execute_disruptive_action_without_approve_permission_is_pending(client, db):
    ctx = await _connected_owner(client, db, org="Execute Pending Co", email="owner@execute-pending.example")
    await _seed_finding(ctx, "mock_cloud")
    finding = await _get_finding(client, "publicly_exposed_cloud_storage")

    analyst = await invite_and_accept_member(
        client, db,
        tenant_id=ctx["tenant_id"], inviter_csrf_token=ctx["csrf_token"],
        email="analyst@execute-pending.example", full_name="Security Analyst",
        password="Analyst-Pass1!", role_name="security_analyst",
    )

    resp = await client.post(
        "/api/actions/execute",
        json={
            "asset_id": finding["asset_id"],
            "action_key": "disable_public_sharing",
            "finding_id": finding["id"],
        },
        headers={"X-CSRF-Token": analyst["csrf_token"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["action_run"]["status"] == "pending_approval"
    assert body["task_id"] is None


async def test_execute_action_requires_execute_safe_permission(client, db):
    ctx = await _connected_owner(client, db, org="No Permission Co", email="owner@no-permission.example")
    await _seed_finding(ctx, "mock_backup")
    finding = await _get_finding(client, "backup_job_failed")

    viewer = await invite_and_accept_member(
        client, db,
        tenant_id=ctx["tenant_id"], inviter_csrf_token=ctx["csrf_token"],
        email="viewer@no-permission.example", full_name="Executive Viewer",
        password="Viewer-Pass1!", role_name="executive_viewer",
    )

    resp = await client.post(
        "/api/actions/execute",
        json={"asset_id": finding["asset_id"], "action_key": "trigger_restore_test"},
        headers={"X-CSRF-Token": viewer["csrf_token"]},
    )
    assert resp.status_code == 403


async def test_approve_and_reject_action_run(client, db):
    ctx = await _connected_owner(client, db, org="Approve Reject Co", email="owner@actions-approve.example")
    await _seed_finding(ctx, "mock_cloud")
    finding = await _get_finding(client, "publicly_exposed_cloud_storage")

    analyst = await invite_and_accept_member(
        client, db,
        tenant_id=ctx["tenant_id"], inviter_csrf_token=ctx["csrf_token"],
        email="analyst@actions-approve.example", full_name="Security Analyst",
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

    # Switch back to the owner, who has actions.approve_disruptive.
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": analyst["csrf_token"]})
    owner_login = await login(client, "owner@actions-approve.example", "Owner-Pass1!")
    owner_csrf = owner_login.json()["csrf_token"]

    approve_resp = await client.post(
        f"/api/actions/{action_run_id}/approve", headers={"X-CSRF-Token": owner_csrf}
    )
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json()["action_run"]["status"] == "approved"
    assert approve_resp.json()["task_id"]

    reject_resp = await client.post(
        f"/api/actions/{action_run_id}/reject",
        json={"reason": "changed my mind"},
        headers={"X-CSRF-Token": owner_csrf},
    )
    assert reject_resp.status_code == 422  # already approved, not pending


async def test_playbooks_crud(client, db):
    ctx = await _connected_owner(client, db, org="Playbooks Co", email="owner@playbooks.example")

    create_resp = await client.post(
        "/api/playbooks",
        json={
            "name": "Retry failed backups",
            "rule_key": "backup_job_failed",
            "action_key": "trigger_restore_test",
        },
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert create_resp.status_code == 200, create_resp.text
    playbook_id = create_resp.json()["id"]
    assert create_resp.json()["is_enabled"] is True

    list_resp = await client.get("/api/playbooks")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    update_resp = await client.patch(
        f"/api/playbooks/{playbook_id}",
        json={"is_enabled": False},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["is_enabled"] is False

    delete_resp = await client.delete(
        f"/api/playbooks/{playbook_id}", headers={"X-CSRF-Token": ctx["csrf_token"]}
    )
    assert delete_resp.status_code == 200

    final_list = await client.get("/api/playbooks")
    assert final_list.json() == []


async def test_playbook_rejects_unknown_rule_key(client, db):
    ctx = await _connected_owner(client, db, org="Bad Rule Co", email="owner@bad-rule.example")
    resp = await client.post(
        "/api/playbooks",
        json={"name": "Bad playbook", "rule_key": "not_a_real_rule", "action_key": "trigger_restore_test"},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert resp.status_code == 422


async def test_automation_settings_get_and_update(client, db):
    ctx = await _connected_owner(
        client, db, org="Automation Settings Co", email="owner@automation-settings.example"
    )

    default_resp = await client.get("/api/automation/settings")
    assert default_resp.status_code == 200
    assert default_resp.json()["mode"] == "observe"

    update_resp = await client.patch(
        "/api/automation/settings",
        json={"mode": "balanced"},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["mode"] == "balanced"

    confirm_resp = await client.get("/api/automation/settings")
    assert confirm_resp.json()["mode"] == "balanced"


async def test_actions_scoped_to_own_tenant(client, db):
    ctx_a = await _connected_owner(client, db, org="Actions Iso A Co", email="ownerA@actions-iso-a.example")
    await _seed_finding(ctx_a, "mock_backup")
    finding = await _get_finding(client, "backup_job_failed")
    await client.post(
        "/api/actions/execute",
        json={"asset_id": finding["asset_id"], "action_key": "trigger_restore_test"},
        headers={"X-CSRF-Token": ctx_a["csrf_token"]},
    )
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx_a["csrf_token"]})

    await _connected_owner(client, db, org="Actions Iso B Co", email="ownerB@actions-iso-b.example")
    resp = await client.get("/api/actions")
    assert resp.status_code == 200
    assert resp.json() == []
