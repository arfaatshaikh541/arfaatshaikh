from datetime import UTC, date, datetime, timedelta

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
        "name": "Standard Proposal", "description": "A standard engagement.", "terms": "Valid for 30 days.",
        "line_items": [{"description": "Setup fee", "quantity": 1, "unit_price": 1000}],
    }
    payload.update(overrides)
    response = client.post("/api/tenant/proposal-templates", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _create_proposal(client, lead_id: str, **overrides) -> dict:
    payload = {"lead_id": lead_id, "title": "Engagement Proposal", "tax_rate": 5}
    payload.update(overrides)
    response = client.post("/api/tenant/proposals", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _seed_proposal_email_template(client, trigger_event: str, name: str):
    response = client.post(
        "/api/tenant/communications/templates",
        json={
            "name": name, "trigger_event": trigger_event, "subject": f"{name}: {{{{proposal_title}}}}",
            "body_text": f"{name} for {{{{proposal_title}}}} totalling {{{{proposal_total}}}}.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_template_with_line_items(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    template = _create_template(client)
    assert template["name"] == "Standard Proposal"
    assert len(template["line_items"]) == 1
    assert template["line_items"][0]["description"] == "Setup fee"

    templates = client.get("/api/tenant/proposal-templates").json()
    assert len(templates) == 1


def test_create_proposal_from_template_computes_totals(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    template = _create_template(
        client,
        line_items=[
            {"description": "Setup fee", "quantity": 1, "unit_price": 1000},
            {"description": "Monthly retainer", "quantity": 3, "unit_price": 500},
        ],
    )
    lead = _create_lead(client)
    proposal = _create_proposal(client, lead["id"], template_id=template["id"], tax_rate=5)

    assert len(proposal["line_items"]) == 2
    assert proposal["subtotal"] == 2500.0
    assert proposal["tax_amount"] == 125.0
    assert proposal["total"] == 2625.0
    assert proposal["status"] == "draft"
    assert proposal["terms"] == "Valid for 30 days."  # inherited from template since none was passed


def test_create_proposal_with_explicit_line_items_overrides_template(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    proposal = _create_proposal(
        client, lead["id"], tax_rate=0, line_items=[{"description": "Flat fee", "quantity": 1, "unit_price": 2000}]
    )
    assert proposal["total"] == 2000.0
    assert proposal["line_items"][0]["description"] == "Flat fee"


def test_only_draft_proposal_line_items_are_editable(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    proposal = _create_proposal(client, lead["id"], line_items=[{"description": "Fee", "quantity": 1, "unit_price": 100}])
    client.post(f"/api/tenant/proposals/{proposal['id']}/send")

    response = client.put(
        f"/api/tenant/proposals/{proposal['id']}/line-items",
        json={"line_items": [{"description": "New fee", "quantity": 1, "unit_price": 200}]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "proposal_not_editable"


def test_send_proposal_generates_token_and_sends_email(client, db_session, fake_email):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")
    _seed_proposal_email_template(client, "proposal_sent", "Proposal Sent")

    lead = _create_lead(client)
    proposal = _create_proposal(client, lead["id"], line_items=[{"description": "Fee", "quantity": 1, "unit_price": 500}])
    assert proposal["public_token"] is None

    sent = client.post(f"/api/tenant/proposals/{proposal['id']}/send").json()
    assert sent["status"] == "sent"
    assert sent["public_token"]
    assert sent["sent_at"] is not None

    assert any(m["to"] == "client.one@testclient.internal" and "Engagement Proposal" in m["subject"] for m in fake_email.sent)


def test_public_view_marks_proposal_as_viewed(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    proposal = _create_proposal(client, lead["id"], tax_rate=0, line_items=[{"description": "Fee", "quantity": 1, "unit_price": 500}])
    sent = client.post(f"/api/tenant/proposals/{proposal['id']}/send").json()
    client.post("/api/auth/logout")

    public_view = client.get(f"/api/public/proposals/{sent['public_token']}")
    assert public_view.status_code == 200
    body = public_view.json()
    assert body["status"] == "viewed"
    assert body["total"] == 500.0
    assert body["tenant_name"]

    login(client, "owner@test.internal", "OwnerPass!2345")
    detail = client.get(f"/api/tenant/proposals/{proposal['id']}").json()
    assert detail["status"] == "viewed"
    assert detail["viewed_at"] is not None


def test_public_accept_proposal_notifies_and_triggers_workflow(client, db_session, fake_email):
    from app.modules.workflow_automation.service import process_due_steps_for_tenant

    tenant, _owner = create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")
    _seed_proposal_email_template(client, "proposal_accepted", "Proposal Accepted")

    workflow = client.post(
        "/api/tenant/workflows",
        json={"name": "On Accept", "trigger_event": "proposal_accepted", "trigger_config": {}, "conditions": []},
    ).json()
    client.post(
        f"/api/tenant/workflows/{workflow['id']}/steps",
        json={"delay_minutes": 0, "action_type": "add_tag", "action_config": {"tag_name": "Won Deal"}},
    )

    lead = _create_lead(client)
    proposal = _create_proposal(client, lead["id"], line_items=[{"description": "Fee", "quantity": 1, "unit_price": 500}])
    sent = client.post(f"/api/tenant/proposals/{proposal['id']}/send").json()
    client.post("/api/auth/logout")

    accept = client.post(f"/api/public/proposals/{sent['public_token']}/accept", json={"accepted_by_name": "Jane Client"})
    assert accept.status_code == 200
    assert accept.json()["status"] == "accepted"

    assert any(m["to"] == "client.one@testclient.internal" and "Accepted" in m["subject"] for m in fake_email.sent)

    process_due_steps_for_tenant(db_session, tenant_id=tenant.id, before=datetime.now(UTC) + timedelta(minutes=1))
    login(client, "owner@test.internal", "OwnerPass!2345")
    tags = client.get(f"/api/tenant/leads/{lead['id']}/tags").json()
    assert any(t["name"] == "Won Deal" for t in tags)

    detail = client.get(f"/api/tenant/proposals/{proposal['id']}").json()
    assert detail["accepted_by_name"] == "Jane Client"
    assert detail["accepted_at"] is not None


def test_public_reject_proposal_records_reason(client, db_session, fake_email):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")
    _seed_proposal_email_template(client, "proposal_rejected", "Proposal Rejected")

    lead = _create_lead(client)
    proposal = _create_proposal(client, lead["id"], line_items=[{"description": "Fee", "quantity": 1, "unit_price": 500}])
    sent = client.post(f"/api/tenant/proposals/{proposal['id']}/send").json()
    client.post("/api/auth/logout")

    reject = client.post(f"/api/public/proposals/{sent['public_token']}/reject", json={"rejection_reason": "Too expensive"})
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"

    login(client, "owner@test.internal", "OwnerPass!2345")
    detail = client.get(f"/api/tenant/proposals/{proposal['id']}").json()
    assert detail["status"] == "rejected"
    assert detail["rejection_reason"] == "Too expensive"


def test_expired_proposal_cannot_be_accepted(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    proposal = _create_proposal(
        client, lead["id"], valid_until=yesterday, line_items=[{"description": "Fee", "quantity": 1, "unit_price": 500}]
    )
    sent = client.post(f"/api/tenant/proposals/{proposal['id']}/send").json()
    client.post("/api/auth/logout")

    accept = client.post(f"/api/public/proposals/{sent['public_token']}/accept", json={"accepted_by_name": "Jane Client"})
    assert accept.status_code == 422
    assert accept.json()["error"]["code"] == "proposal_expired"


def test_public_route_not_gated_by_proposals_module_entitlement(client, db_session):
    from app.modules.entitlements.service import grant_feature_override

    tenant, _owner = create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    proposal = _create_proposal(client, lead["id"], line_items=[{"description": "Fee", "quantity": 1, "unit_price": 500}])
    sent = client.post(f"/api/tenant/proposals/{proposal['id']}/send").json()

    grant_feature_override(db_session, tenant_id=tenant.id, feature_code="proposals", config={"enabled": False}, granted_by=None)
    db_session.commit()

    # Tenant-authenticated route is now blocked...
    list_response = client.get("/api/tenant/proposals")
    assert list_response.status_code == 403

    client.post("/api/auth/logout")

    # ...but the public acceptance surface the client already has a link to must still work.
    public_view = client.get(f"/api/public/proposals/{sent['public_token']}")
    assert public_view.status_code == 200

    accept = client.post(f"/api/public/proposals/{sent['public_token']}/accept", json={"accepted_by_name": "Jane Client"})
    assert accept.status_code == 200


def test_sales_agent_can_view_but_not_manage_proposals(client, db_session):
    # Per the Milestone 1 permission catalog, "Manager" is granted
    # proposals.manage (managers send quotes directly), unlike
    # workflows.manage which is admin-only — "Sales Agent" is the
    # view-only role for proposals.
    tenant, _owner = create_tenant_with_owner(db_session)
    add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")

    login(client, "agent@test.internal", "AgentPass!2345")
    view_response = client.get("/api/tenant/proposals")
    assert view_response.status_code == 200

    create_response = client.post("/api/tenant/proposal-templates", json={"name": "X"})
    assert create_response.status_code == 403
    assert create_response.json()["error"]["code"] == "permission_denied"


def test_proposals_are_isolated_between_tenants(client, db_session):
    create_tenant_with_owner(db_session, name="Tenant A", owner_email="ownera@test.internal")
    create_tenant_with_owner(db_session, name="Tenant B", owner_email="ownerb@test.internal")

    login(client, "ownera@test.internal", "OwnerPass!2345")
    lead = _create_lead(client)
    _create_proposal(client, lead["id"], line_items=[{"description": "Fee", "quantity": 1, "unit_price": 500}])
    client.post("/api/auth/logout")

    login(client, "ownerb@test.internal", "OwnerPass!2345")
    proposals = client.get("/api/tenant/proposals").json()
    assert proposals == []
