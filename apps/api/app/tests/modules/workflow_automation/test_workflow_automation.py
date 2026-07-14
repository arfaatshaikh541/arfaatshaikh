import uuid
from datetime import UTC, datetime, timedelta

from app.tests.conftest import login
from app.tests.factories import add_member, create_tenant_with_owner


def _create_lead(client, **overrides) -> dict:
    payload = {"first_name": "Client", "last_name": "One", "email": "client.one@testclient.internal"}
    payload.update(overrides)
    response = client.post("/api/tenant/leads", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _create_workflow(client, **overrides) -> dict:
    payload = {"name": "Test Workflow", "trigger_event": "lead_created", "trigger_config": {}, "conditions": []}
    payload.update(overrides)
    response = client.post("/api/tenant/workflows", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _add_step(client, workflow_id: str, **overrides) -> dict:
    payload = {"delay_minutes": 0, "action_type": "add_tag", "action_config": {"tag_name": "Test Tag"}}
    payload.update(overrides)
    response = client.post(f"/api/tenant/workflows/{workflow_id}/steps", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_lead_created_trigger_executes_add_tag_step(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    workflow = _create_workflow(client)
    _add_step(client, workflow["id"], action_type="add_tag", action_config={"tag_name": "New Lead"})

    lead = _create_lead(client)

    from app.modules.workflow_automation.service import process_due_steps_for_tenant

    processed = process_due_steps_for_tenant(db_session, tenant_id=tenant.id, before=datetime.now(UTC) + timedelta(minutes=1))
    assert processed == 1

    tags = client.get(f"/api/tenant/leads/{lead['id']}/tags").json()
    assert any(t["name"] == "New Lead" for t in tags)

    runs = client.get(f"/api/tenant/workflows/{workflow['id']}/runs").json()
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"

    logs = client.get(f"/api/tenant/workflows/runs/{runs[0]['id']}/logs").json()
    assert len(logs) == 1
    assert logs[0]["status"] == "executed"


def test_multi_step_workflow_respects_delay_before_advancing(client, db_session):
    from app.modules.workflow_automation.service import process_due_steps_for_tenant

    tenant, _owner = create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    workflow = _create_workflow(client)
    _add_step(client, workflow["id"], delay_minutes=0, action_type="add_tag", action_config={"tag_name": "Step One"})
    _add_step(client, workflow["id"], delay_minutes=60, action_type="create_task", action_config={"title": "Step Two Task", "due_in_hours": 4})

    lead = _create_lead(client)

    soon = datetime.now(UTC) + timedelta(minutes=1)
    first_pass = process_due_steps_for_tenant(db_session, tenant_id=tenant.id, before=soon)
    assert first_pass == 1

    tags = client.get(f"/api/tenant/leads/{lead['id']}/tags").json()
    assert any(t["name"] == "Step One" for t in tags)
    tasks = client.get(f"/api/tenant/leads/{lead['id']}/tasks").json()
    assert not any(t["title"] == "Step Two Task" for t in tasks)  # not due yet

    runs = client.get(f"/api/tenant/workflows/{workflow['id']}/runs").json()
    assert runs[0]["status"] == "running"
    assert runs[0]["current_step_index"] == 1

    later = datetime.now(UTC) + timedelta(minutes=61)
    second_pass = process_due_steps_for_tenant(db_session, tenant_id=tenant.id, before=later)
    assert second_pass == 1

    tasks_after = client.get(f"/api/tenant/leads/{lead['id']}/tasks").json()
    assert any(t["title"] == "Step Two Task" for t in tasks_after)
    runs_after = client.get(f"/api/tenant/workflows/{workflow['id']}/runs").json()
    assert runs_after[0]["status"] == "completed"


def test_condition_filters_which_leads_trigger_the_workflow(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    workflow = _create_workflow(client, conditions=[{"field": "company", "operator": "is_set", "value": None}])
    _add_step(client, workflow["id"])

    _create_lead(client, email="nocompany@testclient.internal")
    _create_lead(client, email="withcompany@testclient.internal", company="Acme LLC")

    runs = client.get(f"/api/tenant/workflows/{workflow['id']}/runs").json()
    assert len(runs) == 1


def test_stage_changed_trigger_config_matches_specific_stage(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    workflow = _create_workflow(client, trigger_event="stage_changed", trigger_config={"stage_name": "Qualified"})
    _add_step(client, workflow["id"])

    lead = _create_lead(client)
    pipeline = client.get("/api/tenant/pipelines").json()[0]
    contacted = next(s for s in pipeline["stages"] if s["name"] == "Contacted")
    qualified = next(s for s in pipeline["stages"] if s["name"] == "Qualified")

    client.post(f"/api/tenant/leads/{lead['id']}/stage", json={"stage_id": contacted["id"]})
    assert client.get(f"/api/tenant/workflows/{workflow['id']}/runs").json() == []

    client.post(f"/api/tenant/leads/{lead['id']}/stage", json={"stage_id": qualified["id"]})
    assert len(client.get(f"/api/tenant/workflows/{workflow['id']}/runs").json()) == 1


def test_send_email_template_step(client, db_session, fake_email):
    from app.modules.workflow_automation.service import process_due_steps_for_tenant

    tenant, _owner = create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    template = client.post(
        "/api/tenant/communications/templates",
        json={"name": "Welcome", "trigger_event": "manual", "subject": "Welcome {{first_name}}", "body_text": "Hi {{first_name}}."},
    ).json()

    workflow = _create_workflow(client)
    _add_step(client, workflow["id"], action_type="send_email_template", action_config={"template_id": template["id"]})

    _create_lead(client)
    process_due_steps_for_tenant(db_session, tenant_id=tenant.id, before=datetime.now(UTC) + timedelta(minutes=1))

    assert any(m["to"] == "client.one@testclient.internal" and "Welcome" in m["subject"] for m in fake_email.sent)


def test_change_stage_step(client, db_session):
    from app.modules.workflow_automation.service import process_due_steps_for_tenant

    tenant, _owner = create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    workflow = _create_workflow(client)
    _add_step(client, workflow["id"], action_type="change_stage", action_config={"stage_name": "Contacted"})

    lead = _create_lead(client)
    process_due_steps_for_tenant(db_session, tenant_id=tenant.id, before=datetime.now(UTC) + timedelta(minutes=1))

    detail = client.get(f"/api/tenant/leads/{lead['id']}").json()
    pipeline = client.get("/api/tenant/pipelines").json()[0]
    contacted = next(s for s in pipeline["stages"] if s["name"] == "Contacted")
    assert detail["stage_id"] == contacted["id"]


def test_failed_step_is_logged_but_run_still_completes(client, db_session):
    from app.modules.workflow_automation.service import process_due_steps_for_tenant

    tenant, _owner = create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    workflow = _create_workflow(client)
    _add_step(client, workflow["id"], action_type="send_email_template", action_config={"template_id": "not-a-valid-uuid"})

    _create_lead(client)
    process_due_steps_for_tenant(db_session, tenant_id=tenant.id, before=datetime.now(UTC) + timedelta(minutes=1))

    runs = client.get(f"/api/tenant/workflows/{workflow['id']}/runs").json()
    assert runs[0]["status"] == "completed"  # advances past the failed step rather than getting stuck
    logs = client.get(f"/api/tenant/workflows/runs/{runs[0]['id']}/logs").json()
    assert logs[0]["status"] == "failed"


def test_soft_skips_when_workflow_automation_module_disabled(client, db_session):
    from app.modules.entitlements.service import grant_feature_override

    tenant, _owner = create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    workflow = _create_workflow(client)
    _add_step(client, workflow["id"])

    grant_feature_override(db_session, tenant_id=tenant.id, feature_code="workflow_automation", config={"enabled": False}, granted_by=None)
    db_session.commit()

    lead_response = client.post("/api/tenant/leads", json={"first_name": "Client", "email": "client.one@testclient.internal"})
    assert lead_response.status_code == 201  # module being off must not block lead creation

    # The runs-list route is itself gated by the module we just disabled,
    # so check directly via the repository rather than through the API.
    from app.modules.workflow_automation.repository import WorkflowRunRepository

    assert WorkflowRunRepository(db_session).list_for_workflow(tenant.id, uuid.UUID(workflow["id"])) == []


def test_soft_skips_when_automation_runs_limit_exhausted(client, db_session):
    from app.modules.entitlements.service import grant_feature_override

    tenant, _owner = create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    workflow = _create_workflow(client)
    _add_step(client, workflow["id"])

    grant_feature_override(db_session, tenant_id=tenant.id, feature_code="automation_runs", config={"limit": 0}, granted_by=None)
    db_session.commit()

    lead_response = client.post("/api/tenant/leads", json={"first_name": "Client", "email": "client.one@testclient.internal"})
    assert lead_response.status_code == 201

    assert client.get(f"/api/tenant/workflows/{workflow['id']}/runs").json() == []


def test_manager_can_view_but_not_manage_workflows(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session)
    add_member(db_session, tenant=tenant, email="manager@test.internal", password="ManagerPass!2345", role_name="Manager")

    login(client, "manager@test.internal", "ManagerPass!2345")
    view_response = client.get("/api/tenant/workflows")
    assert view_response.status_code == 200

    create_response = client.post("/api/tenant/workflows", json={"name": "X", "trigger_event": "lead_created", "trigger_config": {}, "conditions": []})
    assert create_response.status_code == 403
    assert create_response.json()["error"]["code"] == "permission_denied"


def test_workflows_are_isolated_between_tenants(client, db_session):
    create_tenant_with_owner(db_session, name="Tenant A", owner_email="ownera@test.internal")
    create_tenant_with_owner(db_session, name="Tenant B", owner_email="ownerb@test.internal")

    login(client, "ownera@test.internal", "OwnerPass!2345")
    _create_workflow(client, name="A-only workflow")
    client.post("/api/auth/logout")

    login(client, "ownerb@test.internal", "OwnerPass!2345")
    workflows = client.get("/api/tenant/workflows").json()
    assert workflows == []
