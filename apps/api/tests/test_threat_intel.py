import uuid

import pytest
from gridkeep_connector_sdk.registry import get_connector_class
from sqlalchemy import select

from db.session import AsyncSessionLocal, set_tenant_context
from modules.assets.ingestion import ingest_sync_records
from modules.findings.models import Finding
from modules.integrations import service as integrations_service
from modules.tenancy.models import Tenant, TenantSecurityProfile, TenantSettings
from modules.threat_intel.engine import RULE_KEY, run_threat_intel_correlation
from modules.threat_intel.ingestion import ingest_threat_indicators
from modules.threat_intel.models import ThreatIndicator
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


async def _ingest_both(session, tenant_id: uuid.UUID, provider_id: str) -> None:
    """Mirrors exactly what the worker's _run_integration_sync_async does:
    the same record stream feeds both asset ingestion and threat-intel
    ingestion."""
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
    await ingest_threat_indicators(
        session, tenant_id=tenant_id, tenant_integration_id=tenant_integration.id, provider_id=provider_id,
        records=records,
    )
    await session.commit()
    await set_tenant_context(session, tenant_id)


async def _findings_by_rule(session, tenant_id: uuid.UUID) -> dict[str, Finding]:
    rows = (
        await session.execute(
            select(Finding).where(Finding.tenant_id == tenant_id, Finding.rule_key == RULE_KEY)
        )
    ).scalars().all()
    return {f.dedup_key: f for f in rows}


async def test_ingest_threat_indicators_creates_then_updates(db):
    tenant_id = await _make_tenant(db, "Threat Intel Ingest Co")
    tenant_integration = await integrations_service.connect_integration(
        db, tenant_id=tenant_id, actor_user_id=uuid.uuid4(), provider_id="mock_threat_intel",
        label="Test Integration", secret_plaintext="fake-secret",
    )
    connector = get_connector_class("mock_threat_intel")(credential_plaintext="fake-secret")
    records = [r async for r in connector.sync()]

    first = await ingest_threat_indicators(
        db, tenant_id=tenant_id, tenant_integration_id=tenant_integration.id, provider_id="mock_threat_intel",
        records=records,
    )
    assert first.created == 2
    assert first.updated == 0

    second = await ingest_threat_indicators(
        db, tenant_id=tenant_id, tenant_integration_id=tenant_integration.id, provider_id="mock_threat_intel",
        records=records,
    )
    assert second.created == 0
    assert second.updated == 2

    stored = (
        await db.execute(select(ThreatIndicator).where(ThreatIndicator.tenant_id == tenant_id))
    ).scalars().all()
    assert len(stored) == 2


async def test_correlation_flags_endpoint_matching_known_indicator(db):
    tenant_id = await _make_tenant(db, "Threat Intel Match Co")
    await _ingest_both(db, tenant_id, "mock_endpoint")
    await _ingest_both(db, tenant_id, "mock_threat_intel")

    summary = await run_threat_intel_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    assert summary.created == 1  # only sales-laptop-11's planted IP matches mock-ioc-001
    findings = await _findings_by_rule(db, tenant_id)
    assert len(findings) == 1
    finding = next(iter(findings.values()))
    assert finding.severity == "critical"  # mock-ioc-001 has confidence 0.8
    assert finding.evidence["indicator_value"] == "203.0.113.55"
    assert finding.evidence["matched_attribute"] == "last_known_public_ip"


async def test_correlation_is_idempotent_on_rerun(db):
    tenant_id = await _make_tenant(db, "Threat Intel Idempotent Co")
    await _ingest_both(db, tenant_id, "mock_endpoint")
    await _ingest_both(db, tenant_id, "mock_threat_intel")

    first = await run_threat_intel_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)
    assert first.created == 1

    second = await run_threat_intel_correlation(db, tenant_id=tenant_id)
    await db.commit()

    assert second.created == 0
    assert second.updated == 1


async def test_correlation_auto_resolves_when_indicator_value_changes(db):
    tenant_id = await _make_tenant(db, "Threat Intel Auto Resolve Co")
    await _ingest_both(db, tenant_id, "mock_endpoint")
    await _ingest_both(db, tenant_id, "mock_threat_intel")
    await run_threat_intel_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    findings = await _findings_by_rule(db, tenant_id)
    assert len(findings) == 1

    indicator = (
        await db.execute(
            select(ThreatIndicator).where(
                ThreatIndicator.tenant_id == tenant_id, ThreatIndicator.value == "203.0.113.55"
            )
        )
    ).scalar_one()
    indicator.value = "198.51.100.9"  # no longer matches any asset attribute
    await db.commit()
    await set_tenant_context(db, tenant_id)

    summary = await run_threat_intel_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    assert summary.auto_resolved == 1
    findings = await _findings_by_rule(db, tenant_id)
    resolved = next(iter(findings.values()))
    assert resolved.status == "resolved"
    assert resolved.closed_at is not None


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


async def test_indicators_endpoint_lists_matches(client, db):
    ctx = await _connected_owner(
        client, db, org="API Threat Intel Co", email="owner@api-threat-intel.example"
    )
    tenant_id = uuid.UUID(ctx["tenant_id"])
    async with AsyncSessionLocal() as session:
        await _ingest_both(session, tenant_id, "mock_endpoint")
        await _ingest_both(session, tenant_id, "mock_threat_intel")
        await run_threat_intel_correlation(session, tenant_id=tenant_id)
        await session.commit()

    resp = await client.get("/api/threat-intel/indicators")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    matched = next(i for i in body if i["value"] == "203.0.113.55")
    assert len(matched["matches"]) == 1
    assert matched["matches"][0]["asset_display_name"] == "sales-laptop-11.example-tenant.local"
    unmatched = next(i for i in body if i["value"] != "203.0.113.55")
    assert unmatched["matches"] == []


async def test_indicators_scoped_to_own_tenant(client, db):
    ctx_a = await _connected_owner(
        client, db, org="Threat Intel Iso A Co", email="ownerA@threat-intel-iso-a.example"
    )
    tenant_a = uuid.UUID(ctx_a["tenant_id"])
    async with AsyncSessionLocal() as session:
        await _ingest_both(session, tenant_a, "mock_threat_intel")
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": ctx_a["csrf_token"]})

    await _connected_owner(client, db, org="Threat Intel Iso B Co", email="ownerB@threat-intel-iso-b.example")
    resp = await client.get("/api/threat-intel/indicators")

    assert resp.status_code == 200
    assert resp.json() == []
