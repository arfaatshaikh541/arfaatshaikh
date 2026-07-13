from tests.factories import add_member, login, make_tenant_with_owner


def test_default_services_and_pipeline_stages_seeded(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    login(client, owner.email)

    services_resp = client.get("/api/tenants/me/services", headers={"X-Tenant-Id": str(tenant.id)})
    assert services_resp.status_code == 200
    names = {s["name"] for s in services_resp.json()}
    assert "External Audit" in names
    assert "Corporate Tax" in names

    stages_resp = client.get(
        "/api/tenants/me/pipeline-stages", headers={"X-Tenant-Id": str(tenant.id)}
    )
    assert stages_resp.status_code == 200
    slugs = [s["slug"] for s in stages_resp.json()]
    assert slugs == [
        "new",
        "contacted",
        "qualified",
        "consultation_booked",
        "proposal_sent",
        "follow_up",
        "won",
        "lost",
        "nurture",
        "archived",
    ]
    won = next(s for s in stages_resp.json() if s["slug"] == "won")
    lost = next(s for s in stages_resp.json() if s["slug"] == "lost")
    assert won["is_won"] is True
    assert lost["is_lost"] is True


def test_create_service_requires_settings_manage(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    agent, _m = add_member(db_session, tenant, role_slug="sales_agent")

    csrf = login(client, agent.email)
    resp = client.post(
        "/api/tenants/me/services",
        json={"name": "New Service"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 403


def test_create_and_update_service(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    create_resp = client.post(
        "/api/tenants/me/services",
        json={"name": "Estate Planning"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert create_resp.status_code == 201
    service = create_resp.json()
    assert service["slug"] == "estate-planning"

    update_resp = client.patch(
        f"/api/tenants/me/services/{service['id']}",
        json={"is_active": False},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["is_active"] is False


def test_duplicate_service_name_rejected(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    resp = client.post(
        "/api/tenants/me/services",
        json={"name": "External Audit"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 409


def test_pipeline_stage_reorder(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    stages_resp = client.get(
        "/api/tenants/me/pipeline-stages", headers={"X-Tenant-Id": str(tenant.id)}
    )
    stage_ids = [s["id"] for s in stages_resp.json()]
    reversed_ids = list(reversed(stage_ids))

    reorder_resp = client.post(
        "/api/tenants/me/pipeline-stages/reorder",
        json={"stage_ids": reversed_ids},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert reorder_resp.status_code == 200
    assert [s["id"] for s in reorder_resp.json()] == reversed_ids


def test_pipeline_stage_reorder_rejects_incomplete_list(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    resp = client.post(
        "/api/tenants/me/pipeline-stages/reorder",
        json={"stage_ids": [str(tenant.id)]},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422


def test_tags_and_loss_reasons_crud(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    tag_resp = client.post(
        "/api/tenants/me/tags",
        json={"name": "VIP", "color": "#F97316"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert tag_resp.status_code == 201

    reason_resp = client.post(
        "/api/tenants/me/loss-reasons",
        json={"label": "Too expensive"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert reason_resp.status_code == 201

    branch_resp = client.post(
        "/api/tenants/me/branches",
        json={"name": "Dubai HQ"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert branch_resp.status_code == 201
