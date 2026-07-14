from app.tests.conftest import login
from app.tests.factories import add_member, create_tenant_with_owner


def _create_lead(client, **overrides) -> dict:
    payload = {"first_name": "Client", "last_name": "One", "email": "client.one@testclient.internal"}
    payload.update(overrides)
    response = client.post("/api/tenant/leads", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_scoring_rule_matches_and_computes_points(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    rule = client.post(
        "/api/tenant/scoring/rules",
        json={"name": "Has company", "field": "company", "operator": "is_set", "points": 15},
    )
    assert rule.status_code == 201, rule.text

    lead = _create_lead(client, company="Acme LLC")
    detail = client.get(f"/api/tenant/leads/{lead['id']}").json()
    assert detail["score"] is not None

    breakdown = client.get(f"/api/tenant/scoring/leads/{lead['id']}/breakdown").json()
    assert breakdown["total_score"] == 15
    assert breakdown["breakdown"] == [{"rule_id": rule.json()["id"], "rule_name": "Has company", "points": 15}]


def test_scoring_score_clamped_to_100(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    for i in range(3):
        response = client.post(
            "/api/tenant/scoring/rules",
            json={"name": f"Rule {i}", "field": "company", "operator": "is_set", "points": 60},
        )
        assert response.status_code == 201

    lead = _create_lead(client, company="Acme LLC")
    breakdown = client.get(f"/api/tenant/scoring/leads/{lead['id']}/breakdown").json()
    assert breakdown["total_score"] == 100


def test_scoring_auto_priority_from_thresholds(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    client.post("/api/tenant/scoring/rules", json={"name": "Company", "field": "company", "operator": "is_set", "points": 90})
    settings_response = client.patch("/api/tenant/scoring/settings", json={"hot_threshold": 80, "warm_threshold": 40})
    assert settings_response.status_code == 200

    lead = _create_lead(client, company="Acme LLC")
    detail = client.get(f"/api/tenant/leads/{lead['id']}").json()
    assert detail["priority"] == "high"


def test_manual_priority_change_locks_out_auto_priority(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    client.post("/api/tenant/scoring/rules", json={"name": "Company", "field": "company", "operator": "is_set", "points": 90})
    client.patch("/api/tenant/scoring/settings", json={"hot_threshold": 80, "warm_threshold": 40})

    lead = _create_lead(client, company="Acme LLC")
    detail = client.get(f"/api/tenant/leads/{lead['id']}").json()
    assert detail["priority"] == "high"

    manual_update = client.patch(f"/api/tenant/leads/{lead['id']}", json={"priority": "low"})
    assert manual_update.status_code == 200

    rescore = client.post(f"/api/tenant/scoring/leads/{lead['id']}/rescore")
    assert rescore.status_code == 200
    assert rescore.json()["priority"] == "low"  # locked — auto-priority no longer overrides it


def test_scoring_rules_are_isolated_between_tenants(client, db_session):
    tenant_a, _ = create_tenant_with_owner(db_session, name="Tenant A", owner_email="ownera@test.internal")
    create_tenant_with_owner(db_session, name="Tenant B", owner_email="ownerb@test.internal")

    login(client, "ownera@test.internal", "OwnerPass!2345")
    client.post("/api/tenant/scoring/rules", json={"name": "A-only rule", "field": "company", "operator": "is_set", "points": 10})
    client.post("/api/auth/logout")

    login(client, "ownerb@test.internal", "OwnerPass!2345")
    rules = client.get("/api/tenant/scoring/rules").json()
    assert rules == []


def test_scoring_manage_requires_permission(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session)
    add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")

    login(client, "agent@test.internal", "AgentPass!2345")
    view_response = client.get("/api/tenant/scoring/rules")
    assert view_response.status_code == 200  # leads.view is enough to see rules

    create_response = client.post("/api/tenant/scoring/rules", json={"name": "X", "field": "company", "operator": "is_set", "points": 5})
    assert create_response.status_code == 403
    assert create_response.json()["error"]["code"] == "permission_denied"
