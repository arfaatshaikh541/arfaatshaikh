from tests.factories import login, make_tenant_with_owner


def test_add_question_creates_field_and_question(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    resp = client.post(
        "/api/tenants/me/qualification-form/questions",
        json={
            "label": "What is your company name?",
            "field_type": "short_text",
            "is_required": True,
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["field_definition"]["field_key"] == "what-is-your-company-name"
    assert body["is_required"] is True


def test_select_question_requires_options(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    resp = client.post(
        "/api/tenants/me/qualification-form/questions",
        json={"label": "Mainland or Free Zone?", "field_type": "single_select"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422


def test_select_question_with_options(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    resp = client.post(
        "/api/tenants/me/qualification-form/questions",
        json={
            "label": "Mainland or Free Zone?",
            "field_type": "single_select",
            "options": ["Mainland", "Free Zone", "Offshore"],
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 201
    options = resp.json()["field_definition"]["options"]
    assert {o["label"] for o in options} == {"Mainland", "Free Zone", "Offshore"}


def test_deactivating_question_does_not_corrupt_existing_answers(client, db_session):
    """Regression guard for the Milestone 2 requirement: editing/deactivating
    a qualification question must never corrupt historical lead_answers,
    since LeadAnswer snapshots the label/type at submission time."""
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    question_resp = client.post(
        "/api/tenants/me/qualification-form/questions",
        json={"label": "Expected budget?", "field_type": "currency", "is_required": True},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    question_id = question_resp.json()["id"]

    from app.services.lead_service import AnswerInput, LeadService

    lead = LeadService(db_session).create(
        tenant.id,
        actor_user_id=owner.id,
        first_name="Ahmed",
        answers=[AnswerInput(question_id=question_id, value=5000)],
        question_lookup={question_id: ("Expected budget?", "currency")},
    )
    db_session.commit()

    deactivate_resp = client.delete(
        f"/api/tenants/me/qualification-form/questions/{question_id}",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert deactivate_resp.status_code == 200

    lead_resp = client.get(
        f"/api/tenants/me/leads/{lead.id}", headers={"X-Tenant-Id": str(tenant.id)}
    )
    assert lead_resp.status_code == 200
    answers = lead_resp.json()["answers"]
    assert len(answers) == 1
    assert answers[0]["question_label_snapshot"] == "Expected budget?"
    assert answers[0]["value"] == 5000


def test_conditional_rule_creation(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    q1 = client.post(
        "/api/tenants/me/qualification-form/questions",
        json={"label": "Do you have a UAE trade license?", "field_type": "yes_no"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()
    q2 = client.post(
        "/api/tenants/me/qualification-form/questions",
        json={"label": "What is your trade license number?", "field_type": "short_text"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()

    rule_resp = client.post(
        "/api/tenants/me/qualification-form/rules",
        json={
            "question_id": q2["id"],
            "depends_on_question_id": q1["id"],
            "depends_on_value": "yes",
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert rule_resp.status_code == 201

    form_resp = client.get(
        "/api/tenants/me/qualification-form", headers={"X-Tenant-Id": str(tenant.id)}
    )
    q2_out = next(q for q in form_resp.json()["questions"] if q["id"] == q2["id"])
    assert len(q2_out["rules"]) == 1
    assert q2_out["rules"][0]["depends_on_value"] == "yes"
