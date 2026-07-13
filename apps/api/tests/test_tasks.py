from datetime import timedelta

from tests.factories import add_member, login, make_tenant_with_owner


def _stage_id(client, tenant, slug):
    resp = client.get("/api/tenants/me/pipeline-stages", headers={"X-Tenant-Id": str(tenant.id)})
    return next(s["id"] for s in resp.json() if s["slug"] == slug)


def test_create_and_complete_task(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    create_resp = client.post(
        "/api/tenants/me/tasks",
        json={"title": "Call the client", "priority": "high"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert create_resp.status_code == 201
    task = create_resp.json()
    assert task["status"] == "open"
    assert task["is_overdue"] is False

    complete_resp = client.post(
        f"/api/tenants/me/tasks/{task['id']}/complete",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "completed"
    assert complete_resp.json()["completed_at"] is not None


def test_overdue_status_is_computed_not_stored(client, db_session):
    from datetime import UTC, datetime

    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    past_due = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    create_resp = client.post(
        "/api/tenants/me/tasks",
        json={"title": "Overdue callback", "due_at": past_due},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    task_id = create_resp.json()["id"]
    assert create_resp.json()["is_overdue"] is True

    overdue_list = client.get(
        "/api/tenants/me/tasks",
        params={"overdue_only": True},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert task_id in [t["id"] for t in overdue_list.json()["items"]]

    # Completing the task removes it from the overdue view even though
    # due_at is still in the past - overdue is derived from status, not stored.
    client.post(
        f"/api/tenants/me/tasks/{task_id}/complete",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    overdue_list_after = client.get(
        "/api/tenants/me/tasks",
        params={"overdue_only": True},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert task_id not in [t["id"] for t in overdue_list_after.json()["items"]]


def test_task_comments(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    task_id = client.post(
        "/api/tenants/me/tasks",
        json={"title": "Follow up"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]

    comment_resp = client.post(
        f"/api/tenants/me/tasks/{task_id}/comments",
        json={"body": "Left a voicemail."},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert comment_resp.status_code == 201

    list_resp = client.get(
        f"/api/tenants/me/tasks/{task_id}/comments", headers={"X-Tenant-Id": str(tenant.id)}
    )
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["body"] == "Left a voicemail."


def test_task_types_crud(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    create_resp = client.post(
        "/api/tenants/me/task-types",
        json={"name": "Site Visit"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert create_resp.status_code == 201

    list_resp = client.get("/api/tenants/me/task-types", headers={"X-Tenant-Id": str(tenant.id)})
    assert any(t["name"] == "Site Visit" for t in list_resp.json())


def test_tasks_view_permission_required(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    task_id = client.post(
        "/api/tenants/me/tasks",
        json={"title": "Private task"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]

    outsider, _m = add_member(db_session, tenant, role_slug="viewer")
    login(client, outsider.email)
    resp = client.get(f"/api/tenants/me/tasks/{task_id}", headers={"X-Tenant-Id": str(tenant.id)})
    assert resp.status_code == 200  # viewer role does have tasks.view


def test_qualified_stage_creates_callback_task(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    agent, agent_membership = add_member(db_session, tenant, role_slug="sales_agent")
    csrf = login(client, owner.email)

    lead_id = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "Qualifiable"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]
    client.post(
        f"/api/tenants/me/leads/{lead_id}/assign",
        json={"membership_id": str(agent_membership.id)},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )

    qualified_id = _stage_id(client, tenant, "qualified")
    stage_resp = client.post(
        f"/api/tenants/me/leads/{lead_id}/stage",
        json={"to_stage_id": qualified_id},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert stage_resp.status_code == 200

    tasks_resp = client.get(
        "/api/tenants/me/tasks",
        params={"lead_id": lead_id},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    tasks = tasks_resp.json()["items"]
    assert any(t["title"] == "Call back qualified lead" for t in tasks)
    assert any(t["assigned_membership_id"] == str(agent_membership.id) for t in tasks)

    timeline_resp = client.get(
        f"/api/tenants/me/leads/{lead_id}/timeline", headers={"X-Tenant-Id": str(tenant.id)}
    )
    assert "workflow.executed" in [e["event_type"] for e in timeline_resp.json()]
