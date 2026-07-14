from app.tests.conftest import login
from app.tests.factories import create_tenant_with_owner


def test_two_tenants_coexist_with_isolated_membership_lists(client, db_session):
    create_tenant_with_owner(db_session, name="Tenant A", owner_email="ownera@test.internal", owner_password="OwnerPass!2345")
    create_tenant_with_owner(db_session, name="Tenant B", owner_email="ownerb@test.internal", owner_password="OwnerPass!2345")

    login(client, "ownera@test.internal", "OwnerPass!2345")
    tenant_a_users = client.get("/api/tenant/users").json()
    assert {u["email"] for u in tenant_a_users} == {"ownera@test.internal"}
    client.post("/api/auth/logout")

    login(client, "ownerb@test.internal", "OwnerPass!2345")
    tenant_b_users = client.get("/api/tenant/users").json()
    assert {u["email"] for u in tenant_b_users} == {"ownerb@test.internal"}


def test_user_cannot_switch_into_a_tenant_they_do_not_belong_to(client, db_session):
    tenant_a, _ = create_tenant_with_owner(db_session, name="Tenant A", owner_email="ownera@test.internal", owner_password="OwnerPass!2345")
    tenant_b, _ = create_tenant_with_owner(db_session, name="Tenant B", owner_email="ownerb@test.internal", owner_password="OwnerPass!2345")

    login(client, "ownera@test.internal", "OwnerPass!2345")
    response = client.post("/api/auth/switch-tenant", json={"tenant_id": str(tenant_b.id)})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_a_member"


def test_settings_update_in_one_tenant_does_not_affect_the_other(client, db_session):
    create_tenant_with_owner(db_session, name="Tenant A", owner_email="ownera@test.internal", owner_password="OwnerPass!2345")
    create_tenant_with_owner(db_session, name="Tenant B", owner_email="ownerb@test.internal", owner_password="OwnerPass!2345")

    login(client, "ownera@test.internal", "OwnerPass!2345")
    update_response = client.patch("/api/tenant/settings", json={"currency": "USD"})
    assert update_response.status_code == 200
    assert update_response.json()["currency"] == "USD"
    client.post("/api/auth/logout")

    login(client, "ownerb@test.internal", "OwnerPass!2345")
    tenant_b_settings = client.get("/api/tenant/settings").json()
    assert tenant_b_settings["currency"] == "AED"  # tenant default, untouched by tenant A's update


def test_suspended_tenant_blocks_all_access(client, db_session):
    from app.modules.tenancy import service as tenancy_service
    from app.modules.tenancy.models import TenantStatus

    tenant, _owner = create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")
    assert client.get("/api/tenant/settings").status_code == 200

    tenancy_service.set_tenant_status(db_session, tenant=tenant, status=TenantStatus.SUSPENDED)
    db_session.commit()

    response = client.get("/api/tenant/settings")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "tenant_suspended"


def test_read_only_tenant_allows_reads_but_blocks_writes(client, db_session):
    from app.modules.tenancy import service as tenancy_service
    from app.modules.tenancy.models import TenantStatus

    tenant, _owner = create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    tenancy_service.set_tenant_status(db_session, tenant=tenant, status=TenantStatus.READ_ONLY)
    db_session.commit()

    read_response = client.get("/api/tenant/settings")
    assert read_response.status_code == 200

    write_response = client.patch("/api/tenant/settings", json={"currency": "USD"})
    assert write_response.status_code == 403
    assert write_response.json()["error"]["code"] == "tenant_read_only"


def test_restoring_a_suspended_tenant_regains_access_without_data_loss(client, db_session):
    from app.modules.tenancy import service as tenancy_service
    from app.modules.tenancy.models import TenantStatus

    tenant, _owner = create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")
    client.patch("/api/tenant/settings", json={"currency": "USD"})

    tenancy_service.set_tenant_status(db_session, tenant=tenant, status=TenantStatus.SUSPENDED)
    db_session.commit()
    assert client.get("/api/tenant/settings").status_code == 403

    tenancy_service.set_tenant_status(db_session, tenant=tenant, status=TenantStatus.ACTIVE)
    db_session.commit()

    restored_response = client.get("/api/tenant/settings")
    assert restored_response.status_code == 200
    assert restored_response.json()["currency"] == "USD"


def test_archived_tenant_blocks_access(client, db_session):
    from app.modules.tenancy import service as tenancy_service
    from app.modules.tenancy.models import TenantStatus

    tenant, _owner = create_tenant_with_owner(db_session, owner_email="owner@test.internal", owner_password="OwnerPass!2345")
    login(client, "owner@test.internal", "OwnerPass!2345")

    tenancy_service.set_tenant_status(db_session, tenant=tenant, status=TenantStatus.ARCHIVED)
    db_session.commit()

    response = client.get("/api/tenant/settings")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "tenant_archived"
