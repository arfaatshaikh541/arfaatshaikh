import pytest

from tests.helpers import csrf_headers, extract_token_from_url, register_verify_login

pytestmark = pytest.mark.asyncio

STRONG_PASSWORD = "CorrectHorse9Battery"


async def test_create_tenant_grants_owner_full_permissions(client, smtp_capture):
    await register_verify_login(
        client,
        smtp_capture,
        email="owner1@example.com",
        password=STRONG_PASSWORD,
        full_name="Owner One",
    )
    create_resp = await client.post(
        "/tenants", json={"name": "Acme Corp"}, headers=csrf_headers(client)
    )
    assert create_resp.status_code == 200, create_resp.text
    tenant = create_resp.json()
    assert tenant["slug"] == "acme-corp"
    assert tenant["status"] == "trial"

    roles_resp = await client.get("/tenants/roles")
    assert roles_resp.status_code == 200
    role_names = {r["name"] for r in roles_resp.json()}
    assert role_names == {
        "Owner",
        "Administrator",
        "Campaign Manager",
        "Sales Manager",
        "Sales Representative",
        "Analyst",
        "Billing Manager",
        "Read-Only Viewer",
    }

    wallet_resp = await client.get("/usage/wallet")
    assert wallet_resp.status_code == 200
    assert wallet_resp.json()["balance"] == 0.0

    sub_resp = await client.get("/billing/subscription")
    assert sub_resp.status_code == 200
    assert sub_resp.json()["plan_key"] == "trial"

    audit_resp = await client.get("/audit/logs")
    assert audit_resp.status_code == 200
    actions = [a["action"] for a in audit_resp.json()]
    assert "tenant.created" in actions


async def test_invited_read_only_viewer_cannot_manage_users_or_billing(
    client, client_factory, smtp_capture
):
    await register_verify_login(
        client,
        smtp_capture,
        email="owner2@example.com",
        password=STRONG_PASSWORD,
        full_name="Owner Two",
    )
    create_resp = await client.post(
        "/tenants", json={"name": "Beta Inc"}, headers=csrf_headers(client)
    )
    assert create_resp.status_code == 200

    roles = {r["name"]: r["id"] for r in (await client.get("/tenants/roles")).json()}

    invite_resp = await client.post(
        "/tenants/invitations",
        json={"email": "viewer2@example.com", "role_id": roles["Read-Only Viewer"]},
        headers=csrf_headers(client),
    )
    assert invite_resp.status_code == 200, invite_resp.text

    invite_token = extract_token_from_url(
        smtp_capture.latest_body_for("viewer2@example.com"), "token"
    )

    viewer_client = client_factory()
    await register_verify_login(
        viewer_client,
        smtp_capture,
        email="viewer2@example.com",
        password=STRONG_PASSWORD,
        full_name="Viewer Two",
    )
    accept_resp = await viewer_client.post(
        "/invitations/accept", json={"token": invite_token}, headers=csrf_headers(viewer_client)
    )
    assert accept_resp.status_code == 200, accept_resp.text

    switch_resp = await viewer_client.post(
        "/tenants/switch",
        json={"tenant_id": create_resp.json()["id"]},
        headers=csrf_headers(viewer_client),
    )
    assert switch_resp.status_code == 200

    # Read-only viewer CAN view leads/campaigns-equivalent read endpoints...
    tenant_view = await viewer_client.get("/tenants/current")
    assert tenant_view.status_code == 200

    # ...but cannot manage users or billing (permission_denied, not just a 404).
    denied_invite = await viewer_client.post(
        "/tenants/invitations",
        json={"email": "someone-else@example.com", "role_id": roles["Analyst"]},
        headers=csrf_headers(viewer_client),
    )
    assert denied_invite.status_code == 403
    assert denied_invite.json()["error"]["code"] == "permission_denied"

    denied_billing = await viewer_client.get("/billing/subscription")
    assert denied_billing.status_code == 403


async def test_tenant_switch_rejects_tenant_the_user_is_not_a_member_of(
    client, client_factory, smtp_capture
):
    await register_verify_login(
        client,
        smtp_capture,
        email="owner3@example.com",
        password=STRONG_PASSWORD,
        full_name="Owner Three",
    )
    await client.post("/tenants", json={"name": "Gamma LLC"}, headers=csrf_headers(client))

    outsider = client_factory()
    await register_verify_login(
        outsider,
        smtp_capture,
        email="outsider@example.com",
        password=STRONG_PASSWORD,
        full_name="Outsider",
    )
    other_tenant_resp = await outsider.post(
        "/tenants", json={"name": "Delta Co"}, headers=csrf_headers(outsider)
    )
    other_tenant_id = other_tenant_resp.json()["id"]

    # `client` (owner of Gamma LLC) tries to switch into a tenant it has no
    # membership in - the server must reject this using its own recorded
    # memberships, never trusting the tenant_id as sufficient by itself.
    forged_switch = await client.post(
        "/tenants/switch", json={"tenant_id": other_tenant_id}, headers=csrf_headers(client)
    )
    assert forged_switch.status_code == 403
    assert forged_switch.json()["error"]["code"] == "tenant_access_denied"


async def test_invitation_blocked_once_plan_member_limit_reached(client, smtp_capture):
    """The trial plan seeded in Milestone 1 caps max_team_members at 3. The
    tenant starts with 1 member (the Owner), so 2 more invitations should
    succeed and the 3rd should be blocked by the entitlement resolver -
    never by a frontend-computed check."""
    await register_verify_login(
        client,
        smtp_capture,
        email="owner4@example.com",
        password=STRONG_PASSWORD,
        full_name="Owner Four",
    )
    await client.post("/tenants", json={"name": "Epsilon Ltd"}, headers=csrf_headers(client))
    roles = {r["name"]: r["id"] for r in (await client.get("/tenants/roles")).json()}

    ok1 = await client.post(
        "/tenants/invitations",
        json={"email": "member1@example.com", "role_id": roles["Analyst"]},
        headers=csrf_headers(client),
    )
    assert ok1.status_code == 200, ok1.text

    ok2 = await client.post(
        "/tenants/invitations",
        json={"email": "member2@example.com", "role_id": roles["Analyst"]},
        headers=csrf_headers(client),
    )
    assert ok2.status_code == 200, ok2.text

    blocked = await client.post(
        "/tenants/invitations",
        json={"email": "member3@example.com", "role_id": roles["Analyst"]},
        headers=csrf_headers(client),
    )
    assert blocked.status_code == 402
    assert blocked.json()["error"]["code"] == "entitlement_denied"


async def test_mutating_request_without_csrf_header_is_rejected(client, smtp_capture):
    await register_verify_login(
        client,
        smtp_capture,
        email="csrftest@example.com",
        password=STRONG_PASSWORD,
        full_name="Csrf Test",
    )
    resp = await client.post("/tenants", json={"name": "No CSRF Header Co"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "csrf_validation_failed"
