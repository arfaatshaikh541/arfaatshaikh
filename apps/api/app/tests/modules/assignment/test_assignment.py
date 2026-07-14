from app.tests.conftest import login
from app.tests.factories import add_member, create_tenant_with_owner


def _create_lead(client, **overrides) -> dict:
    payload = {"first_name": "Client", "last_name": "One", "email": "client.one@testclient.internal"}
    payload.update(overrides)
    response = client.post("/api/tenant/leads", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_round_robin_cycles_deterministically(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session)
    agent1 = add_member(db_session, tenant=tenant, email="agent1@test.internal", password="AgentPass!2345", role_name="Sales Agent")
    agent2 = add_member(db_session, tenant=tenant, email="agent2@test.internal", password="AgentPass!2345", role_name="Sales Agent")
    db_session.commit()

    login(client, "owner@test.internal", "OwnerPass!2345")
    rule = client.post(
        "/api/tenant/assignment/rules",
        json={"name": "Round robin", "strategy": "round_robin", "conditions": {}, "eligible_user_ids": [str(agent1.id), str(agent2.id)]},
    )
    assert rule.status_code == 201, rule.text

    leads = [_create_lead(client, email=f"lead{i}@testclient.internal") for i in range(4)]
    assigned = [client.get(f"/api/tenant/leads/{lead['id']}").json()["assigned_user_id"] for lead in leads]

    assert assigned == [str(agent1.id), str(agent2.id), str(agent1.id), str(agent2.id)]


def test_service_based_assignment_matches_specific_service(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session)
    agent = add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")
    db_session.commit()

    login(client, "owner@test.internal", "OwnerPass!2345")
    services = client.get("/api/tenant/services").json()
    target_service = services[0]
    other_service = services[1]

    client.post(
        "/api/tenant/assignment/rules",
        json={
            "name": "Audit specialist", "strategy": "service_based",
            "conditions": {"service_ids": [target_service["id"]]}, "eligible_user_ids": [str(agent.id)],
        },
    )

    matching_lead = _create_lead(client, service_id=target_service["id"])
    non_matching_lead = _create_lead(client, email="other@testclient.internal", service_id=other_service["id"])

    assert client.get(f"/api/tenant/leads/{matching_lead['id']}").json()["assigned_user_id"] == str(agent.id)
    assert client.get(f"/api/tenant/leads/{non_matching_lead['id']}").json()["assigned_user_id"] is None


def test_no_matching_rule_leaves_lead_unassigned(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    assert client.get(f"/api/tenant/leads/{lead['id']}").json()["assigned_user_id"] is None


def test_eligible_user_ids_rejects_non_members(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    response = client.post(
        "/api/tenant/assignment/rules",
        json={"name": "Bad rule", "strategy": "round_robin", "conditions": {}, "eligible_user_ids": ["00000000-0000-0000-0000-000000000000"]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_eligible_users"


def test_assignment_rules_are_isolated_between_tenants(client, db_session):
    tenant_a, owner_a = create_tenant_with_owner(db_session, name="Tenant A", owner_email="ownera@test.internal")
    create_tenant_with_owner(db_session, name="Tenant B", owner_email="ownerb@test.internal")

    login(client, "ownera@test.internal", "OwnerPass!2345")
    client.post(
        "/api/tenant/assignment/rules",
        json={"name": "A-only rule", "strategy": "round_robin", "conditions": {}, "eligible_user_ids": [str(owner_a.id)]},
    )
    client.post("/api/auth/logout")

    login(client, "ownerb@test.internal", "OwnerPass!2345")
    rules = client.get("/api/tenant/assignment/rules").json()
    assert rules == []


def test_assignment_manage_requires_permission(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session)
    add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")

    login(client, "agent@test.internal", "AgentPass!2345")
    view_response = client.get("/api/tenant/assignment/rules")
    assert view_response.status_code == 200

    create_response = client.post(
        "/api/tenant/assignment/rules", json={"name": "X", "strategy": "round_robin", "conditions": {}, "eligible_user_ids": []}
    )
    assert create_response.status_code == 403
    assert create_response.json()["error"]["code"] == "permission_denied"
