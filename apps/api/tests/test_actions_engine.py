import uuid

import pytest
from gridkeep_connector_sdk.registry import get_connector_class
from sqlalchemy import select

from core.errors import ValidationAppError
from db.session import set_tenant_context
from modules.actions import service as actions_service
from modules.actions.models import ActionRun, Playbook
from modules.assets.ingestion import ingest_sync_records
from modules.findings.engine import run_correlation
from modules.findings.models import Finding
from modules.identity.models import User
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
    """`ActionRun`/`TenantAutomationSetting` actor columns are real FKs to
    `users.id` (unlike Milestone 2's looser `created_by_user_id` columns),
    so tests that record an actor need a genuine row, not just a UUID."""
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


async def test_manual_action_safety_class_1_auto_approves_without_disruptive_permission(db):
    tenant_id = await _make_tenant(db, "Manual Safe Action Co")
    actor_id = await _make_user(db, "actor@manual-safe-action.example")
    await _ingest_and_correlate(db, tenant_id, "mock_backup")
    finding = await _get_finding(db, tenant_id, "backup_job_failed")

    run, _ = await actions_service.request_manual_action(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        actor_can_approve_disruptive=False,
        asset_id=finding.asset_id,
        action_key="trigger_restore_test",
        params={},
        finding_id=finding.id,
    )
    assert run.safety_class == 1
    assert run.status == "approved"


async def test_manual_action_safety_class_2_waits_for_approval_without_permission(db):
    tenant_id = await _make_tenant(db, "Manual Disruptive Action Co")
    actor_id = await _make_user(db, "actor@manual-disruptive-action.example")
    await _ingest_and_correlate(db, tenant_id, "mock_cloud")
    finding = await _get_finding(db, tenant_id, "publicly_exposed_cloud_storage")

    run, _ = await actions_service.request_manual_action(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        actor_can_approve_disruptive=False,
        asset_id=finding.asset_id,
        action_key="disable_public_sharing",
        params={},
        finding_id=finding.id,
    )
    assert run.safety_class == 2
    assert run.status == "pending_approval"


async def test_manual_action_safety_class_2_auto_approves_with_disruptive_permission(db):
    tenant_id = await _make_tenant(db, "Manual Disruptive Approved Co")
    actor_id = await _make_user(db, "actor@manual-disruptive-approved.example")
    await _ingest_and_correlate(db, tenant_id, "mock_cloud")
    finding = await _get_finding(db, tenant_id, "publicly_exposed_cloud_storage")

    run, _ = await actions_service.request_manual_action(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        actor_can_approve_disruptive=True,
        asset_id=finding.asset_id,
        action_key="disable_public_sharing",
        params={},
        finding_id=finding.id,
    )
    assert run.status == "approved"


async def test_request_manual_action_rejects_unsupported_action_key(db):
    tenant_id = await _make_tenant(db, "Unsupported Action Co")
    actor_id = await _make_user(db, "actor@unsupported-action.example")
    await _ingest_and_correlate(db, tenant_id, "mock_backup")
    finding = await _get_finding(db, tenant_id, "backup_job_failed")

    with pytest.raises(ValidationAppError):
        await actions_service.request_manual_action(
            db,
            tenant_id=tenant_id,
            actor_user_id=actor_id,
            actor_can_approve_disruptive=True,
            asset_id=finding.asset_id,
            action_key="not_a_real_action",
            params={},
            finding_id=None,
        )


async def test_approve_and_reject_action_run(db):
    tenant_id = await _make_tenant(db, "Approve Reject Co")
    actor_id = await _make_user(db, "actor@approve-reject.example")
    approver_id = await _make_user(db, "approver@approve-reject.example")
    await _ingest_and_correlate(db, tenant_id, "mock_cloud")
    finding = await _get_finding(db, tenant_id, "publicly_exposed_cloud_storage")

    run, _ = await actions_service.request_manual_action(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        actor_can_approve_disruptive=False,
        asset_id=finding.asset_id,
        action_key="disable_public_sharing",
        params={},
        finding_id=finding.id,
    )
    assert run.status == "pending_approval"

    approved, _ = await actions_service.approve_action_run(
        db, tenant_id=tenant_id, action_run_id=run.id, actor_user_id=approver_id
    )
    assert approved.status == "approved"
    assert approved.approved_by_user_id == approver_id

    with pytest.raises(ValidationAppError):
        await actions_service.reject_action_run(
            db, tenant_id=tenant_id, action_run_id=run.id, actor_user_id=approver_id, reason="too late"
        )


async def test_evaluate_playbooks_observe_mode_creates_no_runs(db):
    tenant_id = await _make_tenant(db, "Observe Mode Co")
    await _ingest_and_correlate(db, tenant_id, "mock_backup")
    finding = await _get_finding(db, tenant_id, "backup_job_failed")

    db.add(
        Playbook(
            tenant_id=tenant_id, name="Retry failed backups", rule_key="backup_job_failed",
            action_key="trigger_restore_test", is_enabled=True,
        )
    )
    await db.flush()

    # No TenantAutomationSetting row -> defaults to "observe".
    created = await actions_service.evaluate_playbooks_for_findings(
        db, tenant_id=tenant_id, finding_ids=[finding.id]
    )
    assert created == []

    count = (
        await db.execute(select(ActionRun).where(ActionRun.tenant_id == tenant_id))
    ).scalars().all()
    assert count == []


