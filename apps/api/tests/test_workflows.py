from tests.factories import add_member, login, make_tenant_with_owner


def test_default_qualified_callback_rule_is_seeded_for_new_tenant(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    resp = client.get(
        "/api/tenants/me/workflow-rules",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200
    rules = resp.json()
    assert any(
        r["trigger_type"] == "lead_stage_changed"
        and r["conditions"]
        == [{"field": "to_stage_slug", "operator": "equals", "value": "qualified"}]
        for r in rules
    )


def test_custom_rule_add_tag_on_lead_created(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    tag_id = client.post(
        "/api/tenants/me/tags",
        json={"name": "Auto Tagged"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]

    rule_resp = client.post(
        "/api/tenants/me/workflow-rules",
        json={
            "name": "Tag every new lead",
            "trigger_type": "lead_created",
            "conditions": [],
            "actions": [{"type": "add_tag", "tag_id": tag_id}],
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert rule_resp.status_code == 201
    rule_id = rule_resp.json()["id"]

    lead_resp = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "AutoTagged"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert lead_resp.status_code == 201
    assert tag_id in lead_resp.json()["tag_ids"]

    log_resp = client.get(
        "/api/tenants/me/workflow-rules/execution-log",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert log_resp.status_code == 200
    entries = log_resp.json()
    assert any(
        e["workflow_rule_id"] == rule_id and e["actions_taken"][0]["result"] == "ok"
        for e in entries
    )


def test_condition_with_no_match_does_not_fire(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    tag_id = client.post(
        "/api/tenants/me/tags",
        json={"name": "Only Google"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]

    client.post(
        "/api/tenants/me/workflow-rules",
        json={
            "name": "Tag google leads",
            "trigger_type": "lead_created",
            "conditions": [{"field": "source", "operator": "equals", "value": "google"}],
            "actions": [{"type": "add_tag", "tag_id": tag_id}],
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )

    lead_resp = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "NotGoogle"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert tag_id not in lead_resp.json()["tag_ids"]


def test_deactivated_rule_does_not_fire(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    tag_id = client.post(
        "/api/tenants/me/tags",
        json={"name": "Disabled Rule Tag"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]
    rule = client.post(
        "/api/tenants/me/workflow-rules",
        json={
            "name": "Disabled",
            "trigger_type": "lead_created",
            "conditions": [],
            "actions": [{"type": "add_tag", "tag_id": tag_id}],
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()

    deactivate_resp = client.patch(
        f"/api/tenants/me/workflow-rules/{rule['id']}",
        json={"is_active": False},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert deactivate_resp.json()["is_active"] is False

    lead_resp = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "ShouldNotBeTagged"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert tag_id not in lead_resp.json()["tag_ids"]


def test_rule_rejects_unknown_trigger_type(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    resp = client.post(
        "/api/tenants/me/workflow-rules",
        json={"name": "Bad", "trigger_type": "not_a_real_trigger", "conditions": [], "actions": []},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422


def test_rule_rejects_unknown_action_type(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    resp = client.post(
        "/api/tenants/me/workflow-rules",
        json={
            "name": "Bad action",
            "trigger_type": "lead_created",
            "conditions": [],
            "actions": [{"type": "delete_everything"}],
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422


def test_workflow_rules_require_permission(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    sales_agent, _m = add_member(db_session, tenant, role_slug="sales_agent")
    csrf = login(client, sales_agent.email)
    resp = client.get(
        "/api/tenants/me/workflow-rules",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 403


def test_create_task_action_creates_task_for_assignee(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    agent, agent_membership = add_member(db_session, tenant, role_slug="sales_agent")
    csrf = login(client, owner.email)

    client.post(
        "/api/tenants/me/workflow-rules",
        json={
            "name": "High value follow-up",
            "trigger_type": "lead_created",
            "conditions": [{"field": "estimated_value", "operator": "at_least", "value": 10000}],
            "actions": [
                {
                    "type": "create_task",
                    "title": "Priority follow-up call",
                    "priority": "high",
                    "due_offset_hours": 4,
                }
            ],
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )

    lead_resp = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "BigDeal", "estimated_value": 50000},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    lead_id = lead_resp.json()["id"]

    tasks_resp = client.get(
        "/api/tenants/me/tasks",
        params={"lead_id": lead_id},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    titles = [t["title"] for t in tasks_resp.json()["items"]]
    assert "Priority follow-up call" in titles
