from datetime import UTC, datetime, timedelta

from tests.factories import add_member, login, make_tenant_with_owner


def _stage_id(client, tenant, slug):
    resp = client.get("/api/tenants/me/pipeline-stages", headers={"X-Tenant-Id": str(tenant.id)})
    return next(s["id"] for s in resp.json() if s["slug"] == slug)


def test_dashboard_report_reflects_real_data(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    hot_lead_id = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "GoogleLead"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]
    # Fresh test tenants have no scoring rules configured, so creation-time
    # priority is immediately recomputed by the scoring engine (score 0 ->
    # low_priority); PATCH afterwards to set a deliberate manual override,
    # same as LeadService.update()'s documented same-request-override rule.
    client.patch(
        f"/api/tenants/me/leads/{hot_lead_id}",
        json={"priority": "hot"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    client.post(
        "/api/tenants/me/leads",
        json={"first_name": "AnotherLead"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )

    overdue_due = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    client.post(
        "/api/tenants/me/tasks",
        json={"title": "Overdue task", "due_at": overdue_due},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    client.post(
        "/api/tenants/me/tasks",
        json={"title": "Open task"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )

    resp = client.get("/api/tenants/me/reports/dashboard", headers={"X-Tenant-Id": str(tenant.id)})
    assert resp.status_code == 200
    report = resp.json()

    assert report["overview"]["total_leads"] == 2
    assert report["overview"]["hot_leads"] == 1
    assert report["overview"]["open_tasks"] == 2
    assert report["overview"]["overdue_tasks"] == 1

    source_counts = {s["source"]: s["count"] for s in report["lead_sources"]}
    assert source_counts.get("manual") == 2

    priority_counts = {p["priority"]: p["count"] for p in report["score_distribution"]}
    assert priority_counts.get("hot") == 1

    task_stats = report["task_stats"]
    assert task_stats["open"] == 2
    assert task_stats["overdue"] == 1


def test_pipeline_funnel_includes_every_stage(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    client.post(
        "/api/tenants/me/leads",
        json={"first_name": "NewStageLead"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )

    stages_resp = client.get(
        "/api/tenants/me/pipeline-stages", headers={"X-Tenant-Id": str(tenant.id)}
    )
    all_stage_ids = {s["id"] for s in stages_resp.json()}

    report_resp = client.get(
        "/api/tenants/me/reports/dashboard", headers={"X-Tenant-Id": str(tenant.id)}
    )
    funnel = report_resp.json()["pipeline_funnel"]
    funnel_stage_ids = {f["stage_id"] for f in funnel}

    assert funnel_stage_ids == all_stage_ids
    new_stage = next(f for f in funnel if f["stage_id"] == _stage_id(client, tenant, "new"))
    assert new_stage["lead_count"] == 1
    empty_stages = [f for f in funnel if f["stage_id"] != _stage_id(client, tenant, "new")]
    assert all(f["lead_count"] == 0 for f in empty_stages)

    sort_orders = [f["sort_order"] for f in funnel]
    assert sort_orders == sorted(sort_orders)


def test_team_performance_tracks_assigned_and_won_leads(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    agent, agent_membership = add_member(db_session, tenant, role_slug="sales_agent")
    csrf = login(client, owner.email)

    lead_id = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "WinMe"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]
    client.post(
        f"/api/tenants/me/leads/{lead_id}/assign",
        json={"membership_id": str(agent_membership.id)},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    won_stage_id = _stage_id(client, tenant, "won")
    client.post(
        f"/api/tenants/me/leads/{lead_id}/stage",
        json={"to_stage_id": won_stage_id},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )

    report_resp = client.get(
        "/api/tenants/me/reports/dashboard", headers={"X-Tenant-Id": str(tenant.id)}
    )
    team = report_resp.json()["team_performance"]
    agent_row = next(r for r in team if r["membership_id"] == str(agent_membership.id))
    assert agent_row["leads_assigned"] == 1
    assert agent_row["leads_won"] == 1


def test_reports_requires_permission(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    agent, _m = add_member(db_session, tenant, role_slug="sales_agent")
    csrf = login(client, agent.email)
    resp = client.get(
        "/api/tenants/me/reports/dashboard",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 403


def test_reports_are_tenant_isolated(client, db_session):
    tenant_a, owner_a = make_tenant_with_owner(db_session)
    tenant_b, owner_b = make_tenant_with_owner(db_session)

    csrf_b = login(client, owner_b.email)
    client.post(
        "/api/tenants/me/leads",
        json={"first_name": "TenantBLead"},
        headers={"X-Tenant-Id": str(tenant_b.id), "X-CSRF-Token": csrf_b},
    )

    login(client, owner_a.email)
    report_resp = client.get(
        "/api/tenants/me/reports/dashboard", headers={"X-Tenant-Id": str(tenant_a.id)}
    )
    assert report_resp.json()["overview"]["total_leads"] == 0
