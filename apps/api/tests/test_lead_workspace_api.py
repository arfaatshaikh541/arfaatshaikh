"""HTTP-level tests for the Lead Workspace routes (Milestone 6) -
specifically the things that can only be exercised through real request
routing, not by calling repository/service functions directly:

- The `/leads/bulk/status`, `/leads/bulk/assign`, `/leads/bulk/tags`
  route-ordering fix - these literal-segment paths collide with
  `/leads/{lead_id}/status` etc. at the same position, and Starlette
  matches routes in registration order. If a `/{lead_id}/...` route were
  registered first, a request to `/leads/bulk/status` would incorrectly
  try to parse "bulk" as a UUID and 422, never reaching the bulk
  endpoint. See `routes.py`'s ordering comment.
- Permission enforcement on the new endpoints (a Read-Only Viewer can
  list/view leads but not mutate them).
- `GET /tenants/members`, the assignment-picker prerequisite.
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


async def test_bulk_status_route_is_not_shadowed_by_lead_id_route(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="bulk-route-owner@example.com", tenant_name="Bulk Route Co"
    )
    # A random, non-existent lead_id: if `/leads/bulk/status` were
    # incorrectly matched against `/leads/{lead_id}/status` with
    # lead_id="bulk", this would 422 (invalid UUID) before ever reaching
    # a real handler. Reaching `bulk_change_status` and failing with 404
    # ("lead not found") instead proves the routing itself is correct.
    resp = await client.post(
        "/leads/bulk/status",
        json={"lead_ids": [str(uuid.uuid4())], "status": "reviewed"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 404, resp.text
    assert "Lead not found" in resp.text


async def test_bulk_assign_route_is_not_shadowed(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="bulk-assign-owner@example.com", tenant_name="Bulk Assign Co"
    )
    resp = await client.post(
        "/leads/bulk/assign",
        json={"lead_ids": [str(uuid.uuid4())], "assigned_to_user_id": str(uuid.uuid4())},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 404, resp.text


async def test_bulk_tags_route_is_not_shadowed(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="bulk-tags-owner@example.com", tenant_name="Bulk Tags Co"
    )
    resp = await client.post(
        "/leads/bulk/tags",
        json={"lead_ids": [str(uuid.uuid4())], "tag": "hot"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 404, resp.text


async def test_meta_statuses_route_is_not_shadowed(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="meta-owner@example.com", tenant_name="Meta Co"
    )
    resp = await client.get("/leads/meta/statuses")
    assert resp.status_code == 200, resp.text
    assert "new" in resp.json()
    assert "converted" in resp.json()


async def test_list_leads_empty_tenant_returns_empty_page(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="empty-owner@example.com", tenant_name="Empty Co"
    )
    resp = await client.get("/leads")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {"items": [], "total": 0, "page": 1, "page_size": 25}


async def test_tenant_members_lists_the_owner(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="members-owner@example.com", tenant_name="Members Co"
    )
    resp = await client.get("/tenants/members")
    assert resp.status_code == 200, resp.text
    members = resp.json()
    assert len(members) == 1
    assert members[0]["email"] == "members-owner@example.com"
    assert members[0]["role_name"] == "Owner"


async def test_read_only_viewer_can_view_but_not_mutate_leads(client, client_factory, smtp_capture):
    tenant = await _register_owner_and_create_tenant(
        client, smtp_capture, email="viewer-perm-owner@example.com", tenant_name="Viewer Perm Co"
    )
    roles = {r["name"]: r["id"] for r in (await client.get("/tenants/roles")).json()}
    invite_resp = await client.post(
        "/tenants/invitations",
        json={"email": "viewer-perm@example.com", "role_id": roles["Read-Only Viewer"]},
        headers=csrf_headers(client),
    )
    assert invite_resp.status_code == 200, invite_resp.text
    invite_body = smtp_capture.latest_body_for("viewer-perm@example.com")
    invite_token = extract_token_from_url(invite_body)

    viewer = client_factory()
    await register_verify_login(
        viewer,
        smtp_capture,
        email="viewer-perm@example.com",
        password=STRONG_PASSWORD,
        full_name="Viewer",
    )
    accept = await viewer.post(
        "/invitations/accept", json={"token": invite_token}, headers=csrf_headers(viewer)
    )
    assert accept.status_code == 200, accept.text
    switch = await viewer.post(
        "/tenants/switch", json={"tenant_id": tenant["id"]}, headers=csrf_headers(viewer)
    )
    assert switch.status_code == 200, switch.text

    # View access works.
    list_resp = await viewer.get("/leads")
    assert list_resp.status_code == 200, list_resp.text

    # Mutating actions are denied.
    fake_lead_id = str(uuid.uuid4())
    status_resp = await viewer.post(
        f"/leads/{fake_lead_id}/status",
        json={"status": "reviewed"},
        headers=csrf_headers(viewer),
    )
    assert status_resp.status_code == 403, status_resp.text

    assign_resp = await viewer.post(
        f"/leads/{fake_lead_id}/assign",
        json={"assigned_to_user_id": str(uuid.uuid4())},
        headers=csrf_headers(viewer),
    )
    assert assign_resp.status_code == 403, assign_resp.text

    note_resp = await viewer.post(
        f"/leads/{fake_lead_id}/notes",
        json={"body": "Should not be allowed."},
        headers=csrf_headers(viewer),
    )
    assert note_resp.status_code == 403, note_resp.text

    bulk_status_resp = await viewer.post(
        "/leads/bulk/status",
        json={"lead_ids": [fake_lead_id], "status": "reviewed"},
        headers=csrf_headers(viewer),
    )
    assert bulk_status_resp.status_code == 403, bulk_status_resp.text


async def test_saved_views_create_list_delete_over_http(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="saved-view-owner@example.com", tenant_name="Saved View Co"
    )
    create_resp = await client.post(
        "/saved-views",
        json={"name": "Hot leads", "filters": {"tag": "hot"}},
        headers=csrf_headers(client),
    )
    assert create_resp.status_code == 200, create_resp.text
    view_id = create_resp.json()["id"]

    list_resp = await client.get("/saved-views")
    assert list_resp.status_code == 200, list_resp.text
    assert len(list_resp.json()) == 1

    delete_resp = await client.delete(f"/saved-views/{view_id}", headers=csrf_headers(client))
    assert delete_resp.status_code == 204, delete_resp.text

    list_resp_after = await client.get("/saved-views")
    assert list_resp_after.json() == []
