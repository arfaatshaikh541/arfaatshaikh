import uuid
from datetime import UTC, datetime, timedelta

import pytest
from gridkeep_connector_sdk.registry import get_connector_class
from sqlalchemy import select

from db.session import set_tenant_context
from modules.assets.ingestion import ingest_sync_records
from modules.findings import service as findings_service
from modules.findings.engine import run_correlation
from modules.findings.models import Finding
from modules.integrations import service as integrations_service
from modules.tenancy.models import Tenant, TenantSecurityProfile, TenantSettings

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


async def _make_tenant_integration(session, tenant_id: uuid.UUID, provider_id: str) -> uuid.UUID:
    tenant_integration = await integrations_service.connect_integration(
        session,
        tenant_id=tenant_id,
        actor_user_id=uuid.uuid4(),
        provider_id=provider_id,
        label="Test Integration",
        secret_plaintext="fake-secret-for-tests",
    )
    await session.flush()
    return tenant_integration.id


async def _ingest(session, tenant_id: uuid.UUID, provider_id: str) -> uuid.UUID:
    integration_id = await _make_tenant_integration(session, tenant_id, provider_id)
    connector = get_connector_class(provider_id)(credential_plaintext="fake-secret")
    records = [r async for r in connector.sync()]
    await ingest_sync_records(
        session, tenant_id=tenant_id, tenant_integration_id=integration_id, provider_id=provider_id,
        records=records,
    )
    await session.commit()
    await set_tenant_context(session, tenant_id)
    return integration_id


async def _findings_by_rule(session, tenant_id: uuid.UUID) -> dict[str, Finding]:
    rows = (await session.execute(select(Finding).where(Finding.tenant_id == tenant_id))).scalars().all()
    return {f.rule_key: f for f in rows}


async def test_identity_rules_flag_admin_without_mfa_and_dormant_account(db):
    tenant_id = await _make_tenant(db, "Identity Findings Co")
    await _ingest(db, tenant_id, "mock_identity")

    summary = await run_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    assert summary.created == 2  # admin_without_mfa (Amara) + dormant_user_account (Former Employee)
    findings = await _findings_by_rule(db, tenant_id)
    assert findings["admin_without_mfa"].severity == "critical"
    assert findings["admin_without_mfa"].status == "open"
    assert findings["dormant_user_account"].severity == "medium"
    # Farid has MFA enabled and signed in recently — no finding for him.
    assert len(findings) == 2


async def test_endpoint_rules_flag_unencrypted_stale_and_unresponsive_devices(db):
    tenant_id = await _make_tenant(db, "Endpoint Findings Co")
    await _ingest(db, tenant_id, "mock_endpoint")

    summary = await run_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    # unencrypted_endpoint (hr-laptop), edr_agent_unresponsive + stale_device_checkin (sales-laptop)
    assert summary.created == 3
    findings = await _findings_by_rule(db, tenant_id)
    assert findings["unencrypted_endpoint"].severity == "high"
    assert findings["edr_agent_unresponsive"].severity == "high"
    assert findings["stale_device_checkin"].severity == "medium"


async def test_cloud_and_backup_rules(db):
    tenant_id = await _make_tenant(db, "Cloud Backup Findings Co")
    await _ingest(db, tenant_id, "mock_cloud")
    await _ingest(db, tenant_id, "mock_backup")

    summary = await run_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    assert summary.created == 2
    findings = await _findings_by_rule(db, tenant_id)
    assert findings["publicly_exposed_cloud_storage"].severity == "critical"
    assert findings["backup_job_failed"].severity == "high"


async def test_correlation_is_idempotent_on_rerun(db):
    tenant_id = await _make_tenant(db, "Idempotent Co")
    await _ingest(db, tenant_id, "mock_identity")

    first = await run_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)
    assert first.created == 2

    second = await run_correlation(db, tenant_id=tenant_id)
    await db.commit()

    assert second.created == 0
    assert second.updated == 2


