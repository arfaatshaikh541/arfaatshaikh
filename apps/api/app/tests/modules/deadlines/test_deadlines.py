from datetime import date, timedelta

from app.tests.conftest import login
from app.tests.factories import add_member, create_tenant_with_owner


def _create_lead(client, **overrides) -> dict:
    payload = {"first_name": "Client", "last_name": "One", "email": "client.one@testclient.internal"}
    payload.update(overrides)
    response = client.post("/api/tenant/leads", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _create_deadline(client, lead_id: str, **overrides) -> dict:
    payload = {"lead_id": lead_id, "title": "Trade license renewal", "due_date": (date.today() + timedelta(days=30)).isoformat()}
    payload.update(overrides)
    response = client.post("/api/tenant/deadlines", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_complete_deadline_without_recurrence(client, db_session):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    deadline = _create_deadline(client, lead["id"])
    assert deadline["status"] == "open"

    complete = client.post(f"/api/tenant/deadlines/{deadline['id']}/complete")
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"

    all_deadlines = client.get(f"/api/tenant/deadlines?lead_id={lead['id']}").json()
    assert len(all_deadlines) == 1  # no recurrence configured, no next occurrence created


def test_completing_recurring_deadline_creates_next_occurrence(client, db_session):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    due_date = date.today() + timedelta(days=10)
    deadline = _create_deadline(client, lead["id"], due_date=due_date.isoformat(), recurrence_interval_days=365)

    complete = client.post(f"/api/tenant/deadlines/{deadline['id']}/complete")
    assert complete.status_code == 200

    all_deadlines = client.get(f"/api/tenant/deadlines?lead_id={lead['id']}").json()
    assert len(all_deadlines) == 2
    next_occurrence = next(d for d in all_deadlines if d["status"] == "open")
    assert next_occurrence["due_date"] == (due_date + timedelta(days=365)).isoformat()
    assert next_occurrence["recurrence_interval_days"] == 365


def test_cannot_complete_already_completed_deadline(client, db_session):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    deadline = _create_deadline(client, lead["id"])
    client.post(f"/api/tenant/deadlines/{deadline['id']}/complete")

    second_complete = client.post(f"/api/tenant/deadlines/{deadline['id']}/complete")
    assert second_complete.status_code == 422
    assert second_complete.json()["error"]["code"] == "deadline_already_completed"


def test_deadline_reminder_sweep_sends_email(client, db_session, fake_email):
    from app.modules.deadlines.service import send_deadline_reminders_for_tenant

    tenant, _owner = create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")
    client.post(
        "/api/tenant/communications/templates",
        json={
            "name": "Deadline Reminder", "trigger_event": "deadline_upcoming",
            "subject": "Reminder: {{deadline_title}}", "body_text": "Your deadline '{{deadline_title}}' is due {{deadline_due_date}}.",
        },
    )

    lead = _create_lead(client)
    due_date = date.today() + timedelta(days=3)
    _create_deadline(client, lead["id"], due_date=due_date.isoformat())

    reminded = send_deadline_reminders_for_tenant(db_session, tenant_id=tenant.id, on_or_before=date.today() + timedelta(days=7))
    assert reminded == 1
    assert any(m["to"] == "client.one@testclient.internal" and "Trade license" in m["subject"] for m in fake_email.sent)

    # A second sweep pass must not double-send.
    reminded_again = send_deadline_reminders_for_tenant(db_session, tenant_id=tenant.id, on_or_before=date.today() + timedelta(days=7))
    assert reminded_again == 0


def test_sales_agent_cannot_manage_deadlines(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session, plan_code="professional")
    add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")

    login(client, "agent@test.internal", "AgentPass!2345")
    list_response = client.get("/api/tenant/deadlines")
    assert list_response.status_code == 403
    assert list_response.json()["error"]["code"] == "permission_denied"


def test_deadlines_are_isolated_between_tenants(client, db_session):
    create_tenant_with_owner(db_session, name="Tenant A", owner_email="ownera@test.internal", plan_code="professional")
    create_tenant_with_owner(db_session, name="Tenant B", owner_email="ownerb@test.internal", plan_code="professional")

    login(client, "ownera@test.internal", "OwnerPass!2345")
    lead = _create_lead(client)
    _create_deadline(client, lead["id"])
    client.post("/api/auth/logout")

    login(client, "ownerb@test.internal", "OwnerPass!2345")
    deadlines = client.get("/api/tenant/deadlines").json()
    assert deadlines == []
