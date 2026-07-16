import uuid

import pytest
from sqlalchemy import select

from core.errors import NotFoundError, ValidationAppError
from db.session import set_tenant_context
from modules.compliance import service as compliance_service
from modules.compliance.models import ComplianceControl, ComplianceFramework
from modules.identity.models import User
from modules.incidents import service as incidents_service
from modules.tenancy.models import Tenant, TenantSecurityProfile, TenantSettings

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _make_user(session, email: str) -> uuid.UUID:
    user = User(email=email, password_hash="not-a-real-hash", full_name="Test User", email_verified=True)
    session.add(user)
    await session.flush()
    return user.id


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


async def _soc2_controls(session) -> list[ComplianceControl]:
    framework = (
        await session.execute(select(ComplianceFramework).where(ComplianceFramework.key == "soc2_type2"))
    ).scalar_one()
    controls = (
        await session.execute(
            select(ComplianceControl)
            .where(ComplianceControl.framework_id == framework.id)
            .order_by(ComplianceControl.sort_order)
        )
    ).scalars().all()
    return list(controls)


async def test_frameworks_seeded_with_five_controls_each_default_not_met(db):
    tenant_id = await _make_tenant(db, "Compliance Seed Co")

    frameworks = await compliance_service.list_frameworks_with_status(db, tenant_id=tenant_id)

    keys = {f["key"] for f in frameworks}
    assert {"soc2_type2", "iso27001"} <= keys
    soc2 = next(f for f in frameworks if f["key"] == "soc2_type2")
    assert len(soc2["controls"]) == 5
    assert all(c["status"] == "not_met" for c in soc2["controls"])
    assert soc2["score"] == 0


