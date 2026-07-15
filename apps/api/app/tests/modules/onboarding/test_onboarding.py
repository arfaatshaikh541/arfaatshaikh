from datetime import UTC, datetime, timedelta

from app.tests.conftest import login
from app.tests.factories import add_member, create_tenant_with_owner


def _create_lead(client, **overrides) -> dict:
    payload = {"first_name": "Client", "last_name": "One", "email": "client.one@testclient.internal"}
    payload.update(overrides)
    response = client.post("/api/tenant/leads", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _create_template(client, **overrides) -> dict:
    payload = {
        "name": "Standard Onboarding", "description": "Default checklist",
        "steps": [
            {"step_type": "document_request", "title": "Passport copy", "description": ""},
            {"step_type": "task", "title": "Welcome call", "description": "", "due_in_days": 2},
        ],
    }
    payload.update(overrides)
    response = client.post("/api/tenant/onboarding-templates", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_template_with_steps(client, db_session):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    template = _create_template(client)
    assert len(template["steps"]) == 2
    assert template["steps"][0]["step_type"] == "document_request"
    assert template["steps"][1]["due_in_days"] == 2

    templates = client.get("/api/tenant/onboarding-templates").json()
    assert len(templates) == 1


def test_start_case_spawns_task_and_document_request(client, db_session):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    template = _create_template(client)
    lead = _create_lead(client)

    case = client.post("/api/tenant/onboarding-cases", json={"lead_id": lead["id"], "template_id": template["id"]}).json()
    assert case["status"] == "in_progress"
    assert len(case["steps"]) == 2
    doc_step = next(s for s in case["steps"] if s["step_type"] == "document_request")
    task_step = next(s for s in case["steps"] if s["step_type"] == "task")
    assert doc_step["document_request_id"]
    assert task_step["task_id"]
    assert doc_step["status"] == "pending"
    assert task_step["status"] == "pending"

    document_requests = client.get(f"/api/tenant/document-requests?lead_id={lead['id']}").json()
    assert any(r["id"] == doc_step["document_request_id"] for r in document_requests)

    tasks = client.get(f"/api/tenant/leads/{lead['id']}/tasks").json()
    matching_task = next(t for t in tasks if t["id"] == task_step["task_id"])
    assert matching_task["title"] == "Welcome call"
    assert matching_task["due_at"] is not None


def test_completing_underlying_resources_advances_steps_and_completes_case(client, db_session):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    template = _create_template(client)
    lead = _create_lead(client)
    case = client.post("/api/tenant/onboarding-cases", json={"lead_id": lead["id"], "template_id": template["id"]}).json()
    doc_step = next(s for s in case["steps"] if s["step_type"] == "document_request")
    task_step = next(s for s in case["steps"] if s["step_type"] == "task")

    # Complete the task step by completing its underlying task.
    complete_task = client.post(f"/api/tenant/tasks/{task_step['task_id']}/complete")
    assert complete_task.status_code == 200

    case_after_task = client.get(f"/api/tenant/onboarding-cases/{case['id']}").json()
    updated_task_step = next(s for s in case_after_task["steps"] if s["id"] == task_step["id"])
    assert updated_task_step["status"] == "completed"
    assert case_after_task["status"] == "in_progress"  # document step still pending

    # Complete the document step by uploading and approving the document.
    client.post(
        f"/api/tenant/document-requests/{doc_step['document_request_id']}/documents",
        files={"file": ("passport.pdf", b"fake content", "application/pdf")},
    )
    approve = client.post(f"/api/tenant/document-requests/{doc_step['document_request_id']}/approve", json={"notes": ""})
    assert approve.status_code == 200

    case_final = client.get(f"/api/tenant/onboarding-cases/{case['id']}").json()
    updated_doc_step = next(s for s in case_final["steps"] if s["id"] == doc_step["id"])
    assert updated_doc_step["status"] == "completed"
    assert case_final["status"] == "completed"
    assert case_final["completed_at"] is not None


def test_completing_task_not_tied_to_onboarding_is_a_soft_noop(client, db_session):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    task = client.post(f"/api/tenant/leads/{lead['id']}/tasks", json={"title": "Unrelated task"}).json()

    complete = client.post(f"/api/tenant/tasks/{task['id']}/complete")
    assert complete.status_code == 200  # must not raise or be blocked by the onboarding hook


def test_start_case_without_template_completes_immediately(client, db_session):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    case = client.post("/api/tenant/onboarding-cases", json={"lead_id": lead["id"], "name": "Ad hoc onboarding"}).json()
    assert case["status"] == "completed"
    assert case["steps"] == []


def test_cancel_case(client, db_session):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    template = _create_template(client)
    lead = _create_lead(client)
    case = client.post("/api/tenant/onboarding-cases", json={"lead_id": lead["id"], "template_id": template["id"]}).json()

    cancel = client.post(f"/api/tenant/onboarding-cases/{case['id']}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    cancel_again = client.post(f"/api/tenant/onboarding-cases/{case['id']}/cancel")
    assert cancel_again.status_code == 422
    assert cancel_again.json()["error"]["code"] == "case_already_finished"


def test_manual_step_completion_for_ad_hoc_step(client, db_session):
    from app.modules.onboarding.models import OnboardingStepType
    from app.modules.onboarding.repository import OnboardingCaseStepRepository

    tenant, _owner = create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    template = _create_template(client, steps=[{"step_type": "task", "title": "Only step", "description": ""}])
    lead = _create_lead(client)
    case = client.post("/api/tenant/onboarding-cases", json={"lead_id": lead["id"], "template_id": template["id"]}).json()
    task_step = case["steps"][0]

    # Manufacture an ad hoc step (no task_id/document_request_id) directly
    # via the repository — there is no route to add one to an existing
    # case in this milestone, so this exercises the manual-completion
    # code path the same way a future "add an ad hoc step" feature would.
    from uuid import UUID

    ad_hoc_step = OnboardingCaseStepRepository(db_session).create(
        tenant_id=tenant.id, case_id=UUID(case["id"]), sort_order=1, step_type=OnboardingStepType.TASK,
        title="Ad hoc reminder", description="",
    )
    db_session.commit()

    complete_ad_hoc = client.post(f"/api/tenant/onboarding-cases/{case['id']}/steps/{ad_hoc_step.id}/complete")
    assert complete_ad_hoc.status_code == 200
    case_after = client.get(f"/api/tenant/onboarding-cases/{case['id']}").json()
    updated_ad_hoc = next(s for s in case_after["steps"] if s["id"] == str(ad_hoc_step.id))
    assert updated_ad_hoc["status"] == "completed"
    assert case_after["status"] == "in_progress"  # the real task step is still pending

    complete_task_backed_step = client.post(f"/api/tenant/onboarding-cases/{case['id']}/steps/{task_step['id']}/complete")
    assert complete_task_backed_step.status_code == 422
    assert complete_task_backed_step.json()["error"]["code"] == "step_not_manually_completable"


def test_start_onboarding_case_via_workflow_action(client, db_session):
    from app.modules.workflow_automation.service import process_due_steps_for_tenant

    tenant, _owner = create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    template = _create_template(client)
    workflow = client.post(
        "/api/tenant/workflows",
        json={"name": "Start onboarding", "trigger_event": "lead_created", "trigger_config": {}, "conditions": []},
    ).json()
    client.post(
        f"/api/tenant/workflows/{workflow['id']}/steps",
        json={"delay_minutes": 0, "action_type": "start_onboarding_case", "action_config": {"template_id": template["id"]}},
    )

    lead = _create_lead(client)
    processed = process_due_steps_for_tenant(db_session, tenant_id=tenant.id, before=datetime.now(UTC) + timedelta(minutes=1))
    assert processed == 1

    cases = client.get(f"/api/tenant/onboarding-cases?lead_id={lead['id']}").json()
    assert len(cases) == 1
    assert cases[0]["status"] == "in_progress"
    assert len(cases[0]["steps"]) == 2


def test_sales_agent_can_view_but_not_manage_onboarding(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session, plan_code="professional")
    add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")

    login(client, "agent@test.internal", "AgentPass!2345")
    view_response = client.get("/api/tenant/onboarding-cases")
    assert view_response.status_code == 200

    create_response = client.post("/api/tenant/onboarding-templates", json={"name": "X"})
    assert create_response.status_code == 403
    assert create_response.json()["error"]["code"] == "permission_denied"


def test_onboarding_cases_are_isolated_between_tenants(client, db_session):
    create_tenant_with_owner(db_session, name="Tenant A", owner_email="ownera@test.internal", plan_code="professional")
    create_tenant_with_owner(db_session, name="Tenant B", owner_email="ownerb@test.internal", plan_code="professional")

    login(client, "ownera@test.internal", "OwnerPass!2345")
    lead = _create_lead(client)
    client.post("/api/tenant/onboarding-cases", json={"lead_id": lead["id"]})
    client.post("/api/auth/logout")

    login(client, "ownerb@test.internal", "OwnerPass!2345")
    cases = client.get("/api/tenant/onboarding-cases").json()
    assert cases == []
