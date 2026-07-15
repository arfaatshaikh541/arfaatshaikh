"""Exercises the Celery worker's maintenance task logic directly (not
through a broker — that path is verified manually, see
docs/project-status.md). Uses the same gridkeep_test database as the rest
of the backend suite."""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # apps/ (for the `worker` package)

from worker.tasks import (  # noqa: E402
    _cleanup_expired_sessions_async,
    _expire_support_access_grants_async,
)

from db.session import AsyncSessionLocal, set_tenant_context  # noqa: E402
from modules.identity.models import Session as SessionModel  # noqa: E402
from modules.identity.models import User  # noqa: E402
from modules.platform_admin.models import SupportAccessGrant  # noqa: E402
from modules.tenancy.models import Tenant  # noqa: E402

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_cleanup_expired_sessions_removes_only_old_ones(db):
    now = datetime.now(UTC)
    user = User(
        email=f"worker-test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        full_name="Worker Test",
        email_verified=True,
    )
    db.add(user)
    await db.flush()

    old_expired = SessionModel(
        user_id=user.id, token_hash=uuid.uuid4().hex, expires_at=now - timedelta(days=10)
    )
    recently_expired = SessionModel(
        user_id=user.id, token_hash=uuid.uuid4().hex, expires_at=now - timedelta(hours=1)
    )
    still_valid = SessionModel(
        user_id=user.id, token_hash=uuid.uuid4().hex, expires_at=now + timedelta(hours=1)
    )
    db.add_all([old_expired, recently_expired, still_valid])
    await db.commit()

    deleted = await _cleanup_expired_sessions_async()
    assert deleted >= 1

    remaining_ids = {
        row[0]
        for row in (
            await db.execute(
                select(SessionModel.id).where(
                    SessionModel.id.in_([old_expired.id, recently_expired.id, still_valid.id])
                )
            )
        ).all()
    }
    assert old_expired.id not in remaining_ids
    assert recently_expired.id in remaining_ids
    assert still_valid.id in remaining_ids


async def test_expire_support_access_grants_flips_status(db):
    tenant_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        slug = f"worker-grant-{tenant_id.hex[:8]}"
        session.add(Tenant(id=tenant_id, name="Worker Grant Co", slug=slug, status="active"))
        await session.flush()

        platform_user = User(
            email=f"worker-platform-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="x",
            full_name="Platform",
            email_verified=True,
            is_platform_user=True,
        )
        session.add(platform_user)
        await session.flush()

        now = datetime.now(UTC)
        grant = SupportAccessGrant(
            tenant_id=tenant_id,
            platform_user_id=platform_user.id,
            requested_by_user_id=platform_user.id,
            reason="Test grant for worker sweep",
            status="active",
            starts_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),  # already expired
        )
        session.add(grant)
        await session.commit()
        grant_id = grant.id

    expired_count = await _expire_support_access_grants_async()
    assert expired_count >= 1

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        row = (
            await session.execute(select(SupportAccessGrant).where(SupportAccessGrant.id == grant_id))
        ).scalar_one()
        assert row.status == "expired"
