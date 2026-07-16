import uuid

import pytest
from gridkeep_connector_sdk.registry import get_connector_class
from sqlalchemy import select

from core.errors import NotFoundError, ValidationAppError
from db.session import set_tenant_context
from modules.assets.ingestion import ingest_sync_records
from modules.findings.engine import run_correlation
from modules.findings.models import Finding
from modules.identity.models import User
from modules.incidents import service as incidents_service
from modules.incidents.models import IncidentAsset, IncidentFinding
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


async def _make_user(session, email: str) -> uuid.UUID:
    user = User(email=email, password_hash="not-a-real-hash", full_name="Test User", email_verified=True)
    session.add(user)
    await session.flush()
    return user.id


async def _ingest_and_correlate(session, tenant_id: uuid.UUID, provider_id: str) -> None:
    tenant_integration = await integrations_service.connect_integration(
        session,
        tenant_id=tenant_id,
        actor_user_id=uuid.uuid4(),
        provider_id=provider_id,
        label="Test Integration",
        secret_plaintext="fake-secret-for-tests",
    )
    await session.flush()
    connector = get_connector_class(provider_id)(credential_plaintext="fake-secret")
    records = [r async for r in connector.sync()]
    await ingest_sync_records(
        session, tenant_id=tenant_id, tenant_integration_id=tenant_integration.id, provider_id=provider_id,
        records=records,
    )
    await session.commit()
    await set_tenant_context(session, tenant_id)
    await run_correlation(session, tenant_id=tenant_id)
    await session.commit()
    await set_tenant_context(session, tenant_id)


async def _get_finding(session, tenant_id: uuid.UUID, rule_key: str) -> Finding:
    return (
        await session.execute(
            select(Finding).where(Finding.tenant_id == tenant_id, Finding.rule_key == rule_key)
        )
    ).scalar_one()


async def test_declare_incident_sets_declared_status(db):
    tenant_id = await _make_tenant(db, "Declare Co")
    actor_id = await _make_user(db, "actor@declare-co.example")

    incident = await incidents_service.declare_incident(
        db, tenant_id=tenant_id, actor_user_id=actor_id, title="Suspicious login activity",
        description="Multiple failed logins from a new location.", severity="high",
        finding_ids=[], asset_ids=[],
    )
    assert incident.status == "declared"
    assert incident.declared_by_user_id == actor_id
    assert incident.declared_at is not None


async def test_declare_incident_with_finding_links_findings_asset_too(db):
    tenant_id = await _make_tenant(db, "Declare Link Co")
    actor_id = await _make_user(db, "actor@declare-link.example")
    await _ingest_and_correlate(db, tenant_id, "mock_cloud")
    finding = await _get_finding(db, tenant_id, "publicly_exposed_cloud_storage")

    incident = await incidents_service.declare_incident(
        db, tenant_id=tenant_id, actor_user_id=actor_id, title="Exposed bucket",
        description="", severity="critical", finding_ids=[finding.id], asset_ids=[],
    )

    linked_findings = (
        await db.execute(select(IncidentFinding).where(IncidentFinding.incident_id == incident.id))
    ).scalars().all()
    linked_assets = (
        await db.execute(select(IncidentAsset).where(IncidentAsset.incident_id == incident.id))
    ).scalars().all()
    assert len(linked_findings) == 1
    assert linked_findings[0].finding_id == finding.id
    assert len(linked_assets) == 1
    assert linked_assets[0].asset_id == finding.asset_id


async def test_link_finding_is_idempotent(db):
    tenant_id = await _make_tenant(db, "Idempotent Link Co")
    actor_id = await _make_user(db, "actor@idempotent-link.example")
    await _ingest_and_correlate(db, tenant_id, "mock_backup")
    finding = await _get_finding(db, tenant_id, "backup_job_failed")

    incident = await incidents_service.declare_incident(
        db, tenant_id=tenant_id, actor_user_id=actor_id, title="Backup failure",
        description="", severity="medium", finding_ids=[finding.id], asset_ids=[],
    )
    await incidents_service.link_finding(
        db, tenant_id=tenant_id, incident_id=incident.id, finding_id=finding.id
    )
    linked = (
        await db.execute(select(IncidentFinding).where(IncidentFinding.incident_id == incident.id))
    ).scalars().all()
    assert len(linked) == 1


async def test_link_finding_rejects_unknown_finding(db):
    tenant_id = await _make_tenant(db, "Unknown Finding Co")
    actor_id = await _make_user(db, "actor@unknown-finding.example")
    incident = await incidents_service.declare_incident(
        db, tenant_id=tenant_id, actor_user_id=actor_id, title="Test",
        description="", severity="low", finding_ids=[], asset_ids=[],
    )
    with pytest.raises(NotFoundError):
        await incidents_service.link_finding(
            db, tenant_id=tenant_id, incident_id=incident.id, finding_id=uuid.uuid4()
        )


async def test_update_status_sets_resolved_at(db):
    tenant_id = await _make_tenant(db, "Status Co")
    actor_id = await _make_user(db, "actor@status-co.example")
    incident = await incidents_service.declare_incident(
        db, tenant_id=tenant_id, actor_user_id=actor_id, title="Test",
        description="", severity="medium", finding_ids=[], asset_ids=[],
    )

    updated = await incidents_service.update_status(
        db, tenant_id=tenant_id, incident_id=incident.id, status="investigating"
    )
    assert updated.status == "investigating"
    assert updated.resolved_at is None

    resolved = await incidents_service.update_status(
        db, tenant_id=tenant_id, incident_id=incident.id, status="resolved"
    )
    assert resolved.status == "resolved"
    assert resolved.resolved_at is not None


