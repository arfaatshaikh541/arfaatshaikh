import pytest
from sqlalchemy import select

from db.session import AsyncSessionLocal
from modules.compliance.models import ComplianceControl, ComplianceFramework
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


async def _soc2_control_id() -> str:
    async with AsyncSessionLocal() as session:
        framework = (
            await session.execute(
                select(ComplianceFramework).where(ComplianceFramework.key == "soc2_type2")
            )
        ).scalar_one()
        control = (
            await session.execute(
                select(ComplianceControl)
                .where(ComplianceControl.framework_id == framework.id)
                .order_by(ComplianceControl.sort_order)
            )
        ).scalars().first()
        return str(control.id)


async def test_list_frameworks_endpoint(client, db):
    await _connected_owner(client, db, org="API Compliance Co", email="owner@api-compliance.example")

    resp = await client.get("/api/compliance/frameworks")

    assert resp.status_code == 200
    body = resp.json()
    keys = {f["key"] for f in body}
    assert {"soc2_type2", "iso27001"} <= keys
    soc2 = next(f for f in body if f["key"] == "soc2_type2")
    assert len(soc2["controls"]) == 5


async def test_update_control_status_endpoint(client, db):
    ctx = await _connected_owner(client, db, org="API Control Update Co", email="owner@api-control.example")
    control_id = await _soc2_control_id()

    resp = await client.patch(
        f"/api/compliance/controls/{control_id}",
        json={"status": "met", "note": "Verified in audit."},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "met"
    assert body["note"] == "Verified in audit."


async def test_compliance_summary_endpoint(client, db):
    ctx = await _connected_owner(client, db, org="API Summary Co", email="owner@api-summary.example")
    control_id = await _soc2_control_id()
    await client.patch(
        f"/api/compliance/controls/{control_id}",
        json={"status": "met", "note": None},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )

    resp = await client.get("/api/compliance/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_score"] is not None
    assert any(f["key"] == "soc2_type2" and f["met_count"] == 1 for f in body["frameworks"])


async def test_security_analyst_cannot_manage_compliance(client, db):
    ctx = await _connected_owner(
        client, db, org="API Compliance Perm Co", email="owner@api-compliance-perm.example"
    )
    member = await invite_and_accept_member(
        client, db, tenant_id=ctx["tenant_id"], inviter_csrf_token=ctx["csrf_token"],
        email="analyst@api-compliance-perm.example", full_name="Analyst", password="Analyst-Pass1!",
        role_name="security_analyst",
    )
    control_id = await _soc2_control_id()

    resp = await client.patch(
        f"/api/compliance/controls/{control_id}",
        json={"status": "met", "note": None},
        headers={"X-CSRF-Token": member["csrf_token"]},
    )

    assert resp.status_code == 403


async def test_evidence_create_permission_depends_on_target(client, db):
    ctx = await _connected_owner(
        client, db, org="API Evidence Target Co", email="owner@api-evidence-target.example"
    )
    member = await invite_and_accept_member(
        client, db, tenant_id=ctx["tenant_id"], inviter_csrf_token=ctx["csrf_token"],
        email="responder@api-evidence-target.example", full_name="Responder", password="Responder-Pass1!",
        role_name="incident_responder",
    )
    control_id = await _soc2_control_id()

    incident_resp = await client.post(
        "/api/incidents",
        json={"title": "Breach", "description": "", "severity": "high"},
        headers={"X-CSRF-Token": member["csrf_token"]},
    )
    assert incident_resp.status_code == 200
    incident_id = incident_resp.json()["id"]

    # incident_responder has incidents.manage -> can attach evidence to an incident.
    incident_evidence_resp = await client.post(
        "/api/evidence",
        json={
            "title": "Firewall log export", "description": "", "evidence_type": "note",
            "target_type": "incident", "target_id": incident_id,
        },
        headers={"X-CSRF-Token": member["csrf_token"]},
    )
    assert incident_evidence_resp.status_code == 200

    # incident_responder has no compliance.manage -> cannot attach evidence to a control.
    control_evidence_resp = await client.post(
        "/api/evidence",
        json={
            "title": "Access review", "description": "", "evidence_type": "note",
            "target_type": "compliance_control", "target_id": control_id,
        },
        headers={"X-CSRF-Token": member["csrf_token"]},
    )
    assert control_evidence_resp.status_code == 403


async def test_evidence_list_and_export_endpoints(client, db):
    ctx = await _connected_owner(
        client, db, org="API Evidence List Co", email="owner@api-evidence-list.example"
    )
    control_id = await _soc2_control_id()
    create_resp = await client.post(
        "/api/evidence",
        json={
            "title": "Policy document", "description": "Signed policy.", "evidence_type": "url",
            "source_url": "https://example.com/policy.pdf", "target_type": "compliance_control",
            "target_id": control_id,
        },
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert create_resp.status_code == 200

    list_resp = await client.get(
        "/api/evidence", params={"target_type": "compliance_control", "target_id": control_id}
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    export_resp = await client.get(
        "/api/evidence/export", params={"target_type": "compliance_control", "target_id": control_id}
    )
    assert export_resp.status_code == 200
    assert len(export_resp.json()["evidence"]) == 1


async def test_document_evidence_upload_and_download_round_trips_real_bytes(client, db):
    ctx = await _connected_owner(
        client, db, org="API Evidence Upload Co", email="owner@api-evidence-upload.example"
    )
    control_id = await _soc2_control_id()
    file_bytes = b"This is a real uploaded evidence file, not a mock.\n" * 20

    create_resp = await client.post(
        "/api/evidence/document",
        data={
            "title": "Firewall config export",
            "description": "Exported from the firewall admin console.",
            "target_type": "compliance_control",
            "target_id": control_id,
        },
        files={"file": ("firewall-config.txt", file_bytes, "text/plain")},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert create_resp.status_code == 200, create_resp.text
    body = create_resp.json()
    assert body["evidence_type"] == "document"
    assert body["file_name"] == "firewall-config.txt"
    assert body["file_size_bytes"] == len(file_bytes)
    evidence_id = body["id"]

    download_resp = await client.get(f"/api/evidence/{evidence_id}/file")
    assert download_resp.status_code == 200
    assert download_resp.content == file_bytes  # real bytes round-trip through real disk I/O
    assert download_resp.headers["content-type"].startswith("text/plain")
    assert "firewall-config.txt" in download_resp.headers["content-disposition"]


async def test_document_evidence_rejects_oversized_file(client, db):
    ctx = await _connected_owner(
        client, db, org="API Evidence Oversize Co", email="owner@api-evidence-oversize.example"
    )
    control_id = await _soc2_control_id()
    too_big = b"x" * (10 * 1024 * 1024 + 1)

    resp = await client.post(
        "/api/evidence/document",
        data={
            "title": "Huge file",
            "target_type": "compliance_control",
            "target_id": control_id,
        },
        files={"file": ("huge.bin", too_big, "application/octet-stream")},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "validation_error"


async def test_deleting_document_evidence_removes_it_and_the_file(client, db):
    ctx = await _connected_owner(
        client, db, org="API Evidence Delete Co", email="owner@api-evidence-delete.example"
    )
    control_id = await _soc2_control_id()
    create_resp = await client.post(
        "/api/evidence/document",
        data={"title": "Temp file", "target_type": "compliance_control", "target_id": control_id},
        files={"file": ("temp.txt", b"temporary", "text/plain")},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    evidence_id = create_resp.json()["id"]

    delete_resp = await client.delete(
        f"/api/evidence/{evidence_id}", headers={"X-CSRF-Token": ctx["csrf_token"]}
    )
    assert delete_resp.status_code == 200

    download_resp = await client.get(f"/api/evidence/{evidence_id}/file")
    assert download_resp.status_code == 404


async def test_document_evidence_file_scoped_to_own_tenant(client, db):
    ctx_a = await _connected_owner(
        client, db, org="Evidence File Iso A Co", email="ownerA@evidence-file-iso-a.example"
    )
    control_id = await _soc2_control_id()
    create_resp = await client.post(
        "/api/evidence/document",
        data={"title": "Tenant A file", "target_type": "compliance_control", "target_id": control_id},
        files={"file": ("secret.txt", b"tenant a secret", "text/plain")},
        headers={"X-CSRF-Token": ctx_a["csrf_token"]},
    )
    evidence_id = create_resp.json()["id"]
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx_a["csrf_token"]})

    await _connected_owner(
        client, db, org="Evidence File Iso B Co", email="ownerB@evidence-file-iso-b.example"
    )
    resp = await client.get(f"/api/evidence/{evidence_id}/file")
    assert resp.status_code == 404


async def test_evidence_scoped_to_own_tenant(client, db):
    ctx_a = await _connected_owner(
        client, db, org="Evidence Iso A Co", email="ownerA@evidence-iso-a.example"
    )
    control_id = await _soc2_control_id()
    await client.post(
        "/api/evidence",
        json={
            "title": "Tenant A evidence", "description": "", "evidence_type": "note",
            "target_type": "compliance_control", "target_id": control_id,
        },
        headers={"X-CSRF-Token": ctx_a["csrf_token"]},
    )
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx_a["csrf_token"]})

    await _connected_owner(client, db, org="Evidence Iso B Co", email="ownerB@evidence-iso-b.example")
    resp = await client.get(
        "/api/evidence", params={"target_type": "compliance_control", "target_id": control_id}
    )
    assert resp.status_code == 200
    assert resp.json() == []
