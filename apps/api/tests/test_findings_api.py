import uuid

import pytest
from gridkeep_connector_sdk.registry import get_connector_class

from db.session import AsyncSessionLocal, set_tenant_context
from modules.assets.ingestion import ingest_sync_records
from modules.findings.engine import run_correlation
from tests.helpers import login, onboard_verified_owner

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


async def _seed_findings(ctx: dict, provider_id: str = "mock_identity") -> None:
    tenant_id = uuid.UUID(ctx["tenant_id"])
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        from modules.integrations import service as integrations_service

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


async def _get_finding_id(client, rule_key: str) -> str:
    resp = await client.get("/api/findings")
    assert resp.status_code == 200
    match = next(f for f in resp.json() if f["rule_key"] == rule_key)
    return match["id"]


async def test_findings_list_and_summary_after_correlation(client, db):
    ctx = await _connected_owner(client, db, org="Findings List Co", email="owner@findings-list.example")
    await _seed_findings(ctx)

    list_resp = await client.get("/api/findings")
    assert list_resp.status_code == 200
    findings = list_resp.json()
    assert len(findings) == 2
    rule_keys = {f["rule_key"] for f in findings}
    assert rule_keys == {"admin_without_mfa", "dormant_user_account"}
    admin_finding = next(f for f in findings if f["rule_key"] == "admin_without_mfa")
    assert admin_finding["severity"] == "critical"
    assert admin_finding["status"] == "open"
    assert admin_finding["risk_score"] > 0

    summary_resp = await client.get("/api/findings/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["open_findings_total"] == 2
    assert summary["open_findings_by_severity"]["critical"] == 1
    assert summary["open_findings_by_severity"]["medium"] == 1
    assert 0 <= summary["security_score"] <= 100


async def test_finding_detail_includes_evidence_and_asset(client, db):
    ctx = await _connected_owner(client, db, org="Findings Detail Co", email="owner@findings-detail.example")
    await _seed_findings(ctx)
    finding_id = await _get_finding_id(client, "admin_without_mfa")

    resp = await client.get(f"/api/findings/{finding_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["evidence"]["is_admin"] is True
    assert body["asset_display_name"]
    assert body["description"]


async def test_assign_finding_to_self(client, db):
    ctx = await _connected_owner(client, db, org="Findings Assign Co", email="owner@findings-assign.example")
    await _seed_findings(ctx)
    finding_id = await _get_finding_id(client, "admin_without_mfa")

    resp = await client.post(
        f"/api/findings/{finding_id}/assign",
        json={"user_id": ctx["user_id"]},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "assigned"
    assert body["assigned_to_user_id"] == ctx["user_id"]


async def test_assign_finding_rejects_non_member(client, db):
    owner_a_email = "ownerA@assign-iso-a.example"
    ctx_a = await _connected_owner(client, db, org="Assign Iso A Co", email=owner_a_email)
    await _seed_findings(ctx_a)
    finding_id = await _get_finding_id(client, "admin_without_mfa")

    # Create a second, unrelated tenant/owner to use as a non-member user_id.
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx_a["csrf_token"]})
    ctx_b = await _connected_owner(client, db, org="Assign Iso B Co", email="ownerB@assign-iso-b.example")
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx_b["csrf_token"]})

    resp = await login(client, owner_a_email, "Owner-Pass1!")
    assert resp.status_code == 200
    csrf_token = resp.json()["csrf_token"]

    resp = await client.post(
        f"/api/findings/{finding_id}/assign",
        json={"user_id": ctx_b["user_id"]},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == 422


async def test_accept_risk_sets_status_and_reason(client, db):
    ctx = await _connected_owner(
        client, db, org="Findings AcceptRisk Co", email="owner@findings-acceptrisk.example"
    )
    await _seed_findings(ctx)
    finding_id = await _get_finding_id(client, "dormant_user_account")

    resp = await client.post(
        f"/api/findings/{finding_id}/accept-risk",
        json={"reason": "Contractor account, expected to be dormant between engagements."},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "accepted_risk"
    assert body["resolution_note"]


async def test_remediate_finding(client, db):
    ctx = await _connected_owner(
        client, db, org="Findings Remediate Co", email="owner@findings-remediate.example"
    )
    await _seed_findings(ctx)
    finding_id = await _get_finding_id(client, "admin_without_mfa")

    resp = await client.post(
        f"/api/findings/{finding_id}/remediate",
        json={"note": "Enabled MFA for this administrator."},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "remediated"
    assert body["closed_at"] is not None


async def test_dismiss_finding_as_false_positive(client, db):
    ctx = await _connected_owner(
        client, db, org="Findings Dismiss Co", email="owner@findings-dismiss.example"
    )
    await _seed_findings(ctx)
    finding_id = await _get_finding_id(client, "dormant_user_account")

    resp = await client.post(
        f"/api/findings/{finding_id}/dismiss",
        json={"reason": "Service account, dormancy is expected."},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "false_positive"


async def test_reopen_finding(client, db):
    ctx = await _connected_owner(client, db, org="Findings Reopen Co", email="owner@findings-reopen.example")
    await _seed_findings(ctx)
    finding_id = await _get_finding_id(client, "admin_without_mfa")

    await client.post(
        f"/api/findings/{finding_id}/remediate",
        json={"note": "Marked fixed."},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    resp = await client.post(
        f"/api/findings/{finding_id}/reopen", headers={"X-CSRF-Token": ctx["csrf_token"]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "open"
    assert body["closed_at"] is None


async def test_finding_activity_records_lifecycle_events(client, db):
    ctx = await _connected_owner(
        client, db, org="Findings Activity Co", email="owner@findings-activity.example"
    )
    await _seed_findings(ctx)
    finding_id = await _get_finding_id(client, "admin_without_mfa")

    await client.post(
        f"/api/findings/{finding_id}/remediate",
        json={"note": "Fixed."},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )

    resp = await client.get(f"/api/findings/{finding_id}/activity")
    assert resp.status_code == 200
    actions = {entry["action"] for entry in resp.json()}
    assert "findings.detected" in actions
    assert "findings.remediated" in actions


async def test_trigger_correlation_enqueues_task(client, db):
    ctx = await _connected_owner(
        client, db, org="Findings Trigger Co", email="owner@findings-trigger.example"
    )
    resp = await client.post("/api/findings/correlate", headers={"X-CSRF-Token": ctx["csrf_token"]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["task_id"]


async def test_findings_scoped_to_own_tenant(client, db):
    ctx_a = await _connected_owner(client, db, org="Findings Iso A Co", email="ownerA@findings-iso-a.example")
    await _seed_findings(ctx_a)
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx_a["csrf_token"]})

    await _connected_owner(client, db, org="Findings Iso B Co", email="ownerB@findings-iso-b.example")
    resp = await client.get("/api/findings")
    assert resp.status_code == 200
    assert resp.json() == []
