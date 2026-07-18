"""HTTP-level tests for the Exports routes (Milestone 7):
`leads.export` gates `POST /exports`, `exports.view` gates
`GET /exports`/`GET /exports/{id}`/`GET /exports/{id}/download`, request
validation (format, mutually-exclusive lead_ids/filters), and that a
download is refused until the export actually completes - the Celery
task itself is exercised end-to-end in `apps/worker/tests/
test_export_tasks.py`, not here (no worker process consumes the queued
task in these tests, so every export created here stays "pending").
"""

import uuid

import pytest

from tests.helpers import csrf_headers, extract_token_from_url, register_verify_login

pytestmark = pytest.mark.asyncio

STRONG_PASSWORD = "CorrectHorse9Battery"


async def _register_owner_and_create_tenant(client, smtp_capture, *, email: str, tenant_name: str):
    await register_verify_login(
        client, smtp_capture, email=email, password=STRONG_PASSWORD, full_name="Owner"
    )
    resp = await client.post("/tenants", json={"name": tenant_name}, headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _invite_and_login_as(
    owner_client, client_factory, smtp_capture, *, tenant_id, role_name, email
):
    roles = {r["name"]: r["id"] for r in (await owner_client.get("/tenants/roles")).json()}
    invite_resp = await owner_client.post(
        "/tenants/invitations",
        json={"email": email, "role_id": roles[role_name]},
        headers=csrf_headers(owner_client),
    )
    assert invite_resp.status_code == 200, invite_resp.text
    invite_token = extract_token_from_url(smtp_capture.latest_body_for(email))

    member = client_factory()
    await register_verify_login(
        member, smtp_capture, email=email, password=STRONG_PASSWORD, full_name="Member"
    )
    accept = await member.post(
        "/invitations/accept", json={"token": invite_token}, headers=csrf_headers(member)
    )
    assert accept.status_code == 200, accept.text
    switch = await member.post(
        "/tenants/switch", json={"tenant_id": str(tenant_id)}, headers=csrf_headers(member)
    )
    assert switch.status_code == 200, switch.text
    return member


async def test_create_export_by_owner_succeeds_and_is_listed(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="exports-owner@example.com", tenant_name="Exports Co"
    )
    resp = await client.post(
        "/exports",
        json={"format": "xlsx", "lead_ids": [str(uuid.uuid4())]},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["format"] == "xlsx"
    assert body["status"] == "pending"

    list_resp = await client.get("/exports")
    assert list_resp.status_code == 200, list_resp.text
    exports = list_resp.json()["exports"]
    assert any(e["id"] == body["id"] for e in exports)

    get_resp = await client.get(f"/exports/{body['id']}")
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["id"] == body["id"]


async def test_create_export_with_filters_instead_of_lead_ids(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="exports-filters-owner@example.com", tenant_name="Filters Co"
    )
    resp = await client.post(
        "/exports",
        json={"format": "csv", "filters": {"status": ["new", "qualified"], "min_score": 50}},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["format"] == "csv"


async def test_create_export_rejects_both_lead_ids_and_filters(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="exports-both-owner@example.com", tenant_name="Both Co"
    )
    resp = await client.post(
        "/exports",
        json={
            "format": "xlsx",
            "lead_ids": [str(uuid.uuid4())],
            "filters": {"status": ["new"]},
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 422, resp.text


async def test_create_export_rejects_invalid_format(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="exports-badformat-owner@example.com", tenant_name="Bad Fmt Co"
    )
    resp = await client.post(
        "/exports",
        json={"format": "pdf", "lead_ids": [str(uuid.uuid4())]},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 422, resp.text


async def test_download_before_completion_is_conflict(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="exports-download-owner@example.com", tenant_name="Download Co"
    )
    create_resp = await client.post(
        "/exports",
        json={"format": "xlsx", "lead_ids": [str(uuid.uuid4())]},
        headers=csrf_headers(client),
    )
    export_id = create_resp.json()["id"]

    download_resp = await client.get(f"/exports/{export_id}/download")
    assert download_resp.status_code == 409, download_resp.text


async def test_sales_representative_cannot_create_or_list_exports(
    client, client_factory, smtp_capture
):
    tenant = await _register_owner_and_create_tenant(
        client, smtp_capture, email="exports-rep-owner@example.com", tenant_name="Rep Perm Co"
    )
    rep = await _invite_and_login_as(
        client,
        client_factory,
        smtp_capture,
        tenant_id=tenant["id"],
        role_name="Sales Representative",
        email="exports-rep@example.com",
    )

    create_resp = await rep.post(
        "/exports",
        json={"format": "xlsx", "lead_ids": [str(uuid.uuid4())]},
        headers=csrf_headers(rep),
    )
    assert create_resp.status_code == 403, create_resp.text

    list_resp = await rep.get("/exports")
    assert list_resp.status_code == 403, list_resp.text


async def test_analyst_can_create_and_view_exports(client, client_factory, smtp_capture):
    tenant = await _register_owner_and_create_tenant(
        client, smtp_capture, email="exports-analyst-owner@example.com", tenant_name="Analyst Co"
    )
    analyst = await _invite_and_login_as(
        client,
        client_factory,
        smtp_capture,
        tenant_id=tenant["id"],
        role_name="Analyst",
        email="exports-analyst@example.com",
    )

    create_resp = await analyst.post(
        "/exports",
        json={"format": "csv", "lead_ids": [str(uuid.uuid4())]},
        headers=csrf_headers(analyst),
    )
    assert create_resp.status_code == 200, create_resp.text

    list_resp = await analyst.get("/exports")
    assert list_resp.status_code == 200, list_resp.text
