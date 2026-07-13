from tests.factories import add_member, login, make_tenant_with_owner


def test_round_robin_assignment_cycles_between_members(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    agent1, membership1 = add_member(db_session, tenant, role_slug="sales_agent")
    agent2, membership2 = add_member(db_session, tenant, role_slug="sales_agent")
    csrf = login(client, owner.email)

    rule_resp = client.post(
        "/api/tenants/me/assignment-rules",
        json={
            "name": "Round robin",
            "strategy": "round_robin",
            "config": {"membership_ids": [str(membership1.id), str(membership2.id)]},
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert rule_resp.status_code == 201

    assigned = []
    for i in range(4):
        lead_resp = client.post(
            "/api/tenants/me/leads",
            json={"first_name": f"RR{i}"},
            headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
        )
        assert lead_resp.status_code == 201
        assigned.append(lead_resp.json()["assigned_membership_id"])

    assert assigned == [
        str(membership1.id),
        str(membership2.id),
        str(membership1.id),
        str(membership2.id),
    ]


def test_manual_fallback_used_when_no_rule_matches(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    fallback_agent, fallback_membership = add_member(db_session, tenant, role_slug="sales_agent")
    csrf = login(client, owner.email)

    client.post(
        "/api/tenants/me/assignment-rules",
        json={
            "name": "Fallback",
            "strategy": "manual_fallback",
            "config": {},
            "fallback_membership_id": str(fallback_membership.id),
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )

    lead_resp = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "Unmatched"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert lead_resp.json()["assigned_membership_id"] == str(fallback_membership.id)


def test_assignment_rule_rejects_cross_tenant_membership(client, db_session):
    tenant_a, owner_a = make_tenant_with_owner(db_session)
    tenant_b, _owner_b = make_tenant_with_owner(db_session)
    _agent_b, membership_b = add_member(db_session, tenant_b, role_slug="sales_agent")

    csrf = login(client, owner_a.email)
    resp = client.post(
        "/api/tenants/me/assignment-rules",
        json={
            "name": "Bad",
            "strategy": "round_robin",
            "config": {"membership_ids": [str(membership_b.id)]},
        },
        headers={"X-Tenant-Id": str(tenant_a.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422


def test_assignment_rule_requires_permission(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    viewer, _m = add_member(db_session, tenant, role_slug="viewer")
    csrf = login(client, viewer.email)
    resp = client.post(
        "/api/tenants/me/assignment-rules",
        json={"name": "x", "strategy": "round_robin", "config": {}},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 403
