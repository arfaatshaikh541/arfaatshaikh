"""HTTP-level tests for the Integrations routes (Milestone 8):
`integrations.manage` gates CRUD on an `Integration`, `integrations.view`
gates using one (pushing a lead, listing deliveries) - the actual webhook
delivery itself is exercised end-to-end in `apps/worker/tests/
test_integration_tasks.py` (no worker process consumes the queued task in
these tests, so every push created here stays "pending").
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


async def _create_integration(client, *, name="Test Webhook", url="https://example.com/hook"):
    return await client.post(
        "/integrations",
        json={"name": name, "webhook_url": url, "webhook_secret": "a-real-secret-value"},
        headers=csrf_headers(client),
    )


async def test_owner_can_create_list_get_update_delete_integration(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="integrations-owner@example.com", tenant_name="Integrations Co"
    )
    create_resp = await _create_integration(client)
    assert create_resp.status_code == 200, create_resp.text
    body = create_resp.json()
    assert body["name"] == "Test Webhook"
    assert body["webhook_url"] == "https://example.com/hook"
    assert body["enabled"] is True
    assert "webhook_secret" not in body
    assert "webhook_secret_encrypted" not in body

    list_resp = await client.get("/integrations")
    assert list_resp.status_code == 200, list_resp.text
    assert any(i["id"] == body["id"] for i in list_resp.json()["integrations"])

    get_resp = await client.get(f"/integrations/{body['id']}")
    assert get_resp.status_code == 200, get_resp.text

    update_resp = await client.patch(
        f"/integrations/{body['id']}",
        json={"enabled": False},
        headers=csrf_headers(client),
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["enabled"] is False

    delete_resp = await client.delete(f"/integrations/{body['id']}", headers=csrf_headers(client))
    assert delete_resp.status_code == 204, delete_resp.text

    get_after_delete = await client.get(f"/integrations/{body['id']}")
    assert get_after_delete.status_code == 404


async def test_create_integration_rejects_invalid_webhook_url_scheme(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client,
        smtp_capture,
        email="integrations-badurl-owner@example.com",
        tenant_name="Bad URL Co",
    )
    resp = await client.post(
        "/integrations",
        json={
            "name": "Bad Scheme",
            "webhook_url": "ftp://example.com/hook",
            "webhook_secret": "a-real-secret-value",
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 422, resp.text


async def test_push_to_disabled_integration_is_conflict(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client,
        smtp_capture,
        email="integrations-disabled-owner@example.com",
        tenant_name="Disabled Co",
    )
    create_resp = await _create_integration(client)
    integration_id = create_resp.json()["id"]
    await client.patch(
        f"/integrations/{integration_id}", json={"enabled": False}, headers=csrf_headers(client)
    )

    push_resp = await client.post(
        f"/integrations/{integration_id}/push/{uuid.uuid4()}", headers=csrf_headers(client)
    )
    assert push_resp.status_code == 409, push_resp.text


async def test_bulk_push_route_is_not_shadowed_by_lead_id_route(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client,
        smtp_capture,
        email="integrations-bulk-owner@example.com",
        tenant_name="Bulk Push Co",
    )
    create_resp = await _create_integration(client)
    integration_id = create_resp.json()["id"]

    # A random, non-existent lead id: if `/push/bulk` were incorrectly
    # matched against `/push/{lead_id}` with lead_id="bulk", this would
    # 422 (invalid UUID) before ever reaching the bulk handler. Reaching
    # `bulk_push_leads` and failing with 404 ("lead not found") instead
    # proves the routing itself is correct - same fix class as ADR-0014.
    resp = await client.post(
        f"/integrations/{integration_id}/push/bulk",
        json={"lead_ids": [str(uuid.uuid4())]},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 404, resp.text
    assert "Lead not found" in resp.text


async def test_sales_manager_can_view_and_push_but_not_manage_integrations(
    client, client_factory, smtp_capture
):
    tenant = await _register_owner_and_create_tenant(
        client, smtp_capture, email="integrations-sm-owner@example.com", tenant_name="SM Perm Co"
    )
    create_resp = await _create_integration(client)
    integration_id = create_resp.json()["id"]

    sales_manager = await _invite_and_login_as(
        client,
        client_factory,
        smtp_capture,
        tenant_id=tenant["id"],
        role_name="Sales Manager",
        email="integrations-sm@example.com",
    )

    list_resp = await sales_manager.get("/integrations")
    assert list_resp.status_code == 200, list_resp.text

    push_resp = await sales_manager.post(
        f"/integrations/{integration_id}/push/{uuid.uuid4()}", headers=csrf_headers(sales_manager)
    )
    assert push_resp.status_code == 404, (
        push_resp.text
    )  # routed and permitted; lead just doesn't exist

    create_attempt = await _create_integration(sales_manager, name="Should Fail")
    assert create_attempt.status_code == 403, create_attempt.text

    delete_attempt = await sales_manager.delete(
        f"/integrations/{integration_id}", headers=csrf_headers(sales_manager)
    )
    assert delete_attempt.status_code == 403, delete_attempt.text


async def test_sales_representative_cannot_view_or_push_integrations(
    client, client_factory, smtp_capture
):
    tenant = await _register_owner_and_create_tenant(
        client, smtp_capture, email="integrations-rep-owner@example.com", tenant_name="Rep Perm Co"
    )
    create_resp = await _create_integration(client)
    integration_id = create_resp.json()["id"]

    rep = await _invite_and_login_as(
        client,
        client_factory,
        smtp_capture,
        tenant_id=tenant["id"],
        role_name="Sales Representative",
        email="integrations-rep@example.com",
    )

    list_resp = await rep.get("/integrations")
    assert list_resp.status_code == 403, list_resp.text

    push_resp = await rep.post(
        f"/integrations/{integration_id}/push/{uuid.uuid4()}", headers=csrf_headers(rep)
    )
    assert push_resp.status_code == 403, push_resp.text
