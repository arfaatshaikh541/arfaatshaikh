from app.services.message_template_service import render_template
from tests.factories import add_member, login, make_tenant_with_owner


def test_render_template_never_evaluates_expressions():
    """Regression guard for the "no eval/exec" requirement: only
    ``{{identifier}}`` placeholders are substituted from the supplied
    context dict. Non-identifier expressions never match the pattern (so
    stay literal), and unknown identifiers - like the class-attribute-style
    ``__class__`` a code-injection attempt might try - are never resolved
    against the object itself, only against the plain string context."""
    rendered = render_template(
        "Hello {{first_name}}, {{7*7}} stays literal but {{__class__}} is blank.",
        {"first_name": "Sam"},
    )
    assert "49" not in rendered
    assert "<class" not in rendered
    assert rendered == "Hello Sam, {{7*7}} stays literal but  is blank."


def test_render_template_unknown_variable_renders_empty():
    rendered = render_template("Ref: {{lead_id}}, extra: {{does_not_exist}}", {"lead_id": "LD-1"})
    assert rendered == "Ref: LD-1, extra: "


def test_message_template_crud(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    create_resp = client.post(
        "/api/tenants/me/message-templates",
        json={
            "key": "follow_up",
            "subject": "Checking in, {{first_name}}",
            "body": "Hi {{first_name}}, just checking in.",
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert create_resp.status_code == 201
    template_id = create_resp.json()["id"]

    update_resp = client.patch(
        f"/api/tenants/me/message-templates/{template_id}",
        json={"subject": "Updated subject"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["subject"] == "Updated subject"

    list_resp = client.get(
        "/api/tenants/me/message-templates", headers={"X-Tenant-Id": str(tenant.id)}
    )
    assert any(t["id"] == template_id for t in list_resp.json())


def test_message_template_requires_permission(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    viewer, _m = add_member(db_session, tenant, role_slug="viewer")
    csrf = login(client, viewer.email)
    resp = client.post(
        "/api/tenants/me/message-templates",
        json={"key": "follow_up", "subject": "x", "body": "y"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 403


def test_message_template_rejects_duplicate_key(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    payload = {"key": "follow_up", "subject": "x", "body": "y"}
    first = client.post(
        "/api/tenants/me/message-templates",
        json=payload,
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/tenants/me/message-templates",
        json=payload,
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert second.status_code == 422


def test_lead_assignment_creates_notification_for_assignee(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    agent, agent_membership = add_member(db_session, tenant, role_slug="sales_agent")
    owner_csrf = login(client, owner.email)

    lead_id = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "Notify"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": owner_csrf},
    ).json()["id"]
    client.post(
        f"/api/tenants/me/leads/{lead_id}/assign",
        json={"membership_id": str(agent_membership.id)},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": owner_csrf},
    )

    # Manual assignment via LeadService.assign() does not itself emit a
    # notification (only the automatic assignment engine path does) - so
    # exercise auto-assignment via a round-robin rule instead.
    client.post(
        "/api/tenants/me/assignment-rules",
        json={
            "name": "RR",
            "strategy": "round_robin",
            "config": {"membership_ids": [str(agent_membership.id)]},
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": owner_csrf},
    )
    client.post(
        "/api/tenants/me/leads",
        json={"first_name": "AutoAssigned"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": owner_csrf},
    )

    agent_csrf = login(client, agent.email)
    notifications_resp = client.get(
        "/api/tenants/me/notifications", headers={"X-Tenant-Id": str(tenant.id)}
    )
    assert notifications_resp.status_code == 200
    notifications = notifications_resp.json()
    assert any(n["title"] == "New lead assigned to you" for n in notifications)
    assert all(n["is_read"] is False for n in notifications)

    unread_resp = client.get(
        "/api/tenants/me/notifications/unread-count", headers={"X-Tenant-Id": str(tenant.id)}
    )
    assert unread_resp.json()["count"] >= 1

    notification_id = notifications[0]["id"]
    read_resp = client.post(
        f"/api/tenants/me/notifications/{notification_id}/read",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": agent_csrf},
    )
    assert read_resp.status_code == 200
    assert read_resp.json()["is_read"] is True


def test_notifications_are_isolated_per_user(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    agent, agent_membership = add_member(db_session, tenant, role_slug="sales_agent")
    owner_csrf = login(client, owner.email)

    client.post(
        "/api/tenants/me/assignment-rules",
        json={
            "name": "RR",
            "strategy": "round_robin",
            "config": {"membership_ids": [str(agent_membership.id)]},
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": owner_csrf},
    )
    client.post(
        "/api/tenants/me/leads",
        json={"first_name": "ForAgent"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": owner_csrf},
    )

    owner_notifications = client.get(
        "/api/tenants/me/notifications", headers={"X-Tenant-Id": str(tenant.id)}
    ).json()
    assert owner_notifications == []
