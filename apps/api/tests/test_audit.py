import uuid

import pytest
from sqlalchemy import select, text

from db.session import AsyncSessionLocal, set_tenant_context
from modules.audit import service as audit_service
from modules.audit.models import AuditLog
from tests.helpers import login, onboard_verified_owner

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_login_creates_audit_record(client, db):
    await onboard_verified_owner(
        client, db, org_name="Audit Co", full_name="Owner", email="owner@audit-co.example",
        password="Owner-Pass1!",
    )
    resp = await login(client, "owner@audit-co.example", "Owner-Pass1!")
    assert resp.status_code == 200
    user_id = uuid.UUID(resp.json()["user"]["id"])

    async with AsyncSessionLocal() as session:
        # Platform-level audit rows (tenant_id IS NULL, e.g. login/logout
        # before a tenant is selected) are only visible under the
        # `is_platform_admin` RLS branch — reading them here as a stand-in
        # for a platform auditor.
        await set_tenant_context(session, uuid.uuid4(), is_platform_admin=True)
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.actor_user_id == user_id, AuditLog.action == "auth.login")
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].tenant_id is None  # login happens before a tenant is selected


async def test_audit_log_is_append_only_update_has_no_effect(db):
    """FORCE ROW LEVEL SECURITY with no UPDATE policy denies the command by
    filtering it to zero matching rows — it doesn't raise, so the way to
    observe append-only-ness is that the row is unchanged afterwards."""
    tenant_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        entry = await audit_service.record(
            session,
            tenant_id=tenant_id,
            actor_user_id=None,
            actor_label="test-actor",
            action="test.append_only_check",
        )
        await session.commit()
        entry_id = entry.id

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        result = await session.execute(
            text("UPDATE audit_logs SET action = 'tampered' WHERE id = :id"), {"id": entry_id}
        )
        await session.commit()
        assert result.rowcount == 0

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        row = (await session.execute(select(AuditLog).where(AuditLog.id == entry_id))).scalar_one()
        assert row.action == "test.append_only_check"


async def test_audit_log_is_append_only_delete_has_no_effect(db):
    tenant_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        entry = await audit_service.record(
            session,
            tenant_id=tenant_id,
            actor_user_id=None,
            actor_label="test-actor",
            action="test.delete_check",
        )
        await session.commit()
        entry_id = entry.id

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        result = await session.execute(text("DELETE FROM audit_logs WHERE id = :id"), {"id": entry_id})
        await session.commit()
        assert result.rowcount == 0

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        row = (await session.execute(select(AuditLog).where(AuditLog.id == entry_id))).scalar_one()
        assert row.action == "test.delete_check"