async def test_finding_auto_resolves_when_condition_clears(db):
    tenant_id = await _make_tenant(db, "Auto Resolve Co")
    integration_id = await _ingest(db, tenant_id, "mock_endpoint")
    await run_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    findings = await _findings_by_rule(db, tenant_id)
    assert findings["unencrypted_endpoint"].status == "open"

    # Re-ingest the same provider with the previously-unencrypted device now fixed.
    from gridkeep_connector_sdk.base import NormalizedRecord

    fixed_records = [
        NormalizedRecord(
            record_type="endpoint.device",
            external_id="mock-device-002",
            identifier_type="hostname",
            identifier_value="hr-laptop-03.example-tenant.local",
            display_name="hr-laptop-03.example-tenant.local",
            attributes={
                "os": "Windows 11",
                "encrypted": True,
                "edr_status": "healthy",
                "last_seen_at": datetime.now(UTC).isoformat(),
            },
            raw={},
            observed_at=datetime.now(UTC),
        )
    ]
    await ingest_sync_records(
        db, tenant_id=tenant_id, tenant_integration_id=integration_id, provider_id="mock_endpoint",
        records=fixed_records,
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    summary = await run_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    assert summary.auto_resolved == 1
    findings = await _findings_by_rule(db, tenant_id)
    assert findings["unencrypted_endpoint"].status == "resolved"
    assert findings["unencrypted_endpoint"].closed_at is not None


async def test_remediated_finding_reopens_if_condition_still_present(db):
    tenant_id = await _make_tenant(db, "Reopen Co")
    await _ingest(db, tenant_id, "mock_identity")
    await run_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    findings = await _findings_by_rule(db, tenant_id)
    finding_id = findings["admin_without_mfa"].id
    await findings_service.remediate_finding(
        db, tenant_id=tenant_id, finding_id=finding_id, note="Fixed manually"
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    summary = await run_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    assert summary.reopened == 1
    findings = await _findings_by_rule(db, tenant_id)
    assert findings["admin_without_mfa"].status == "open"


async def test_false_positive_is_never_reopened_by_the_engine(db):
    tenant_id = await _make_tenant(db, "False Positive Co")
    await _ingest(db, tenant_id, "mock_identity")
    await run_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    findings = await _findings_by_rule(db, tenant_id)
    finding_id = findings["dormant_user_account"].id
    await findings_service.dismiss_finding(
        db, tenant_id=tenant_id, finding_id=finding_id, reason="Known contractor, expected."
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    summary = await run_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    assert summary.reopened == 0
    findings = await _findings_by_rule(db, tenant_id)
    assert findings["dormant_user_account"].status == "false_positive"


async def test_accepted_risk_reopens_after_expiry(db):
    tenant_id = await _make_tenant(db, "Accept Risk Expiry Co")
    await _ingest(db, tenant_id, "mock_identity")
    await run_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    findings = await _findings_by_rule(db, tenant_id)
    finding_id = findings["admin_without_mfa"].id
    await findings_service.accept_risk(
        db,
        tenant_id=tenant_id,
        finding_id=finding_id,
        reason="Compensating control in place temporarily.",
        expires_at=datetime.now(UTC) - timedelta(hours=1),  # already expired
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    summary = await run_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    assert summary.accepted_risk_expired == 1
    findings = await _findings_by_rule(db, tenant_id)
    assert findings["admin_without_mfa"].status == "open"
    assert findings["admin_without_mfa"].accepted_risk_expires_at is None


async def test_accepted_risk_without_expiry_persists_across_rerun(db):
    tenant_id = await _make_tenant(db, "Accept Risk Persist Co")
    await _ingest(db, tenant_id, "mock_identity")
    await run_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    findings = await _findings_by_rule(db, tenant_id)
    finding_id = findings["admin_without_mfa"].id
    await findings_service.accept_risk(
        db, tenant_id=tenant_id, finding_id=finding_id, reason="Accepted indefinitely.", expires_at=None
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    summary = await run_correlation(db, tenant_id=tenant_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    assert summary.accepted_risk_expired == 0
    findings = await _findings_by_rule(db, tenant_id)
    assert findings["admin_without_mfa"].status == "accepted_risk"
