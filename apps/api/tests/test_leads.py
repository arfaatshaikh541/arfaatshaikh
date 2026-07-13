from tests.factories import add_member, login, make_tenant_with_owner


def _stage_id(client, tenant, slug):
    resp = client.get("/api/tenants/me/pipeline-stages", headers={"X-Tenant-Id": str(tenant.id)})
    return next(s["id"] for s in resp.json() if s["slug"] == slug)


def _service_id(client, tenant, name):
    resp = client.get("/api/tenants/me/services", headers={"X-Tenant-Id": str(tenant.id)})
    return next(s["id"] for s in resp.json() if s["name"] == name)


def test_create_manual_lead(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    service_id = _service_id(client, tenant, "Corporate Tax")

    resp = client.post(
        "/api/tenants/me/leads",
        json={
            "first_name": "Fatima",
            "last_name": "Al Marri",
            "email": "fatima@example-corp.dev",
            "phone": "+971501112222",
            "service_id": service_id,
            "consent_given": True,
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["reference_number"].startswith("LD-")
    assert body["stage_id"] == _stage_id(client, tenant, "new")
    assert body["source"] == "manual"


def test_create_lead_requires_leads_create_permission(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    viewer, _m = add_member(db_session, tenant, role_slug="viewer")
    csrf = login(client, viewer.email)
    resp = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "Test"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 403


def test_lead_cross_tenant_service_reference_rejected(client, db_session):
    from app.repositories.service import ServiceRepository

    tenant_a, owner_a = make_tenant_with_owner(db_session)
    tenant_b, _owner_b = make_tenant_with_owner(db_session)
    service_b_id = str(ServiceRepository(db_session).list_for_tenant(tenant_b.id)[0].id)

    csrf = login(client, owner_a.email)
    resp = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "Cross", "service_id": service_b_id},
        headers={"X-Tenant-Id": str(tenant_a.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422


def test_list_leads_filters_search_and_pagination(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    for i in range(3):
        client.post(
            "/api/tenants/me/leads",
            json={"first_name": f"Lead{i}", "email": f"lead{i}@example-corp.dev"},
            headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
        )

    list_resp = client.get(
        "/api/tenants/me/leads",
        params={"page": 1, "page_size": 2},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2

    search_resp = client.get(
        "/api/tenants/me/leads",
        params={"search": "lead1@example-corp.dev"},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert search_resp.json()["total"] == 1
    assert search_resp.json()["items"][0]["first_name"] == "Lead1"


def test_stage_change_and_history_and_timeline(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    create_resp = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "Stagey"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    lead_id = create_resp.json()["id"]
    contacted_id = _stage_id(client, tenant, "contacted")

    stage_resp = client.post(
        f"/api/tenants/me/leads/{lead_id}/stage",
        json={"to_stage_id": contacted_id},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert stage_resp.status_code == 200
    assert stage_resp.json()["stage_id"] == contacted_id

    timeline_resp = client.get(
        f"/api/tenants/me/leads/{lead_id}/timeline", headers={"X-Tenant-Id": str(tenant.id)}
    )
    event_types = [e["event_type"] for e in timeline_resp.json()]
    assert "lead.created" in event_types
    assert "lead.stage_changed" in event_types


def test_moving_to_lost_stage_requires_loss_reason(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    lead_id = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "Losing"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]
    lost_id = _stage_id(client, tenant, "lost")

    without_reason = client.post(
        f"/api/tenants/me/leads/{lead_id}/stage",
        json={"to_stage_id": lost_id},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert without_reason.status_code == 422

    reason_id = client.post(
        "/api/tenants/me/loss-reasons",
        json={"label": "No budget"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]

    with_reason = client.post(
        f"/api/tenants/me/leads/{lead_id}/stage",
        json={"to_stage_id": lost_id, "loss_reason_id": reason_id},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert with_reason.status_code == 200
    assert with_reason.json()["loss_reason_id"] == reason_id


def test_assign_notes_and_tags(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    agent, agent_membership = add_member(db_session, tenant, role_slug="sales_agent")
    csrf = login(client, owner.email)

    lead_id = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "Assignable"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]

    assign_resp = client.post(
        f"/api/tenants/me/leads/{lead_id}/assign",
        json={"membership_id": str(agent_membership.id)},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["assigned_membership_id"] == str(agent_membership.id)

    note_resp = client.post(
        f"/api/tenants/me/leads/{lead_id}/notes",
        json={"body": "Called, left voicemail."},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert note_resp.status_code == 201

    notes_resp = client.get(
        f"/api/tenants/me/leads/{lead_id}/notes", headers={"X-Tenant-Id": str(tenant.id)}
    )
    assert len(notes_resp.json()) == 1

    tag_id = client.post(
        "/api/tenants/me/tags",
        json={"name": "Hot Lead"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]

    add_tag_resp = client.post(
        f"/api/tenants/me/leads/{lead_id}/tags",
        json={"tag_id": tag_id},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert add_tag_resp.status_code == 200

    lead_detail = client.get(
        f"/api/tenants/me/leads/{lead_id}", headers={"X-Tenant-Id": str(tenant.id)}
    ).json()
    assert tag_id in lead_detail["tag_ids"]

    remove_tag_resp = client.delete(
        f"/api/tenants/me/leads/{lead_id}/tags/{tag_id}",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert remove_tag_resp.status_code == 200


def test_bulk_stage_change_skips_cross_tenant_ids(client, db_session):
    tenant_a, owner_a = make_tenant_with_owner(db_session)
    tenant_b, owner_b = make_tenant_with_owner(db_session)

    csrf_a = login(client, owner_a.email)
    lead_a_id = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "A-Lead"},
        headers={"X-Tenant-Id": str(tenant_a.id), "X-CSRF-Token": csrf_a},
    ).json()["id"]

    csrf_b = login(client, owner_b.email)
    lead_b_id = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "B-Lead"},
        headers={"X-Tenant-Id": str(tenant_b.id), "X-CSRF-Token": csrf_b},
    ).json()["id"]

    csrf_a = login(client, owner_a.email)
    contacted_id = _stage_id(client, tenant_a, "contacted")
    bulk_resp = client.post(
        "/api/tenants/me/leads/bulk/stage",
        json={"lead_ids": [lead_a_id, lead_b_id], "to_stage_id": contacted_id},
        headers={"X-Tenant-Id": str(tenant_a.id), "X-CSRF-Token": csrf_a},
    )
    assert bulk_resp.status_code == 200
    result = bulk_resp.json()
    assert result["updated"] == [lead_a_id]
    assert result["failed"] == [lead_b_id]


def test_lead_not_found_in_other_tenant(client, db_session):
    tenant_a, owner_a = make_tenant_with_owner(db_session)
    tenant_b, owner_b = make_tenant_with_owner(db_session)

    csrf_b = login(client, owner_b.email)
    lead_b_id = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "B-Lead"},
        headers={"X-Tenant-Id": str(tenant_b.id), "X-CSRF-Token": csrf_b},
    ).json()["id"]

    login(client, owner_a.email)
    resp = client.get(
        f"/api/tenants/me/leads/{lead_b_id}", headers={"X-Tenant-Id": str(tenant_a.id)}
    )
    assert resp.status_code == 404
