"""Canonical tenant-isolation test suite.

Every future tenant-owned resource should get an equivalent test here or in
its own module following the same pattern: two tenants, cross-tenant reads
return 404 (not 403, to avoid confirming existence), cross-tenant object
references in a request body are rejected, and requests missing a verified
tenant context are rejected outright. See
docs/architecture/tenant-isolation-strategy.md.
"""

from tests.factories import add_member, login, make_tenant_with_owner


def test_tenant_header_is_required(client, db_session):
    _tenant, owner = make_tenant_with_owner(db_session)
    login(client, owner.email)
    resp = client.get("/api/tenants/me")
    assert resp.status_code == 400


def test_non_member_cannot_access_other_tenant_context(client, db_session):
    tenant_a, owner_a = make_tenant_with_owner(db_session)
    tenant_b, _owner_b = make_tenant_with_owner(db_session)

    login(client, owner_a.email)
    resp = client.get("/api/tenants/me", headers={"X-Tenant-Id": str(tenant_b.id)})
    assert resp.status_code == 403

    # Owner A's own tenant still works fine.
    resp_own = client.get("/api/tenants/me", headers={"X-Tenant-Id": str(tenant_a.id)})
    assert resp_own.status_code == 200
    assert resp_own.json()["slug"] == tenant_a.slug


def test_nonexistent_tenant_id_returns_404_not_403(client, db_session):
    _tenant, owner = make_tenant_with_owner(db_session)
    login(client, owner.email)
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = client.get("/api/tenants/me", headers={"X-Tenant-Id": fake_id})
    assert resp.status_code == 404


def test_member_cannot_read_other_tenants_membership_by_id(client, db_session):
    tenant_a, owner_a = make_tenant_with_owner(db_session)
    tenant_b, owner_b = make_tenant_with_owner(db_session)
    _user_b, membership_b = add_member(db_session, tenant_b, role_slug="manager")

    csrf = login(client, owner_a.email)

    # Owner A, scoped to tenant A, tries to mutate a membership that
    # actually belongs to tenant B (guessed/enumerated ID). Repository
    # scoping means this looks up nothing for tenant A -> 404.
    resp = client.patch(
        f"/api/tenants/me/members/{membership_b.id}/role",
        json={"role_id": str(owner_a.id)},  # irrelevant, should 404 before validating body
        headers={"X-Tenant-Id": str(tenant_a.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 404


def test_cannot_assign_role_from_another_tenant(client, db_session):
    tenant_a, owner_a = make_tenant_with_owner(db_session)
    tenant_b, _owner_b = make_tenant_with_owner(db_session)
    member_a, membership_a = add_member(db_session, tenant_a, role_slug="sales_agent")

    from app.repositories.role import RoleRepository

    tenant_b_manager_role = RoleRepository(db_session).get_by_slug_for_tenant(
        tenant_b.id, "manager"
    )

    csrf = login(client, owner_a.email)
    resp = client.patch(
        f"/api/tenants/me/members/{membership_a.id}/role",
        json={"role_id": str(tenant_b_manager_role.id)},
        headers={"X-Tenant-Id": str(tenant_a.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422
    assert "does not belong to this tenant" in resp.json()["detail"]


def test_invitation_role_must_belong_to_inviting_tenant(client, db_session):
    tenant_a, owner_a = make_tenant_with_owner(db_session)
    tenant_b, _owner_b = make_tenant_with_owner(db_session)

    from app.repositories.role import RoleRepository

    tenant_b_role = RoleRepository(db_session).get_by_slug_for_tenant(tenant_b.id, "manager")

    csrf = login(client, owner_a.email)
    resp = client.post(
        "/api/tenants/me/invitations",
        json={"email": "someone@factory.testmail.dev", "role_id": str(tenant_b_role.id)},
        headers={"X-Tenant-Id": str(tenant_a.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422


def test_suspended_tenant_denies_member_access(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    tenant.status = "suspended"
    db_session.commit()

    login(client, owner.email)
    resp = client.get("/api/tenants/me", headers={"X-Tenant-Id": str(tenant.id)})
    assert resp.status_code == 403


def test_member_of_two_tenants_can_switch_context(client, db_session):
    tenant_a, owner_a = make_tenant_with_owner(db_session)
    tenant_b, _owner_b = make_tenant_with_owner(db_session)

    from app.repositories.role import RoleRepository

    tenant_b_viewer_role = RoleRepository(db_session).get_by_slug_for_tenant(tenant_b.id, "viewer")
    from app.repositories.membership import MembershipRepository

    MembershipRepository(db_session).create(
        tenant_id=tenant_b.id, user_id=owner_a.id, role_id=tenant_b_viewer_role.id
    )
    db_session.commit()

    login(client, owner_a.email)

    resp_a = client.get("/api/tenants/me", headers={"X-Tenant-Id": str(tenant_a.id)})
    assert resp_a.status_code == 200
    assert resp_a.json()["slug"] == tenant_a.slug

    resp_b = client.get("/api/tenants/me", headers={"X-Tenant-Id": str(tenant_b.id)})
    assert resp_b.status_code == 200
    assert resp_b.json()["slug"] == tenant_b.slug
