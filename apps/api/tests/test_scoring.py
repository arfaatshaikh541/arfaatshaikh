from tests.factories import add_member, login, make_tenant_with_owner


def _service_id(client, tenant, name):
    resp = client.get("/api/tenants/me/services", headers={"X-Tenant-Id": str(tenant.id)})
    return next(s["id"] for s in resp.json() if s["name"] == name)


def test_scoring_rule_awards_points_and_sets_priority(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    service_id = _service_id(client, tenant, "Corporate Tax")

    rule_resp = client.post(
        "/api/tenants/me/scoring/rules",
        json={
            "name": "Corporate tax leads",
            "rule_type": "service_equals",
            "config": {"service_id": service_id},
            "points": 60,
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert rule_resp.status_code == 201

    lead_resp = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "Scored", "service_id": service_id},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert lead_resp.status_code == 201
    body = lead_resp.json()
    assert body["score"] == 60
    assert body["priority"] == "hot"
    assert body["score_reasons"][0]["name"] == "Corporate tax leads"


def test_scoring_rule_requires_permission(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    viewer, _m = add_member(db_session, tenant, role_slug="viewer")
    csrf = login(client, viewer.email)
    resp = client.post(
        "/api/tenants/me/scoring/rules",
        json={"name": "x", "rule_type": "consent_given", "config": {}, "points": 5},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 403


def test_scoring_rule_rejects_unknown_rule_type(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    resp = client.post(
        "/api/tenants/me/scoring/rules",
        json={"name": "x", "rule_type": "not_a_real_type", "config": {}, "points": 5},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422


def test_scoring_thresholds_update(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    resp = client.patch(
        "/api/tenants/me/scoring/thresholds",
        json={"hot_threshold": 80, "warm_threshold": 40, "standard_threshold": 10},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["hot_threshold"] == 80
    assert body["warm_threshold"] == 40
    assert body["standard_threshold"] == 10


def test_manual_priority_override_in_same_request_is_not_recomputed(client, db_session):
    """A caller who sets `priority` explicitly in the same update request as
    a scoring-relevant field is treated as an intentional manual override
    and the scoring engine does not immediately recompute over it. See
    LeadService.update()."""
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    lead_id = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "Manual"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]

    override_resp = client.patch(
        f"/api/tenants/me/leads/{lead_id}",
        json={"priority": "hot", "estimated_value": 1000},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert override_resp.status_code == 200
    assert override_resp.json()["priority"] == "hot"