async def test_evaluate_playbooks_guided_mode_creates_pending_approval(db):
    tenant_id = await _make_tenant(db, "Guided Mode Co")
    admin_id = await _make_user(db, "admin@guided-mode.example")
    await _ingest_and_correlate(db, tenant_id, "mock_backup")
    finding = await _get_finding(db, tenant_id, "backup_job_failed")

    db.add(
        Playbook(
            tenant_id=tenant_id, name="Retry failed backups", rule_key="backup_job_failed",
            action_key="trigger_restore_test", is_enabled=True,
        )
    )
    await actions_service.set_automation_mode(
        db, tenant_id=tenant_id, mode="guided", actor_user_id=admin_id
    )
    await db.flush()

    created = await actions_service.evaluate_playbooks_for_findings(
        db, tenant_id=tenant_id, finding_ids=[finding.id]
    )
    assert len(created) == 1
    assert created[0].status == "pending_approval"
    assert created[0].trigger == "playbook"


async def test_evaluate_playbooks_balanced_mode_auto_approves_safe_action(db):
    tenant_id = await _make_tenant(db, "Balanced Safe Co")
    admin_id = await _make_user(db, "admin@balanced-safe.example")
    await _ingest_and_correlate(db, tenant_id, "mock_backup")
    finding = await _get_finding(db, tenant_id, "backup_job_failed")

    db.add(
        Playbook(
            tenant_id=tenant_id, name="Retry failed backups", rule_key="backup_job_failed",
            action_key="trigger_restore_test", is_enabled=True,
        )
    )
    await actions_service.set_automation_mode(
        db, tenant_id=tenant_id, mode="balanced", actor_user_id=admin_id
    )
    await db.flush()

    created = await actions_service.evaluate_playbooks_for_findings(
        db, tenant_id=tenant_id, finding_ids=[finding.id]
    )
    assert len(created) == 1
    assert created[0].status == "approved"  # safety_class 1 <= balanced threshold of 1


async def test_evaluate_playbooks_balanced_mode_holds_disruptive_action_for_approval(db):
    tenant_id = await _make_tenant(db, "Balanced Disruptive Co")
    admin_id = await _make_user(db, "admin@balanced-disruptive.example")
    await _ingest_and_correlate(db, tenant_id, "mock_cloud")
    finding = await _get_finding(db, tenant_id, "publicly_exposed_cloud_storage")

    db.add(
        Playbook(
            tenant_id=tenant_id, name="Lock down public buckets", rule_key="publicly_exposed_cloud_storage",
            action_key="disable_public_sharing", is_enabled=True,
        )
    )
    await actions_service.set_automation_mode(
        db, tenant_id=tenant_id, mode="balanced", actor_user_id=admin_id
    )
    await db.flush()

    created = await actions_service.evaluate_playbooks_for_findings(
        db, tenant_id=tenant_id, finding_ids=[finding.id]
    )
    assert len(created) == 1
    assert created[0].status == "pending_approval"  # safety_class 2 > balanced threshold of 1


async def test_evaluate_playbooks_autopilot_mode_auto_approves_disruptive_action(db):
    tenant_id = await _make_tenant(db, "Autopilot Co")
    admin_id = await _make_user(db, "admin@autopilot.example")
    await _ingest_and_correlate(db, tenant_id, "mock_cloud")
    finding = await _get_finding(db, tenant_id, "publicly_exposed_cloud_storage")

    db.add(
        Playbook(
            tenant_id=tenant_id, name="Lock down public buckets", rule_key="publicly_exposed_cloud_storage",
            action_key="disable_public_sharing", is_enabled=True,
        )
    )
    await actions_service.set_automation_mode(
        db, tenant_id=tenant_id, mode="autopilot", actor_user_id=admin_id
    )
    await db.flush()

    created = await actions_service.evaluate_playbooks_for_findings(
        db, tenant_id=tenant_id, finding_ids=[finding.id]
    )
    assert len(created) == 1
    assert created[0].status == "approved"  # safety_class 2 <= autopilot threshold of 3


async def test_evaluate_playbooks_skips_disabled_playbook(db):
    tenant_id = await _make_tenant(db, "Disabled Playbook Co")
    admin_id = await _make_user(db, "admin@disabled-playbook.example")
    await _ingest_and_correlate(db, tenant_id, "mock_backup")
    finding = await _get_finding(db, tenant_id, "backup_job_failed")

    db.add(
        Playbook(
            tenant_id=tenant_id, name="Retry failed backups", rule_key="backup_job_failed",
            action_key="trigger_restore_test", is_enabled=False,
        )
    )
    await actions_service.set_automation_mode(
        db, tenant_id=tenant_id, mode="balanced", actor_user_id=admin_id
    )
    await db.flush()

    created = await actions_service.evaluate_playbooks_for_findings(
        db, tenant_id=tenant_id, finding_ids=[finding.id]
    )
    assert created == []


async def test_evaluate_playbooks_no_matching_rule_key_creates_nothing(db):
    tenant_id = await _make_tenant(db, "No Match Playbook Co")
    admin_id = await _make_user(db, "admin@no-match-playbook.example")
    await _ingest_and_correlate(db, tenant_id, "mock_backup")
    finding = await _get_finding(db, tenant_id, "backup_job_failed")

    db.add(
        Playbook(
            tenant_id=tenant_id, name="Unrelated playbook", rule_key="admin_without_mfa",
            action_key="revoke_session", is_enabled=True,
        )
    )
    await actions_service.set_automation_mode(
        db, tenant_id=tenant_id, mode="balanced", actor_user_id=admin_id
    )
    await db.flush()

    created = await actions_service.evaluate_playbooks_for_findings(
        db, tenant_id=tenant_id, finding_ids=[finding.id]
    )
    assert created == []


async def test_automation_mode_defaults_to_observe(db):
    tenant_id = await _make_tenant(db, "Default Mode Co")
    mode = await actions_service.get_automation_mode(db, tenant_id=tenant_id)
    assert mode == "observe"
