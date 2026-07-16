import uuid

import pytest
from gridkeep_connector_sdk.registry import get_connector_class

from db.session import AsyncSessionLocal, set_tenant_context
from modules.assets.ingestion import ingest_sync_records
from modules.findings.engine import run_correlation
from modules.integrations import service as integrations_service
from modules.resilience import service as resilience_service
from modules.tenancy.models import Tenant, TenantSecurityProfile, TenantSettings
from tests.helpers import login, onboard_verified_owner

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _make_tenant(session, name: str) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    await set_tenant_context(session, tenant_id)
    slug = f"{name.lower().replace(' ', '-')}-{tenant_id.hex[:6]}"
    session.add(Tenant(id=tenant_id, name=name, slug=slug, status="active"))
    await session.flush()
    session.add(TenantSettings(tenant_id=tenant_id, display_name=name))
    session.add(TenantSecurityProfile(tenant_id=tenant_id))
    await session.flush()
    return tenant_id


async def _ingest_backup(session, tenant_id: uuid.UUID) -> None:
    await set_tenant_context(session, tenant_id)
    tenant_integration = await integrations_service.connect_integration(
        session,
        tenant_id=tenant_id,
        actor_user_id=uuid.uuid4(),
        provider_id="mock_backup",
        label="Test Backup Integration",
        secret_plaintext="fake-secret-for-tests",
    )
    connector = get_connector_class("mock_backup")(credential_plaintext="fake-secret")
    records = [r async for r in connector.sync()]
    await ingest_sync_records(
        session, tenant_id=tenant_id, tenant_integration_id=tenant_integration.id,
        provider_id="mock_backup", records=records,
    )
    await session.commit()
    await set_tenant_context(session, tenant_id)


async def test_resilience_summary_empty_tenant_has_no_score(db):
    tenant_id = await _make_tenant(db, "No Backup Jobs Co")

    summary = await resilience_service.get_resilience_summary(db, tenant_id=tenant_id)

    assert summary["recovery_confidence_score"] is None
    assert summary["backup_job_total"] == 0
    assert summary["jobs"] == []


async def test_resilience_summary_scores_mock_backup_jobs(db):
    tenant_id = await _make_tenant(db, "Backup Resilience Co")
    await _ingest_backup(db, tenant_id)

    summary = await resilience_service.get_resilience_summary(db, tenant_id=tenant_id)

    assert summary["backup_job_total"] == 2
    assert summary["backup_jobs_immutable"] == 1  # only the database job is immutable
    assert summary["backup_jobs_stale"] == 1  # only the file-server job is stale
    assert summary["backup_jobs_failed"] == 1  # only the database job failed

    jobs_by_name = {j["job_name"]: j for j in summary["jobs"]}
    file_server_job = jobs_by_name["nightly-file-server-backup"]
    assert file_server_job["immutable"] is False
    assert file_server_job["is_stale"] is True
    assert file_server_job["last_run_status"] == "success"
    # 100 - 30 (not immutable) - 20 (stale) = 50
    assert file_server_job["score"] == 50

    database_job = jobs_by_name["nightly-database-backup"]
    assert database_job["immutable"] is True
    assert database_job["is_stale"] is False
    assert database_job["last_run_status"] == "failed"
    # 100 - 50 (last run failed) = 50
    assert database_job["score"] == 50

    assert summary["recovery_confidence_score"] == 50


async def test_correlation_flags_not_immutable_and_stale_backup_jobs(db):
    tenant_id = await _make_tenant(db, "Backup Findings Co")
    await _ingest_backup(db, tenant_id)

    summary = await run_correlation(db, tenant_id=tenant_id)
    await db.commit()

    assert summary.created == 3  # backup_job_failed + backup_not_immutable + backup_job_stale


async def _connected_owner(client, db, *, org: str, email: str, password: str = "Owner-Pass1!"):
    await onboard_verified_owner(client, db, org_name=org, full_name="Owner", email=email, password=password)
    resp = await login(client, email, password)
    assert resp.status_code == 200
    body = resp.json()
    return {
        "tenant_id": body["memberships"][0]["tenant_id"],
        "csrf_token": body["csrf_token"],
        "user_id": body["user"]["id"],
    }


async def test_resilience_summary_endpoint(client, db):
    ctx = await _connected_owner(client, db, org="API Resilience Co", email="owner@api-resilience.example")
    async with AsyncSessionLocal() as session:
        await _ingest_backup(session, uuid.UUID(ctx["tenant_id"]))

    resp = await client.get("/api/resilience/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["backup_job_total"] == 2
    assert body["recovery_confidence_score"] == 50
    assert len(body["jobs"]) == 2


async def test_resilience_summary_scoped_to_own_tenant(client, db):
    ctx_a = await _connected_owner(client, db, org="Tenant A Resilience", email="owner@tenant-a-res.example")
    async with AsyncSessionLocal() as session:
        await _ingest_backup(session, uuid.UUID(ctx_a["tenant_id"]))
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx_a["csrf_token"]})

    await _connected_owner(client, db, org="Tenant B Resilience", email="owner@tenant-b-res.example")
    resp = await client.get("/api/resilience/summary")

    assert resp.status_code == 200
    assert resp.json()["backup_job_total"] == 0  # tenant B has no backup jobs of its own
