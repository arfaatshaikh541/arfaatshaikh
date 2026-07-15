from app.tests.conftest import login
from app.tests.factories import add_member, create_tenant_with_owner


def _create_lead(client, **overrides) -> dict:
    payload = {"first_name": "Client", "last_name": "One", "email": "client.one@testclient.internal"}
    payload.update(overrides)
    response = client.post("/api/tenant/leads", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _invite_lead_to_portal(client, lead_id: str) -> dict:
    response = client.post("/api/tenant/portal-accounts/invite", json={"lead_id": lead_id})
    assert response.status_code == 201, response.text
    return response.json()


def _accept_portal_invitation(client, fake_email, email: str, password: str = "ClientPortalPass!2345") -> dict:
    token = fake_email.last_token_for(email)
    response = client.post("/api/portal/auth/accept-invitation", json={"token": token, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


def test_invite_accept_and_me(client, db_session, fake_email):
    tenant, _owner = create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    _invite_lead_to_portal(client, lead["id"])
    assert any(m["to"] == "client.one@testclient.internal" for m in fake_email.sent)

    client.post("/api/auth/logout")
    account = _accept_portal_invitation(client, fake_email, "client.one@testclient.internal")
    assert account["email"] == "client.one@testclient.internal"
    assert account["lead_id"] == lead["id"]
    assert account["tenant_name"] == tenant.name

    me = client.get("/api/portal/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "client.one@testclient.internal"


def test_portal_login_after_logout(client, db_session, fake_email):
    tenant, _owner = create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")
    lead = _create_lead(client)
    _invite_lead_to_portal(client, lead["id"])
    client.post("/api/auth/logout")
    _accept_portal_invitation(client, fake_email, "client.one@testclient.internal")

    client.post("/api/portal/auth/logout")
    assert client.get("/api/portal/auth/me").status_code == 401

    relogin = client.post(
        "/api/portal/auth/login",
        json={"tenant_slug": tenant.slug, "email": "client.one@testclient.internal", "password": "ClientPortalPass!2345"},
    )
    assert relogin.status_code == 200, relogin.text
    assert client.get("/api/portal/auth/me").status_code == 200


def test_portal_login_wrong_password_generic_error(client, db_session, fake_email):
    tenant, _owner = create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")
    lead = _create_lead(client)
    _invite_lead_to_portal(client, lead["id"])
    client.post("/api/auth/logout")
    _accept_portal_invitation(client, fake_email, "client.one@testclient.internal")
    client.post("/api/portal/auth/logout")

    bad = client.post(
        "/api/portal/auth/login",
        json={"tenant_slug": tenant.slug, "email": "client.one@testclient.internal", "password": "WrongPassword!1"},
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_credentials"

    unknown_slug = client.post(
        "/api/portal/auth/login",
        json={"tenant_slug": "not-a-real-tenant-slug", "email": "client.one@testclient.internal", "password": "ClientPortalPass!2345"},
    )
    assert unknown_slug.status_code == 401
    assert unknown_slug.json()["error"]["code"] == "invalid_credentials"


def test_invite_requires_lead_email(client, db_session):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")
    lead = _create_lead(client, email=None)

    invite = client.post("/api/tenant/portal-accounts/invite", json={"lead_id": lead["id"]})
    assert invite.status_code == 422
    assert invite.json()["error"]["code"] == "lead_missing_email"


def test_invite_conflict_when_already_has_access(client, db_session, fake_email):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")
    lead = _create_lead(client)
    _invite_lead_to_portal(client, lead["id"])
    client.post("/api/auth/logout")
    _accept_portal_invitation(client, fake_email, "client.one@testclient.internal")

    client.post("/api/portal/auth/logout")
    login(client, "owner@test.internal", "OwnerPass!2345")
    duplicate_invite = client.post("/api/tenant/portal-accounts/invite", json={"lead_id": lead["id"]})
    assert duplicate_invite.status_code == 409
    assert duplicate_invite.json()["error"]["code"] == "already_has_portal_access"


def test_forgot_password_and_reset_flow(client, db_session, fake_email):
    tenant, _owner = create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")
    lead = _create_lead(client)
    _invite_lead_to_portal(client, lead["id"])
    client.post("/api/auth/logout")
    _accept_portal_invitation(client, fake_email, "client.one@testclient.internal")
    client.post("/api/portal/auth/logout")

    forgot = client.post("/api/portal/auth/forgot-password", json={"tenant_slug": tenant.slug, "email": "client.one@testclient.internal"})
    assert forgot.status_code == 202

    token = fake_email.last_token_for("client.one@testclient.internal")
    reset = client.post("/api/portal/auth/reset-password", json={"token": token, "new_password": "BrandNewPass!456"})
    assert reset.status_code == 204

    old_password_login = client.post(
        "/api/portal/auth/login",
        json={"tenant_slug": tenant.slug, "email": "client.one@testclient.internal", "password": "ClientPortalPass!2345"},
    )
    assert old_password_login.status_code == 401

    new_password_login = client.post(
        "/api/portal/auth/login",
        json={"tenant_slug": tenant.slug, "email": "client.one@testclient.internal", "password": "BrandNewPass!456"},
    )
    assert new_password_login.status_code == 200


def test_revoke_portal_account_blocks_login(client, db_session, fake_email):
    tenant, _owner = create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")
    lead = _create_lead(client)
    _invite_lead_to_portal(client, lead["id"])
    client.post("/api/auth/logout")
    _accept_portal_invitation(client, fake_email, "client.one@testclient.internal")
    client.post("/api/portal/auth/logout")

    login(client, "owner@test.internal", "OwnerPass!2345")
    accounts = client.get("/api/tenant/portal-accounts").json()
    assert len(accounts) == 1
    revoke = client.post(f"/api/tenant/portal-accounts/{accounts[0]['id']}/revoke")
    assert revoke.status_code == 200
    assert revoke.json()["is_active"] is False
    client.post("/api/auth/logout")

    blocked_login = client.post(
        "/api/portal/auth/login",
        json={"tenant_slug": tenant.slug, "email": "client.one@testclient.internal", "password": "ClientPortalPass!2345"},
    )
    assert blocked_login.status_code == 401


def test_portal_cannot_access_another_leads_resources(client, db_session, fake_email):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead_a = _create_lead(client, email="client.a@testclient.internal")
    lead_b = _create_lead(client, email="client.b@testclient.internal")
    _invite_lead_to_portal(client, lead_a["id"])

    proposal_b = client.post(
        "/api/tenant/proposals", json={"lead_id": lead_b["id"], "title": "Lead B Proposal", "tax_rate": 0, "line_items": [{"description": "Fee", "quantity": 1, "unit_price": 100}]}
    ).json()

    client.post("/api/auth/logout")
    _accept_portal_invitation(client, fake_email, "client.a@testclient.internal")

    cross_access = client.get(f"/api/portal/proposals/{proposal_b['id']}")
    assert cross_access.status_code == 404


def test_portal_can_view_and_accept_own_proposal(client, db_session, fake_email):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")
    lead = _create_lead(client)
    _invite_lead_to_portal(client, lead["id"])

    proposal = client.post(
        "/api/tenant/proposals",
        json={"lead_id": lead["id"], "title": "Engagement Proposal", "tax_rate": 0, "line_items": [{"description": "Fee", "quantity": 1, "unit_price": 500}]},
    ).json()
    client.post(f"/api/tenant/proposals/{proposal['id']}/send")

    client.post("/api/auth/logout")
    _accept_portal_invitation(client, fake_email, "client.one@testclient.internal")

    my_proposals = client.get("/api/portal/proposals").json()
    assert len(my_proposals) == 1
    assert my_proposals[0]["id"] == proposal["id"]

    accept = client.post(f"/api/portal/proposals/{proposal['id']}/accept", json={"accepted_by_name": "Client One"})
    assert accept.status_code == 200
    assert accept.json()["status"] == "accepted"


def test_portal_can_view_and_upload_document_request(client, db_session, fake_email):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")
    lead = _create_lead(client)
    _invite_lead_to_portal(client, lead["id"])
    request = client.post("/api/tenant/document-requests", json={"lead_id": lead["id"], "title": "Passport copy", "notify": False}).json()

    client.post("/api/auth/logout")
    _accept_portal_invitation(client, fake_email, "client.one@testclient.internal")

    my_requests = client.get("/api/portal/documents").json()
    assert len(my_requests) == 1

    upload = client.post(
        f"/api/portal/documents/{request['id']}/upload",
        files={"file": ("passport.pdf", b"fake content", "application/pdf")},
    )
    assert upload.status_code == 201, upload.text

    detail = client.get(f"/api/portal/documents/{request['id']}").json()
    assert detail["status"] == "uploaded"


def test_portal_can_view_onboarding_deadlines_and_appointments(client, db_session, fake_email):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")
    lead = _create_lead(client)
    _invite_lead_to_portal(client, lead["id"])

    template = client.post(
        "/api/tenant/onboarding-templates",
        json={"name": "Standard", "steps": [{"step_type": "task", "title": "Welcome call", "description": ""}]},
    ).json()
    client.post("/api/tenant/onboarding-cases", json={"lead_id": lead["id"], "template_id": template["id"]})
    client.post("/api/tenant/deadlines", json={"lead_id": lead["id"], "title": "VAT filing", "due_date": "2027-01-01"})

    client.post("/api/auth/logout")
    _accept_portal_invitation(client, fake_email, "client.one@testclient.internal")

    cases = client.get("/api/portal/onboarding-cases").json()
    assert len(cases) == 1
    assert cases[0]["steps"][0]["title"] == "Welcome call"

    deadlines = client.get("/api/portal/deadlines").json()
    assert len(deadlines) == 1
    assert deadlines[0]["title"] == "VAT filing"

    appointments = client.get("/api/portal/appointments").json()
    assert appointments == []


def test_portal_module_gating(client, db_session, fake_email):
    from app.modules.entitlements.service import grant_feature_override

    tenant, _owner = create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")
    lead = _create_lead(client)
    _invite_lead_to_portal(client, lead["id"])
    client.post("/api/auth/logout")
    _accept_portal_invitation(client, fake_email, "client.one@testclient.internal")
    assert client.get("/api/portal/auth/me").status_code == 200

    login(client, "owner@test.internal", "OwnerPass!2345")
    grant_feature_override(db_session, tenant_id=tenant.id, feature_code="client_portal", config={"enabled": False}, granted_by=None)
    db_session.commit()
    client.post("/api/auth/logout")

    assert client.get("/api/portal/auth/me").status_code == 403


def test_sales_agent_cannot_manage_portal_accounts(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session, plan_code="professional")
    add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")

    login(client, "agent@test.internal", "AgentPass!2345")
    list_response = client.get("/api/tenant/portal-accounts")
    assert list_response.status_code == 403
    assert list_response.json()["error"]["code"] == "permission_denied"


def test_portal_accounts_are_isolated_between_tenants(client, db_session, fake_email):
    tenant_a, _owner_a = create_tenant_with_owner(db_session, name="Tenant A", owner_email="ownera@test.internal", plan_code="professional")

    login(client, "ownera@test.internal", "OwnerPass!2345")
    lead_a = _create_lead(client, email="shared.email@testclient.internal")
    _invite_lead_to_portal(client, lead_a["id"])
    client.post("/api/auth/logout")
    _accept_portal_invitation(client, fake_email, "shared.email@testclient.internal", password="TenantAPass!2345")
    client.post("/api/portal/auth/logout")

    tenant_b, _owner_b = create_tenant_with_owner(db_session, name="Tenant B", owner_email="ownerb@test.internal", plan_code="professional")
    login(client, "ownerb@test.internal", "OwnerPass!2345")
    lead_b = _create_lead(client, email="shared.email@testclient.internal")
    _invite_lead_to_portal(client, lead_b["id"])
    client.post("/api/auth/logout")
    _accept_portal_invitation(client, fake_email, "shared.email@testclient.internal", password="TenantBPass!2345")
    client.post("/api/portal/auth/logout")

    login_a = client.post(
        "/api/portal/auth/login",
        json={"tenant_slug": tenant_a.slug, "email": "shared.email@testclient.internal", "password": "TenantAPass!2345"},
    )
    assert login_a.status_code == 200
    assert login_a.json()["tenant_name"] == tenant_a.name
    client.post("/api/portal/auth/logout")

    login_b = client.post(
        "/api/portal/auth/login",
        json={"tenant_slug": tenant_b.slug, "email": "shared.email@testclient.internal", "password": "TenantBPass!2345"},
    )
    assert login_b.status_code == 200
    assert login_b.json()["tenant_name"] == tenant_b.name
