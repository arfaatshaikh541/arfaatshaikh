import uuid

import pytest

from tests.helpers import login, onboard_verified_owner

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _connected_owner(client, db, *, org: str, email: str, password: str = "Owner-Pass1!"):
    await onboard_verified_owner(client, db, org_name=org, full_name="Owner", email=email, password=password)
    resp = await login(client, email, password)
    assert resp.status_code == 200
    body = resp.json()
    return {
        "tenant_id": body["memberships"][0]["tenant_id"],
        "csrf_token": body["csrf_token"],
    }


async def test_catalog_lists_mock_connectors(client, db):
    await _connected_owner(client, db, org="Catalog Co", email="owner@catalog-co.example")
    resp = await client.get("/api/integrations/catalog")
    assert resp.status_code == 200
    provider_ids = {entry["provider_id"] for entry in resp.json()}
    expected = {"mock_identity", "mock_endpoint", "mock_cloud", "mock_backup", "mock_threat_intel"}
    assert expected <= provider_ids
    assert all(entry["is_simulator"] for entry in resp.json())


async def test_connect_integration_stores_encrypted_credential_and_marks_connected(client, db):
    ctx = await _connected_owner(client, db, org="Connect Co", email="owner@connect-co.example")
    resp = await client.post(
        "/api/integrations",
        json={"provider_id": "mock_identity", "label": "Demo Identity", "secret": "fake-secret-value"},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "connected"
    assert body["provider_id"] == "mock_identity"

    list_resp = await client.get("/api/integrations")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    health_resp = await client.get(f"/api/integrations/{body['id']}/health")
    assert health_resp.status_code == 200
    assert health_resp.json()[0]["status"] == "healthy"


async def test_connect_integration_rejects_unknown_provider(client, db):
    ctx = await _connected_owner(client, db, org="Unknown Co", email="owner@unknown-co.example")
    resp = await client.post(
        "/api/integrations",
        json={"provider_id": "not_a_real_provider", "label": "Not real", "secret": "some-secret"},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert resp.status_code == 404


async def test_disconnect_integration_revokes_credential(client, db):
    ctx = await _connected_owner(client, db, org="Disconnect Co", email="owner@disconnect-co.example")
    connect_resp = await client.post(
        "/api/integrations",
        json={"provider_id": "mock_backup", "label": "Demo Backup", "secret": "fake-secret"},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    integration_id = connect_resp.json()["id"]

    disconnect_resp = await client.post(
        f"/api/integrations/{integration_id}/disconnect",
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert disconnect_resp.status_code == 200
    assert disconnect_resp.json()["status"] == "disconnected"

    creds_resp = await client.get("/api/integrations/credentials")
    assert creds_resp.status_code == 200
    assert creds_resp.json()[0]["health_status"] == "revoked"


async def test_trigger_sync_creates_running_sync_run(client, db):
    ctx = await _connected_owner(client, db, org="Sync Co", email="owner@sync-co.example")
    connect_resp = await client.post(
        "/api/integrations",
        json={"provider_id": "mock_cloud", "label": "Demo Cloud", "secret": "fake-secret"},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    integration_id = connect_resp.json()["id"]

    sync_resp = await client.post(
        f"/api/integrations/{integration_id}/sync", headers={"X-CSRF-Token": ctx["csrf_token"]}
    )
    assert sync_resp.status_code == 200, sync_resp.text
    assert sync_resp.json()["sync_run_id"]
    assert sync_resp.json()["task_id"]

    runs_resp = await client.get(f"/api/integrations/{integration_id}/sync-runs")
    assert runs_resp.status_code == 200
    runs = runs_resp.json()
    assert len(runs) == 1
    assert runs[0]["status"] == "running"


async def test_cannot_disconnect_another_tenants_integration(client, db):
    ctx_a = await _connected_owner(client, db, org="Isolation A Co", email="ownerA@isolation-a.example")
    connect_resp = await client.post(
        "/api/integrations",
        json={"provider_id": "mock_identity", "label": "A's identity", "secret": "fake-secret"},
        headers={"X-CSRF-Token": ctx_a["csrf_token"]},
    )
    integration_id = connect_resp.json()["id"]
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx_a["csrf_token"]})

    ctx_b = await _connected_owner(client, db, org="Isolation B Co", email="ownerB@isolation-b.example")
    resp = await client.post(
        f"/api/integrations/{integration_id}/disconnect", headers={"X-CSRF-Token": ctx_b["csrf_token"]}
    )
    assert resp.status_code == 404

    list_resp = await client.get("/api/integrations")
    assert list_resp.json() == []


async def test_assets_list_and_detail_after_sync(client, db):
    """End-to-end via the real ingestion service (not the worker/Celery
    path, which is exercised separately) — connects a mock integration,
    ingests its records directly, then verifies the assets API surface."""
    ctx = await _connected_owner(client, db, org="Assets Co", email="owner@assets-co.example")
    connect_resp = await client.post(
        "/api/integrations",
        json={"provider_id": "mock_cloud", "label": "Demo Cloud", "secret": "fake-secret"},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    integration_id = connect_resp.json()["id"]

    from gridkeep_connector_sdk.registry import get_connector_class

    from db.session import AsyncSessionLocal, set_tenant_context
    from modules.assets.ingestion import ingest_sync_records

    tenant_id = uuid.UUID(ctx["tenant_id"])
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        connector = get_connector_class("mock_cloud")(credential_plaintext="fake-secret")
        records = [r async for r in connector.sync()]
        await ingest_sync_records(
            session,
            tenant_id=tenant_id,
            tenant_integration_id=uuid.UUID(integration_id),
            provider_id="mock_cloud",
            records=records,
        )
        await session.commit()

    list_resp = await client.get("/api/assets")
    assert list_resp.status_code == 200
    assets = list_resp.json()
    assert len(assets) == 3
    resource = next(
        a for a in assets if a["asset_type"] == "cloud_resource" and "bucket" in a["display_name"]
    )

    detail_resp = await client.get(f"/api/assets/{resource['id']}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["attributes"]["public_access"] is True
    assert any(r["relationship_type"] == "belongs_to" for r in detail["relationships"])

    criticality_resp = await client.patch(
        f"/api/assets/{resource['id']}/criticality",
        json={"criticality": "critical"},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert criticality_resp.status_code == 200
    assert criticality_resp.json()["criticality"] == "critical"

    changes_resp = await client.get(f"/api/assets/{resource['id']}/changes")
    assert changes_resp.status_code == 200
    assert any(c["field_name"] == "criticality" for c in changes_resp.json())


async def test_assets_scoped_to_own_tenant(client, db):
    ctx_a = await _connected_owner(client, db, org="AssetIso A Co", email="ownerA@asset-iso-a.example")
    connect_resp = await client.post(
        "/api/integrations",
        json={"provider_id": "mock_endpoint", "label": "A endpoints", "secret": "fake-secret"},
        headers={"X-CSRF-Token": ctx_a["csrf_token"]},
    )
    integration_id = connect_resp.json()["id"]

    from gridkeep_connector_sdk.registry import get_connector_class

    from db.session import AsyncSessionLocal, set_tenant_context
    from modules.assets.ingestion import ingest_sync_records

    tenant_a_id = uuid.UUID(ctx_a["tenant_id"])
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_a_id)
        connector = get_connector_class("mock_endpoint")(credential_plaintext="fake-secret")
        records = [r async for r in connector.sync()]
        await ingest_sync_records(
            session,
            tenant_id=tenant_a_id,
            tenant_integration_id=uuid.UUID(integration_id),
            provider_id="mock_endpoint",
            records=records,
        )
        await session.commit()

    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx_a["csrf_token"]})
    await _connected_owner(client, db, org="AssetIso B Co", email="ownerB@asset-iso-b.example")

    resp = await client.get("/api/assets")
    assert resp.status_code == 200
    assert resp.json() == []
