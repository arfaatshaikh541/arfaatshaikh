from tests.factories import add_member, login, make_tenant_with_owner


def _owner_membership_id(db_session, tenant, owner):
    from app.repositories.membership import MembershipRepository

    return MembershipRepository(db_session).get_for_user_and_tenant(owner.id, tenant.id).id


def test_cannot_demote_last_owner(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)

    from app.repositories.role import RoleRepository

    viewer_role_id = str(RoleRepository(db_session).get_by_slug_for_tenant(tenant.id, "viewer").id)
    owner_membership_id = _owner_membership_id(db_session, tenant, owner)

    resp = client.patch(
        f"/api/tenants/me/members/{owner_membership_id}/role",
        json={"role_id": viewer_role_id},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422
    assert "at least one active Owner" in resp.json()["detail"]


def test_can_demote_owner_when_another_owner_exists(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    _second_owner, _membership = add_member(db_session, tenant, role_slug="owner")
    csrf = login(client, owner.email)

    from app.repositories.role import RoleRepository

    viewer_role_id = str(RoleRepository(db_session).get_by_slug_for_tenant(tenant.id, "viewer").id)
    owner_membership_id = _owner_membership_id(db_session, tenant, owner)

    resp = client.patch(
        f"/api/tenants/me/members/{owner_membership_id}/role",
        json={"role_id": viewer_role_id},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200


def test_suspend_and_reactivate_member(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    member, membership = add_member(db_session, tenant, role_slug="sales_agent")
    csrf = login(client, owner.email)

    suspend_resp = client.post(
        f"/api/tenants/me/members/{membership.id}/suspend",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert suspend_resp.status_code == 200
    assert suspend_resp.json()["status"] == "suspended"

    # A suspended member's own session can no longer act within this tenant.
    login(client, member.email)
    denied = client.get("/api/tenants/me", headers={"X-Tenant-Id": str(tenant.id)})
    assert denied.status_code == 403

    login(client, owner.email)
    csrf2 = client.cookies.get("csrf_token")
    reactivate_resp = client.post(
        f"/api/tenants/me/members/{membership.id}/reactivate",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf2},
    )
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.json()["status"] == "active"
