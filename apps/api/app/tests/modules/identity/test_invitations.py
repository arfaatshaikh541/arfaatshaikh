from app.tests.conftest import login
from app.tests.factories import create_tenant_with_owner


def _get_sales_agent_role_id(client) -> str:
    roles_response = client.get("/api/tenant/roles")
    assert roles_response.status_code == 200
    roles = {r["name"]: r["id"] for r in roles_response.json()}
    return roles["Sales Agent"]


def test_invite_and_accept_invitation_creates_active_membership(client, db_session, fake_email):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    role_id = _get_sales_agent_role_id(client)
    invite_response = client.post(
        "/api/tenant/users/invitations", json={"email": "newagent@test.internal", "role_id": role_id}
    )
    assert invite_response.status_code == 202

    token = fake_email.last_token_for("newagent@test.internal")
    client.post("/api/auth/logout")

    accept_response = client.post(
        "/api/auth/accept-invitation",
        json={"token": token, "password": "AgentPass!2345", "first_name": "New", "last_name": "Agent"},
    )
    assert accept_response.status_code == 201
    body = accept_response.json()
    assert body["email"] == "newagent@test.internal"
    assert len(body["memberships"]) == 1
    assert body["memberships"][0]["role_name"] == "Sales Agent"

    login_response = client.post("/api/auth/login", json={"email": "newagent@test.internal", "password": "AgentPass!2345"})
    assert login_response.status_code == 200


def test_accept_invitation_twice_fails(client, db_session, fake_email):
    create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")
    role_id = _get_sales_agent_role_id(client)
    client.post("/api/tenant/users/invitations", json={"email": "newagent@test.internal", "role_id": role_id})
    token = fake_email.last_token_for("newagent@test.internal")
    client.post("/api/auth/logout")

    first = client.post(
        "/api/auth/accept-invitation",
        json={"token": token, "password": "AgentPass!2345", "first_name": "New", "last_name": "Agent"},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/auth/accept-invitation",
        json={"token": token, "password": "AgentPass!2345", "first_name": "New", "last_name": "Agent"},
    )
    assert second.status_code == 409


def test_invite_requires_users_manage_permission(client, db_session, fake_email):
    tenant, _owner = create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")
    role_id = _get_sales_agent_role_id(client)
    client.post("/api/tenant/users/invitations", json={"email": "agent@test.internal", "role_id": role_id})
    token = fake_email.last_token_for("agent@test.internal")
    client.post("/api/auth/logout")
    client.post(
        "/api/auth/accept-invitation",
        json={"token": token, "password": "AgentPass!2345", "first_name": "Sales", "last_name": "Agent"},
    )
    client.post("/api/auth/logout")

    login(client, "agent@test.internal", "AgentPass!2345")
    response = client.post("/api/tenant/users/invitations", json={"email": "another@test.internal", "role_id": role_id})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"