async def test_close_then_status_change_rejected(db):
    tenant_id = await _make_tenant(db, "Close Reject Co")
    actor_id = await _make_user(db, "actor@close-reject.example")
    incident = await incidents_service.declare_incident(
        db, tenant_id=tenant_id, actor_user_id=actor_id, title="Test",
        description="", severity="medium", finding_ids=[], asset_ids=[],
    )
    closed = await incidents_service.close_incident(
        db, tenant_id=tenant_id, incident_id=incident.id, closure_summary="Contained and resolved."
    )
    assert closed.status == "closed"
    assert closed.closed_at is not None

    with pytest.raises(ValidationAppError):
        await incidents_service.update_status(
            db, tenant_id=tenant_id, incident_id=incident.id, status="investigating"
        )

    with pytest.raises(ValidationAppError):
        await incidents_service.close_incident(
            db, tenant_id=tenant_id, incident_id=incident.id, closure_summary="Already closed."
        )


async def test_reopen_incident(db):
    tenant_id = await _make_tenant(db, "Reopen Co")
    actor_id = await _make_user(db, "actor@reopen-co.example")
    incident = await incidents_service.declare_incident(
        db, tenant_id=tenant_id, actor_user_id=actor_id, title="Test",
        description="", severity="medium", finding_ids=[], asset_ids=[],
    )
    await incidents_service.close_incident(
        db, tenant_id=tenant_id, incident_id=incident.id, closure_summary="Done."
    )

    reopened = await incidents_service.reopen_incident(db, tenant_id=tenant_id, incident_id=incident.id)
    assert reopened.status == "investigating"
    assert reopened.closed_at is None


async def test_reopen_rejects_non_closed_incident(db):
    tenant_id = await _make_tenant(db, "Reopen Reject Co")
    actor_id = await _make_user(db, "actor@reopen-reject.example")
    incident = await incidents_service.declare_incident(
        db, tenant_id=tenant_id, actor_user_id=actor_id, title="Test",
        description="", severity="medium", finding_ids=[], asset_ids=[],
    )
    with pytest.raises(ValidationAppError):
        await incidents_service.reopen_incident(db, tenant_id=tenant_id, incident_id=incident.id)


async def test_update_incident_validates_assignee_membership(db):
    tenant_id = await _make_tenant(db, "Assignee Co")
    actor_id = await _make_user(db, "actor@assignee-co.example")
    outsider_id = await _make_user(db, "outsider@assignee-co.example")
    incident = await incidents_service.declare_incident(
        db, tenant_id=tenant_id, actor_user_id=actor_id, title="Test",
        description="", severity="medium", finding_ids=[], asset_ids=[],
    )
    with pytest.raises(ValidationAppError):
        await incidents_service.update_incident(
            db, tenant_id=tenant_id, incident_id=incident.id, title=None, description=None,
            severity=None, assigned_to_user_id=outsider_id,
        )


async def test_list_incidents_filters_and_counts(db):
    tenant_id = await _make_tenant(db, "List Co")
    actor_id = await _make_user(db, "actor@list-co.example")
    await _ingest_and_correlate(db, tenant_id, "mock_cloud")
    finding = await _get_finding(db, tenant_id, "publicly_exposed_cloud_storage")

    await incidents_service.declare_incident(
        db, tenant_id=tenant_id, actor_user_id=actor_id, title="Critical incident",
        description="", severity="critical", finding_ids=[finding.id], asset_ids=[],
    )
    await incidents_service.declare_incident(
        db, tenant_id=tenant_id, actor_user_id=actor_id, title="Low incident",
        description="", severity="low", finding_ids=[], asset_ids=[],
    )

    all_rows = await incidents_service.list_incidents(
        db, tenant_id=tenant_id, status=None, severity=None
    )
    assert len(all_rows) == 2

    critical_rows = await incidents_service.list_incidents(
        db, tenant_id=tenant_id, status=None, severity="critical"
    )
    assert len(critical_rows) == 1
    incident, finding_count, asset_count = critical_rows[0]
    assert incident.title == "Critical incident"
    assert finding_count == 1
    assert asset_count == 1


async def test_incident_summary_excludes_closed(db):
    tenant_id = await _make_tenant(db, "Summary Co")
    actor_id = await _make_user(db, "actor@summary-co.example")

    open_incident = await incidents_service.declare_incident(
        db, tenant_id=tenant_id, actor_user_id=actor_id, title="Open",
        description="", severity="high", finding_ids=[], asset_ids=[],
    )
    closed_incident = await incidents_service.declare_incident(
        db, tenant_id=tenant_id, actor_user_id=actor_id, title="Closed",
        description="", severity="critical", finding_ids=[], asset_ids=[],
    )
    await incidents_service.close_incident(
        db, tenant_id=tenant_id, incident_id=closed_incident.id, closure_summary="Done."
    )

    summary = await incidents_service.get_incident_summary(db, tenant_id=tenant_id)
    assert summary["open_incidents_total"] == 1
    assert summary["open_incidents_by_severity"]["high"] == 1
    assert summary["open_incidents_by_severity"]["critical"] == 0
    assert open_incident.status == "declared"
