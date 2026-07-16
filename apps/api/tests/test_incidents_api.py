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


async def test_declare_incident_and_get_detail(client, db):
    ctx = await _connected_owner(client, db, org="Declare Co", email="owner@incidents-declare.example")
    resp = await client.post(
        "/api/incidents",
        json={"title": "Suspicious login", "description": "Multiple failed attempts.", "severity": "high"},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "declared"
    assert body["finding_count"] == 0
    assert body["asset_count"] == 0

    detail_resp = await client.get(f"/api/incidents/{body['id']}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["title"] == "Suspicious login"


async def test_declare_incident_from_finding_links_asset(client, db):
    ctx = await _connected_owner(client, db, org="Escalate Co", email="owner@incidents-escalate.example")
    await _seed_finding(ctx, "mock_cloud")
    finding = await _get_finding(client, "publicly_exposed_cloud_storage")

    resp = await client.post(
        "/api/incidents",
        json={
            "title": "Exposed bucket incident",
            "description": "",
            "severity": "critical",
            "finding_ids": [finding["id"]],
        },
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["finding_count"] == 1
    assert body["asset_count"] == 1
    assert body["findings"][0]["rule_key"] == "publicly_exposed_cloud_storage"
    assert body["assets"][0]["id"] == finding["asset_id"]


async def test_incident_lifecycle_status_notes_close_reopen(client, db):
    ctx = await _connected_owner(client, db, org="Lifecycle Co", email="owner@incidents-lifecycle.example")
    declare_resp = await client.post(
        "/api/incidents",
        json={"title": "Test incident", "description": "", "severity": "medium"},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    incident_id = declare_resp.json()["id"]

    status_resp = await client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "investigating"},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "investigating"

    note_resp = await client.post(
        f"/api/incidents/{incident_id}/notes",
        json={"message": "Confirmed with the affected user."},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert note_resp.status_code == 200

    close_resp = await client.post(
        f"/api/incidents/{incident_id}/close",
        json={"closure_summary": "Password reset, sessions revoked."},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "closed"

    reopen_resp = await client.post(
        f"/api/incidents/{incident_id}/reopen", headers={"X-CSRF-Token": ctx["csrf_token"]}
    )
    assert reopen_resp.status_code == 200
    assert reopen_resp.json()["status"] == "investigating"

    activity_resp = await client.get(f"/api/incidents/{incident_id}/activity")
    assert activity_resp.status_code == 200
    actions = {entry["action"] for entry in activity_resp.json()}
    assert {"incidents.declared", "incidents.status_changed", "incidents.note_added",
            "incidents.closed", "incidents.reopened"} <= actions


async def test_link_finding_and_asset_endpoints(client, db):
    ctx = await _connected_owner(client, db, org="Link Co", email="owner@incidents-link.example")
    await _seed_finding(ctx, "mock_backup")
    finding = await _get_finding(client, "backup_job_failed")

    declare_resp = await client.post(
        "/api/incidents",
        json={"title": "Backup incident", "description": "", "severity": "high"},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    incident_id = declare_resp.json()["id"]

    link_finding_resp = await client.post(
        f"/api/incidents/{incident_id}/link-finding",
        json={"finding_id": finding["id"]},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert link_finding_resp.status_code == 200
    assert link_finding_resp.json()["finding_count"] == 1
    assert link_finding_resp.json()["asset_count"] == 1  # the finding's own asset auto-linked

    link_asset_resp = await client.post(
        f"/api/incidents/{incident_id}/link-asset",
        json={"asset_id": finding["asset_id"]},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert link_asset_resp.status_code == 200
    assert link_asset_resp.json()["asset_count"] == 1  # already linked, not duplicated


async def test_security_analyst_can_declare_but_not_manage_or_close(client, db):
    ctx = await _connected_owner(
        client, db, org="Analyst Perm Co", email="owner@incidents-analyst-perm.example"
    )
    analyst = await invite_and_accept_member(
        client, db,
        tenant_id=ctx["tenant_id"], inviter_csrf_token=ctx["csrf_token"],
        email="analyst@incidents-analyst-perm.example", full_name="Security Analyst",
        password="Analyst-Pass1!", role_name="security_analyst",
    )

    declare_resp = await client.post(
        "/api/incidents",
        json={"title": "Analyst-declared incident", "description": "", "severity": "medium"},
        headers={"X-CSRF-Token": analyst["csrf_token"]},
    )
    assert declare_resp.status_code == 200, declare_resp.text
    incident_id = declare_resp.json()["id"]

    status_resp = await client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "investigating"},
        headers={"X-CSRF-Token": analyst["csrf_token"]},
    )
    assert status_resp.status_code == 403

    close_resp = await client.post(
        f"/api/incidents/{incident_id}/close",
        json={"closure_summary": "n/a"},
        headers={"X-CSRF-Token": analyst["csrf_token"]},
    )
    assert close_resp.status_code == 403


async def test_incident_summary_endpoint(client, db):
    ctx = await _connected_owner(client, db, org="Summary Co", email="owner@incidents-summary.example")
    await client.post(
        "/api/incidents",
        json={"title": "Open one", "description": "", "severity": "critical"},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    summary_resp = await client.get("/api/incidents/summary")
    assert summary_resp.status_code == 200
    body = summary_resp.json()
    assert body["open_incidents_total"] == 1
    assert body["open_incidents_by_severity"]["critical"] == 1


async def test_incidents_scoped_to_own_tenant(client, db):
    ctx_a = await _connected_owner(
        client, db, org="Incidents Iso A Co", email="ownerA@incidents-iso-a.example"
    )
    await client.post(
        "/api/incidents",
        json={"title": "Tenant A incident", "description": "", "severity": "high"},
        headers={"X-CSRF-Token": ctx_a["csrf_token"]},
    )
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx_a["csrf_token"]})

    await _connected_owner(client, db, org="Incidents Iso B Co", email="ownerB@incidents-iso-b.example")
    resp = await client.get("/api/incidents")
    assert resp.status_code == 200
    assert resp.json() == []
