from datetime import UTC, datetime, timedelta

from app.tests.conftest import login
from app.tests.factories import add_member, create_tenant_with_owner


def test_render_template_substitutes_known_fields_and_leaves_unknown_literal():
    from app.modules.communications.service import render_template

    rendered = render_template("Hi {{first_name}}, re {{unknown_field}}", {"first_name": "Sara"})
    assert rendered == "Hi Sara, re {{unknown_field}}"


def _create_lead(client, **overrides) -> dict:
    payload = {"first_name": "Client", "last_name": "One", "email": "client.one@testclient.internal"}
    payload.update(overrides)
    response = client.post("/api/tenant/leads", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_lead_assigned_notification_sent_and_logged(client, db_session, fake_email):
    tenant, _owner = create_tenant_with_owner(db_session)
    agent = add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")
    db_session.commit()

    login(client, "owner@test.internal", "OwnerPass!2345")
    template = client.post(
        "/api/tenant/communications/templates",
        json={
            "name": "Lead Assigned", "trigger_event": "lead_assigned", "subject": "Assigned: {{first_name}}",
            "body_text": "You were assigned {{first_name}} {{last_name}} ({{reference_number}}).",
        },
    )
    assert template.status_code == 201, template.text

    client.post(
        "/api/tenant/assignment/rules",
        json={"name": "Round robin", "strategy": "round_robin", "conditions": {}, "eligible_user_ids": [str(agent.id)]},
    )

    lead = _create_lead(client)
    assert client.get(f"/api/tenant/leads/{lead['id']}").json()["assigned_user_id"] == str(agent.id)
    assert any(m["to"] == "agent@test.internal" and "Assigned:" in m["subject"] for m in fake_email.sent)

    logs = client.get("/api/tenant/communications/logs").json()
    assert len(logs) == 1
    assert logs[0]["status"] == "sent"
    assert logs[0]["lead_id"] == lead["id"]


def test_notification_soft_skips_when_communications_module_disabled(client, db_session, fake_email):
    from app.modules.entitlements.service import grant_feature_override

    tenant, _owner = create_tenant_with_owner(db_session)
    agent = add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")
    grant_feature_override(db_session, tenant_id=tenant.id, feature_code="communications", config={"enabled": False}, granted_by=None)
    db_session.commit()

    login(client, "owner@test.internal", "OwnerPass!2345")
    # No template is created here on purpose — a disabled module soft-skips
    # before `send_templated_email` ever looks for one.
    client.post(
        "/api/tenant/assignment/rules",
        json={"name": "Round robin", "strategy": "round_robin", "conditions": {}, "eligible_user_ids": [str(agent.id)]},
    )

    lead = _create_lead(client)
    assert client.get(f"/api/tenant/leads/{lead['id']}").json()["assigned_user_id"] == str(agent.id)  # assignment still happened
    assert fake_email.sent == []  # but the notification was soft-skipped, not sent


def test_notification_soft_skips_when_messages_usage_limit_exceeded(client, db_session, fake_email):
    from app.modules.entitlements.service import grant_feature_override

    tenant, _owner = create_tenant_with_owner(db_session)
    agent = add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")
    db_session.commit()

    login(client, "owner@test.internal", "OwnerPass!2345")
    client.post(
        "/api/tenant/communications/templates",
        json={"name": "Lead Assigned", "trigger_event": "lead_assigned", "subject": "Assigned", "body_text": "Assigned."},
    )
    client.post(
        "/api/tenant/assignment/rules",
        json={"name": "Round robin", "strategy": "round_robin", "conditions": {}, "eligible_user_ids": [str(agent.id)]},
    )
    grant_feature_override(db_session, tenant_id=tenant.id, feature_code="messages", config={"limit": 0}, granted_by=None)
    db_session.commit()

    lead = _create_lead(client)
    assert client.get(f"/api/tenant/leads/{lead['id']}").json()["assigned_user_id"] == str(agent.id)
    assert fake_email.sent == []


def test_retry_failed_deliveries_transitions_to_sent(client, db_session, fake_email, monkeypatch):
    import app.core.email as email_module
    from app.modules.communications.service import retry_failed_deliveries
    from app.tests.fakes import FailingEmailProvider

    tenant, _owner = create_tenant_with_owner(db_session)
    agent = add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")
    db_session.commit()

    login(client, "owner@test.internal", "OwnerPass!2345")
    client.post(
        "/api/tenant/communications/templates",
        json={"name": "Lead Assigned", "trigger_event": "lead_assigned", "subject": "Assigned", "body_text": "Assigned."},
    )
    client.post(
        "/api/tenant/assignment/rules",
        json={"name": "Round robin", "strategy": "round_robin", "conditions": {}, "eligible_user_ids": [str(agent.id)]},
    )

    # Patch the module-global singleton, not `get_email_provider` itself —
    # `communications.service` imported that function by reference, so it
    # reads/writes the same `app.core.email._provider` global regardless
    # of which module's name it's called through.
    monkeypatch.setattr(email_module, "_provider", FailingEmailProvider())
    lead = _create_lead(client)

    logs = client.get("/api/tenant/communications/logs").json()
    assert len(logs) == 1
    assert logs[0]["status"] == "failed"
    assert logs[0]["attempt_count"] == 1

    monkeypatch.setattr(email_module, "_provider", fake_email)
    retried = retry_failed_deliveries(db_session, tenant_id=tenant.id, max_attempts=3)
    assert retried == 1

    logs_after = client.get("/api/tenant/communications/logs").json()
    assert logs_after[0]["status"] == "sent"
    assert logs_after[0]["attempt_count"] == 2
    assert any(m["to"] == "agent@test.internal" for m in fake_email.sent)
    assert lead["id"]  # sanity: same lead throughout


def test_send_test_always_targets_requesting_users_own_email(client, db_session, fake_email):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    template = client.post(
        "/api/tenant/communications/templates",
        json={"name": "Lead Assigned", "trigger_event": "lead_assigned", "subject": "Hi {{first_name}}", "body_text": "Body"},
    )
    template_id = template.json()["id"]

    response = client.post(f"/api/tenant/communications/templates/{template_id}/send-test")
    assert response.status_code == 200
    assert response.json()["recipient"] == "owner@test.internal"
    assert any(m["to"] == "owner@test.internal" and m["subject"].startswith("[TEST]") for m in fake_email.sent)


def test_task_reminder_sent_once_and_idempotent(client, db_session, fake_email):
    from app.modules.communications.service import send_task_reminders_for_tenant

    tenant, _owner = create_tenant_with_owner(db_session)
    agent = add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")
    db_session.commit()

    login(client, "owner@test.internal", "OwnerPass!2345")
    client.post(
        "/api/tenant/communications/templates",
        json={"name": "Task Reminder", "trigger_event": "task_reminder", "subject": "Reminder: {{task_title}}", "body_text": "Due {{task_due_date}}"},
    )

    lead = _create_lead(client)
    task = client.post(
        f"/api/tenant/leads/{lead['id']}/tasks",
        json={"title": "Call the client", "assigned_user_id": str(agent.id), "due_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat()},
    )
    assert task.status_code == 201

    cutoff = datetime.now(UTC)
    first_run = send_task_reminders_for_tenant(db_session, tenant_id=tenant.id, before=cutoff)
    assert first_run == 1
    assert any(m["to"] == "agent@test.internal" and "Call the client" in m["subject"] for m in fake_email.sent)

    second_run = send_task_reminders_for_tenant(db_session, tenant_id=tenant.id, before=cutoff)
    assert second_run == 0  # already reminded — idempotent


def test_communications_manage_requires_permission(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session)
    add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")

    login(client, "agent@test.internal", "AgentPass!2345")
    response = client.post(
        "/api/tenant/communications/templates",
        json={"name": "X", "trigger_event": "manual", "subject": "X", "body_text": "X"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"
