import uuid

import pytest
from gridkeep_connector_sdk.registry import get_connector_class
from sqlalchemy import select

from db.session import AsyncSessionLocal, set_tenant_context
from modules.assets.ingestion import ingest_sync_records
from modules.compliance import service as compliance_service
from modules.compliance.models import ComplianceControl, ComplianceFramework
from modules.findings.engine import run_correlation
from modules.identity.models import User
from modules.incidents import service as incidents_service
from modules.integrations import service as integrations_service
from modules.reporting import service as reporting_service
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


async def _make_user(session, email: str) -> uuid.UUID:
    user = User(email=email, password_hash="not-a-real-hash", full_name="Test User", email_verified=True)
    session.add(user)
    await session.flush()
    return user.id


async def _ingest(session, tenant_id: uuid.UUID, provider_id: str) -> None:
    await set_tenant_context(session, tenant_id)
    tenant_integration = await integrations_service.connect_integration(
        session, tenant_id=tenant_id, actor_user_id=uuid.uuid4(), provider_id=provider_id,
        label="Test Integration", secret_plaintext="fake-secret-for-tests",
    )
    connector = get_connector_class(provider_id)(credential_plaintext="fake-secret")
    records = [r async for r in connector.sync()]
    await ingest_sync_records(
        session, tenant_id=tenant_id, tenant_integration_id=tenant_integration.id, provider_id=provider_id,
        records=records,
    )
    await session.commit()
    await set_tenant_context(session, tenant_id)


async def test_executive_summary_empty_tenant_has_sensible_defaults(db):
    tenant_id = await _make_tenant(db, "Reporting Empty Co")

    summary = await reporting_service.get_executive_summary(db, tenant_id=tenant_id)

    assert summary["asset_total"] == 0
    assert summary["security_score"] == 100
    assert summary["open_findings_total"] == 0
    assert summary["open_incidents_total"] == 0
    assert summary["recovery_confidence_score"] is None
    assert summary["backup_job_total"] == 0
    # Compliance frameworks are seeded platform-wide, so they always score
    # (0, since nothing has been assessed yet) rather than being absent.
    assert summary["compliance_overall_score"] == 0
    assert len(summary["compliance_frameworks"]) == 2


async def test_executive_summary_aggregates_across_all_modules(db):
    tenant_id = await _make_tenant(db, "Reporting Full Co")
    actor_id = await _make_user(db, "actor@reporting-full.example")

    await _ingest(db, tenant_id, "mock_identity")
    await _ingest(db, tenant_id, "mock_backup")
    await run_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    await incidents_service.declare_incident(
        db, tenant_id=tenant_id, actor_user_id=actor_id, title="Test incident", description="",
        severity="high", finding_ids=[], asset_ids=[],
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    framework = (
        await db.execute(select(ComplianceFramework).where(ComplianceFramework.key == "soc2_type2"))
    ).scalar_one()
    control = (
        await db.execute(
            select(ComplianceControl)
            .where(ComplianceControl.framework_id == framework.id)
            .order_by(ComplianceControl.sort_order)
        )
    ).scalars().first()
    await compliance_service.update_control_status(
        db, tenant_id=tenant_id, control_id=control.id, status="met", note=None, actor_user_id=actor_id,
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    summary = await reporting_service.get_executive_summary(db, tenant_id=tenant_id)

    assert summary["asset_total"] > 0
    assert summary["open_findings_total"] > 0  # admin_without_mfa / dormant_user_account
    assert summary["open_incidents_total"] == 1
    assert summary["open_incidents_by_severity"]["high"] == 1
    assert summary["recovery_confidence_score"] is not None
    assert summary["backup_job_total"] == 2
    assert summary["compliance_overall_score"] is not None
    assert summary["compliance_overall_score"] > 0
    soc2 = next(f for f in summary["compliance_frameworks"] if f["key"] == "soc2_type2")
    assert soc2["score"] == 20


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


async def test_executive_summary_endpoint(client, db):
    await _connected_owner(client, db, org="API Reporting Co", email="owner@api-reporting.example")

    resp = await client.get("/api/reports/executive-summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["compliance_overall_score"] == 0
    assert len(body["compliance_frameworks"]) == 2
    assert body["open_findings_total"] == 0


async def test_executive_summary_scoped_to_own_tenant(client, db):
    ctx_a = await _connected_owner(
        client, db, org="Reporting Iso A Co", email="ownerA@reporting-iso-a.example"
    )
    async with AsyncSessionLocal() as session:
        await _ingest(session, uuid.UUID(ctx_a["tenant_id"]), "mock_backup")
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx_a["csrf_token"]})

    await _connected_owner(client, db, org="Reporting Iso B Co", email="ownerB@reporting-iso-b.example")
    resp = await client.get("/api/reports/executive-summary")

    assert resp.status_code == 200
    assert resp.json()["backup_job_total"] == 0  # tenant B has no backup jobs of its own
