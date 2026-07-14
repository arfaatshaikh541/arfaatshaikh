from app.tests.conftest import login
from app.tests.factories import create_tenant_with_owner


def _create_lead(client, service_id=None) -> str:
    payload = {"first_name": "Client", "last_name": "One", "email": "client.one@testclient.internal"}
    if service_id:
        payload["service_id"] = service_id
    response = client.post("/api/tenant/leads", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_manual_lead_creation_and_default_stage(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead_id = _create_lead(client)
    detail = client.get(f"/api/tenant/leads/{lead_id}").json()

    assert detail["stage_id"] is not None
    pipelines = client.get("/api/tenant/pipelines").json()
    first_stage = pipelines[0]["stages"][0]
    assert detail["stage_id"] == first_stage["id"]
    assert first_stage["name"] == "New"


def test_stage_change_recorded_in_history_and_timeline(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")
    lead_id = _create_lead(client)

    pipeline = client.get("/api/tenant/pipelines").json()[0]
    contacted_stage = next(s for s in pipeline["stages"] if s["name"] == "Contacted")

    response = client.post(f"/api/tenant/leads/{lead_id}/stage", json={"stage_id": contacted_stage["id"]})
    assert response.status_code == 200

    history = client.get(f"/api/tenant/leads/{lead_id}/history").json()
    assert len(history) == 1
    assert history[0]["to_stage_id"] == contacted_stage["id"]

    timeline = client.get(f"/api/tenant/leads/{lead_id}/timeline").json()
    assert any(a["activity_type"] == "lead.stage_changed" for a in timeline)
    assert any(a["activity_type"] == "lead.created" for a in timeline)


def test_notes_tags_and_tasks_on_a_lead(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")
    lead_id = _create_lead(client)

    note_response = client.post(f"/api/tenant/leads/{lead_id}/notes", json={"body": "Called the client."})
    assert note_response.status_code == 201
    notes = client.get(f"/api/tenant/leads/{lead_id}/notes").json()
    assert len(notes) == 1

    tag_response = client.post(f"/api/tenant/leads/{lead_id}/tags", json={"name": "Priority"})
    assert tag_response.status_code == 201
    tags = client.get(f"/api/tenant/leads/{lead_id}/tags").json()
    assert any(t["name"] == "Priority" for t in tags)

    task_response = client.post(f"/api/tenant/leads/{lead_id}/tasks", json={"title": "Send proposal"})
    assert task_response.status_code == 201
    task_id = task_response.json()["id"]
    tasks = client.get(f"/api/tenant/leads/{lead_id}/tasks").json()
    assert any(t["id"] == task_id and t["status"] == "open" for t in tasks)

    complete_response = client.post(f"/api/tenant/tasks/{task_id}/complete")
    assert complete_response.status_code == 200
    tasks_after = client.get(f"/api/tenant/leads/{lead_id}/tasks").json()
    assert next(t for t in tasks_after if t["id"] == task_id)["status"] == "completed"


def test_leads_and_attachments_are_isolated_between_tenants(client, db_session):
    tenant_a, _ = create_tenant_with_owner(db_session, name="Tenant A", owner_email="ownera@test.internal")
    tenant_b, _ = create_tenant_with_owner(db_session, name="Tenant B", owner_email="ownerb@test.internal")

    login(client, "ownera@test.internal", "OwnerPass!2345")
    lead_id = _create_lead(client)
    client.post(f"/api/tenant/leads/{lead_id}/notes", json={"body": "Tenant A note"})
    client.post("/api/auth/logout")

    login(client, "ownerb@test.internal", "OwnerPass!2345")
    cross_tenant_get = client.get(f"/api/tenant/leads/{lead_id}")
    assert cross_tenant_get.status_code == 404

    cross_tenant_notes = client.get(f"/api/tenant/leads/{lead_id}/notes")
    assert cross_tenant_notes.status_code == 200
    assert cross_tenant_notes.json() == []  # tenant B sees none of tenant A's notes, even for a "foreign" lead id

    tenant_b_leads = client.get("/api/tenant/leads").json()["items"]
    assert tenant_b_leads == []


def test_lead_creation_requires_crm_module_permissions_not_platform_permissions(client, db_session):
    """A Viewer (leads.view only, no leads.create) must not be able to create a lead."""
    from app.tests.factories import add_member

    tenant, _owner = create_tenant_with_owner(db_session)
    add_member(db_session, tenant=tenant, email="viewer@test.internal", password="ViewerPass!2345", role_name="Viewer")

    login(client, "viewer@test.internal", "ViewerPass!2345")
    response = client.post("/api/tenant/leads", json={"first_name": "Should", "last_name": "Fail"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_usage_limit_blocks_lead_creation_beyond_plan_limit(client, db_session):
    from app.modules.entitlements.service import grant_feature_override

    tenant, _owner = create_tenant_with_owner(db_session, plan_code="starter")
    login(client, "owner@test.internal", "OwnerPass!2345")

    grant_feature_override(db_session, tenant_id=tenant.id, feature_code="leads", config={"limit": 1}, granted_by=None)
    db_session.commit()

    first = client.post("/api/tenant/leads", json={"first_name": "First", "email": "first@testclient.internal"})
    second = client.post("/api/tenant/leads", json={"first_name": "Second", "email": "second@testclient.internal"})

    assert first.status_code == 201
    assert second.status_code == 403
    assert second.json()["error"]["code"] == "usage_limit_exceeded"


def test_professional_services_template_seeds_nine_services_and_default_form(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    services = client.get("/api/tenant/services").json()
    assert len(services) == 9
    assert {s["name"] for s in services} == {
        "External Audit", "Internal Audit", "Corporate Tax", "VAT", "Accounting and Bookkeeping",
        "Financial Advisory", "Business Setup", "Company Liquidation", "Compliance Consultation",
    }

    forms = client.get("/api/tenant/qualification-forms").json()
    assert len(forms) == 1
    questions = client.get(f"/api/tenant/qualification-forms/{forms[0]['id']}/questions").json()
    assert len(questions) == 9
