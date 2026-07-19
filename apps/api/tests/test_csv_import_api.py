"""HTTP-level tests for the CSV Import routes (Milestone 8):
`campaigns.create` gates uploading/starting an import (the same tier of
user who launches a campaign - CSV import is another way of getting
businesses into the system), `campaigns.view` gates reading status. The
actual row-processing pipeline is exercised end-to-end in
`apps/worker/tests/test_csv_import_tasks.py` (no worker process consumes
the queued task in these tests, so a started import stays "queued").
"""

import pytest

from tests.helpers import csrf_headers, extract_token_from_url, register_verify_login

pytestmark = pytest.mark.asyncio

STRONG_PASSWORD = "CorrectHorse9Battery"

SAMPLE_CSV = (
    b"Business Name,City,Phone\n"
    b"Blue Bottle Cafe,Austin,+1-512-555-0100\n"
    b"Golden Spoon Diner,Austin,+1-512-555-0101\n"
)


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


async def _upload(client, *, content: bytes = SAMPLE_CSV, filename: str = "businesses.csv"):
    return await client.post(
        "/imports",
        files={"file": (filename, content, "text/csv")},
        headers=csrf_headers(client),
    )


async def test_upload_returns_preview_with_headers_and_sample_rows(client, smtp_capture, moto_s3):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="imports-owner@example.com", tenant_name="Imports Co"
    )
    resp = await _upload(client)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "mapping_required"
    assert body["detected_headers"] == ["Business Name", "City", "Phone"]
    assert body["row_count"] == 2
    assert len(body["sample_rows"]) == 2
    assert "name" in body["mappable_fields"]
    assert "email" not in body["mappable_fields"]


async def test_start_import_without_name_mapping_is_rejected(client, smtp_capture, moto_s3):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="imports-noname-owner@example.com", tenant_name="No Name Co"
    )
    preview = (await _upload(client)).json()
    resp = await client.post(
        f"/imports/{preview['id']}/start",
        json={"column_mapping": {"city": "City"}},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 422, resp.text


async def test_start_import_with_unknown_mapped_column_is_rejected(client, smtp_capture, moto_s3):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="imports-badcol-owner@example.com", tenant_name="Bad Col Co"
    )
    preview = (await _upload(client)).json()
    resp = await client.post(
        f"/imports/{preview['id']}/start",
        json={"column_mapping": {"name": "Nonexistent Column"}},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 422, resp.text


async def test_start_import_with_valid_mapping_reserves_credits_and_queues(
    client, smtp_capture, moto_s3
):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="imports-start-owner@example.com", tenant_name="Start Co"
    )
    wallet_before = (await client.get("/usage/wallet")).json()

    preview = (await _upload(client)).json()
    resp = await client.post(
        f"/imports/{preview['id']}/start",
        json={"column_mapping": {"name": "Business Name", "city": "City", "phone": "Phone"}},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "queued"

    wallet_after = (await client.get("/usage/wallet")).json()
    # Reserved (not yet debited) - available balance drops, total
    # balance doesn't, mirroring how campaign launch's estimate
    # reservation behaves.
    assert wallet_after["balance"] == wallet_before["balance"]
    assert wallet_after["available"] == wallet_before["available"] - 2.0


async def test_starting_an_already_started_import_is_conflict(client, smtp_capture, moto_s3):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="imports-restart-owner@example.com", tenant_name="Restart Co"
    )
    preview = (await _upload(client)).json()
    mapping = {"column_mapping": {"name": "Business Name"}}
    first = await client.post(
        f"/imports/{preview['id']}/start", json=mapping, headers=csrf_headers(client)
    )
    assert first.status_code == 200, first.text

    second = await client.post(
        f"/imports/{preview['id']}/start", json=mapping, headers=csrf_headers(client)
    )
    assert second.status_code == 409, second.text


async def test_list_and_get_csv_import(client, smtp_capture, moto_s3):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="imports-list-owner@example.com", tenant_name="List Co"
    )
    preview = (await _upload(client)).json()

    list_resp = await client.get("/imports")
    assert list_resp.status_code == 200, list_resp.text
    assert any(i["id"] == preview["id"] for i in list_resp.json()["imports"])

    get_resp = await client.get(f"/imports/{preview['id']}")
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["original_filename"] == "businesses.csv"


async def test_sales_representative_cannot_upload_or_view_imports(
    client, client_factory, smtp_capture, moto_s3
):
    tenant = await _register_owner_and_create_tenant(
        client, smtp_capture, email="imports-rep-owner@example.com", tenant_name="Rep Perm Co"
    )
    rep = await _invite_and_login_as(
        client,
        client_factory,
        smtp_capture,
        tenant_id=tenant["id"],
        role_name="Sales Representative",
        email="imports-rep@example.com",
    )

    upload_resp = await _upload(rep)
    assert upload_resp.status_code == 403, upload_resp.text

    list_resp = await rep.get("/imports")
    assert list_resp.status_code == 403, list_resp.text


async def test_campaign_manager_can_upload_and_view_imports(
    client, client_factory, smtp_capture, moto_s3
):
    tenant = await _register_owner_and_create_tenant(
        client, smtp_capture, email="imports-cm-owner@example.com", tenant_name="CM Perm Co"
    )
    campaign_manager = await _invite_and_login_as(
        client,
        client_factory,
        smtp_capture,
        tenant_id=tenant["id"],
        role_name="Campaign Manager",
        email="imports-cm@example.com",
    )

    upload_resp = await _upload(campaign_manager)
    assert upload_resp.status_code == 200, upload_resp.text

    list_resp = await campaign_manager.get("/imports")
    assert list_resp.status_code == 200, list_resp.text
