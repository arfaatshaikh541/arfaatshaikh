from tests.factories import login, make_tenant_with_owner


def _get_role_id(db_session, tenant, slug):
    from app.repositories.role import RoleRepository

    return str(RoleRepository(db_session).get_by_slug_for_tenant(tenant.id, slug).id)


def test_invite_and_accept_new_user(client, db_session, monkeypatch):
    import app.services.invitation_service as invitation_service_module

    captured: dict[str, str] = {}

    def fake_send(*, to, tenant_name, accept_url):
        captured["url"] = accept_url

    monkeypatch.setattr(invitation_service_module, "send_invitation_email", fake_send)

    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    manager_role_id = _get_role_id(db_session, tenant, "manager")

    resp = client.post(
        "/api/tenants/me/invitations",
        json={"email": "new-hire@factory.testmail.dev", "role_id": manager_role_id},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 201
    assert "url" in captured
    token = captured["url"].split("token=")[1]

    from fastapi.testclient import TestClient

    from app.main import app

    # A separate TestClient instance sharing the same `app` singleton (and
    # therefore the same dependency_overrides set by the `client` fixture)
    # but with its own independent cookie jar, to simulate an anonymous
    # visitor accepting the invitation without the inviter's session.
    with TestClient(app) as anon_client:
        accept_resp = anon_client.post(
            "/api/invitations/accept",
            json={
                "token": token,
                "first_name": "New",
                "last_name": "Hire",
                "password": "NewHirePassw0rd!123",
            },
        )
        assert accept_resp.status_code == 200
        assert "access_token" in anon_client.cookies

    me_resp = client.get("/api/tenants/me/members", headers={"X-Tenant-Id": str(tenant.id)})
    assert me_resp.status_code == 200
    emails = [m["email"] for m in me_resp.json()]
    assert "new-hire@factory.testmail.dev" in emails


def test_invite_existing_member_conflicts(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    manager_role_id = _get_role_id(db_session, tenant, "manager")

    resp = client.post(
        "/api/tenants/me/invitations",
        json={"email": owner.email, "role_id": manager_role_id},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 409


def test_revoke_invitation(client, db_session, monkeypatch):
    import app.services.invitation_service as invitation_service_module

    monkeypatch.setattr(invitation_service_module, "send_invitation_email", lambda **kw: None)

    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    manager_role_id = _get_role_id(db_session, tenant, "manager")

    create_resp = client.post(
        "/api/tenants/me/invitations",
        json={"email": "revoke-me@factory.testmail.dev", "role_id": manager_role_id},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    invitation_id = create_resp.json()["id"]

    revoke_resp = client.delete(
        f"/api/tenants/me/invitations/{invitation_id}",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert revoke_resp.status_code == 200

    list_resp = client.get("/api/tenants/me/invitations", headers={"X-Tenant-Id": str(tenant.id)})
    revoked = next(i for i in list_resp.json() if i["id"] == invitation_id)
    assert revoked["status"] == "revoked"