async def test_update_control_status_upserts_and_recomputes_score(db):
    tenant_id = await _make_tenant(db, "Compliance Score Co")
    controls = await _soc2_controls(db)
    actor_id = await _make_user(db, "actor@compliance-score.example")

    await compliance_service.update_control_status(
        db, tenant_id=tenant_id, control_id=controls[0].id, status="met", note="Reviewed access logs.",
        actor_user_id=actor_id,
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    frameworks = await compliance_service.list_frameworks_with_status(db, tenant_id=tenant_id)
    soc2 = next(f for f in frameworks if f["key"] == "soc2_type2")
    assert soc2["score"] == 20  # 1 of 5 met
    met_control = next(c for c in soc2["controls"] if c["id"] == controls[0].id)
    assert met_control["status"] == "met"
    assert met_control["note"] == "Reviewed access logs."
    assert met_control["updated_by_user_id"] == actor_id


async def test_partial_status_counts_as_half_credit(db):
    tenant_id = await _make_tenant(db, "Compliance Partial Co")
    controls = await _soc2_controls(db)
    actor_id = await _make_user(db, "actor@compliance-partial.example")

    await compliance_service.update_control_status(
        db, tenant_id=tenant_id, control_id=controls[0].id, status="partial", note=None,
        actor_user_id=actor_id,
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    frameworks = await compliance_service.list_frameworks_with_status(db, tenant_id=tenant_id)
    soc2 = next(f for f in frameworks if f["key"] == "soc2_type2")
    assert soc2["score"] == 10  # 0.5 of 5 controls


async def test_not_applicable_controls_excluded_from_score(db):
    tenant_id = await _make_tenant(db, "Compliance NA Co")
    controls = await _soc2_controls(db)
    actor_id = await _make_user(db, "actor@compliance-na.example")

    for control in controls:
        await compliance_service.update_control_status(
            db, tenant_id=tenant_id, control_id=control.id, status="not_applicable", note=None,
            actor_user_id=actor_id,
        )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    frameworks = await compliance_service.list_frameworks_with_status(db, tenant_id=tenant_id)
    soc2 = next(f for f in frameworks if f["key"] == "soc2_type2")
    assert soc2["score"] == 100  # nothing left to count is treated as fully met, not 0


async def test_update_control_status_unknown_control_raises_not_found(db):
    tenant_id = await _make_tenant(db, "Compliance Missing Co")

    with pytest.raises(NotFoundError):
        await compliance_service.update_control_status(
            db, tenant_id=tenant_id, control_id=uuid.uuid4(), status="met", note=None,
            actor_user_id=uuid.uuid4(),
        )


async def test_compliance_summary_averages_framework_scores(db):
    tenant_id = await _make_tenant(db, "Compliance Summary Co")
    controls = await _soc2_controls(db)
    actor_id = await _make_user(db, "actor@compliance-summary.example")
    for control in controls:
        await compliance_service.update_control_status(
            db, tenant_id=tenant_id, control_id=control.id, status="met", note=None,
            actor_user_id=actor_id,
        )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    summary = await compliance_service.get_compliance_summary(db, tenant_id=tenant_id)
    soc2_score = next(f for f in summary["frameworks"] if f["key"] == "soc2_type2")
    assert soc2_score["score"] == 100
    assert soc2_score["met_count"] == 5
    assert soc2_score["total_count"] == 5
    # ISO framework is untouched (all not_met, score 0) -> overall averages the two.
    assert summary["overall_score"] == 50


async def test_create_evidence_for_compliance_control(db):
    tenant_id = await _make_tenant(db, "Evidence Control Co")
    controls = await _soc2_controls(db)
    actor_id = await _make_user(db, "actor@evidence-control.example")

    evidence = await compliance_service.create_evidence(
        db, tenant_id=tenant_id, title="Access review screenshot", description="Q2 access review.",
        evidence_type="note", source_url=None, target_type="compliance_control",
        target_id=controls[0].id, collected_at=None, created_by_user_id=actor_id,
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    rows = await compliance_service.list_evidence(
        db, tenant_id=tenant_id, target_type="compliance_control", target_id=controls[0].id
    )
    assert [r.id for r in rows] == [evidence.id]


async def test_create_evidence_for_unknown_control_raises_not_found(db):
    tenant_id = await _make_tenant(db, "Evidence Missing Control Co")

    with pytest.raises(NotFoundError):
        await compliance_service.create_evidence(
            db, tenant_id=tenant_id, title="x", description="", evidence_type="note", source_url=None,
            target_type="compliance_control", target_id=uuid.uuid4(), collected_at=None,
            created_by_user_id=uuid.uuid4(),
        )


async def test_create_evidence_for_incident_in_another_tenant_raises_not_found(db):
    tenant_a = await _make_tenant(db, "Evidence Incident A Co")
    actor_id = await _make_user(db, "actor@evidence-incident-a.example")
    incident = await incidents_service.declare_incident(
        db, tenant_id=tenant_a, actor_user_id=actor_id, title="Breach", description="",
        severity="high", finding_ids=[], asset_ids=[],
    )
    await db.commit()

    tenant_b = await _make_tenant(db, "Evidence Incident B Co")
    with pytest.raises(NotFoundError):
        await compliance_service.create_evidence(
            db, tenant_id=tenant_b, title="x", description="", evidence_type="note", source_url=None,
            target_type="incident", target_id=incident.id, collected_at=None,
            created_by_user_id=actor_id,
        )


async def test_create_evidence_rejects_unknown_target_type(db):
    tenant_id = await _make_tenant(db, "Evidence Bad Target Co")

    with pytest.raises(ValidationAppError):
        await compliance_service.create_evidence(
            db, tenant_id=tenant_id, title="x", description="", evidence_type="note", source_url=None,
            target_type="asset", target_id=uuid.uuid4(), collected_at=None, created_by_user_id=uuid.uuid4(),
        )


async def test_delete_evidence_removes_it_from_the_list(db):
    tenant_id = await _make_tenant(db, "Evidence Delete Co")
    controls = await _soc2_controls(db)
    actor_id = await _make_user(db, "actor@evidence-delete.example")
    evidence = await compliance_service.create_evidence(
        db, tenant_id=tenant_id, title="x", description="", evidence_type="note", source_url=None,
        target_type="compliance_control", target_id=controls[0].id, collected_at=None,
        created_by_user_id=actor_id,
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    await compliance_service.delete_evidence(db, tenant_id=tenant_id, evidence_id=evidence.id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    rows = await compliance_service.list_evidence(
        db, tenant_id=tenant_id, target_type="compliance_control", target_id=controls[0].id
    )
    assert rows == []
