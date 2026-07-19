"""Tests for `worker.export_cleanup_tasks` - the periodic sweep
(Milestone 14, docs/adr/0022) that deletes a completed export's
underlying object storage file once its retention period
(`Export.expires_at`, set by `worker.export_tasks` on completion) has
passed, and marks the row `storage_deleted_at`.

Same "call the private async function directly, bypass the Celery
broker" approach `test_export_tasks.py` already established, and the same
`moto_s3` real-local-S3-server fixture (no MinIO binary is installable in
this sandbox - see docs/adr/0015).
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import get_settings
from app.modules.exports import repositories as exports_repo
from app.modules.exports.models import Export
from app.modules.tenancy import repositories as tenancy_repo
from botocore.exceptions import ClientError
from sqlalchemy.ext.asyncio import async_sessionmaker
from worker import export_cleanup_tasks as ect

pytestmark = pytest.mark.asyncio


async def _make_tenant(session):
    return await tenancy_repo.create_tenant(
        session, name="Export Cleanup Test Co", slug=f"exp-cleanup-{uuid.uuid4().hex[:10]}"
    )


def _object_key(tenant_id, export_id: uuid.UUID) -> str:
    return f"tenants/{tenant_id}/exports/{export_id}/export.csv"


async def _make_completed_export(
    session, moto_s3, *, tenant_id, expires_at, storage_deleted_at=None, upload_object=True
) -> Export:
    export_id = uuid.uuid4()
    key = _object_key(tenant_id, export_id)
    if upload_object:
        settings = get_settings()
        moto_s3.put_object(
            Bucket=settings.s3_bucket_name, Key=key, Body=b"business,city\nAcme,Springfield\n"
        )
    export = Export(
        id=export_id,
        tenant_id=tenant_id,
        requested_by_user_id=None,
        format="csv",
        status="completed",
        selection={"mode": "lead_ids", "lead_ids": []},
        object_key=key,
        row_count=1,
        error_count=0,
        completed_at=datetime.now(UTC),
        expires_at=expires_at,
        storage_deleted_at=storage_deleted_at,
    )
    session.add(export)
    await session.flush()
    await session.commit()
    return export


async def _refresh(migrator_session, export_id) -> Export:
    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    async with session_factory() as verify_session:
        refreshed = await exports_repo.get_export(verify_session, export_id)
        assert refreshed is not None
        return refreshed


def _object_exists(moto_s3, key: str) -> bool:
    settings = get_settings()
    try:
        moto_s3.get_object(Bucket=settings.s3_bucket_name, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return False
        raise
    return True


async def test_cleanup_deletes_object_and_marks_storage_deleted_for_an_expired_export(
    migrator_session, moto_s3
):
    tenant = await _make_tenant(migrator_session)
    export = await _make_completed_export(
        migrator_session,
        moto_s3,
        tenant_id=tenant.id,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    count = await ect._cleanup_expired_exports_async()
    assert count == 1

    refreshed = await _refresh(migrator_session, export.id)
    assert refreshed.storage_deleted_at is not None
    assert not _object_exists(moto_s3, export.object_key)


async def test_cleanup_skips_an_export_whose_retention_has_not_expired_yet(
    migrator_session, moto_s3
):
    tenant = await _make_tenant(migrator_session)
    export = await _make_completed_export(
        migrator_session,
        moto_s3,
        tenant_id=tenant.id,
        expires_at=datetime.now(UTC) + timedelta(days=29),
    )

    count = await ect._cleanup_expired_exports_async()
    assert count == 0

    refreshed = await _refresh(migrator_session, export.id)
    assert refreshed.storage_deleted_at is None
    assert _object_exists(moto_s3, export.object_key)


async def test_cleanup_skips_an_export_already_cleaned_up(migrator_session, moto_s3):
    tenant = await _make_tenant(migrator_session)
    already_cleaned_at = datetime.now(UTC) - timedelta(hours=1)
    export = await _make_completed_export(
        migrator_session,
        moto_s3,
        tenant_id=tenant.id,
        expires_at=datetime.now(UTC) - timedelta(days=1),
        storage_deleted_at=already_cleaned_at,
        upload_object=False,  # the object is long gone - a real prior sweep already deleted it
    )

    count = await ect._cleanup_expired_exports_async()
    assert count == 0  # excluded by the query filter, not re-processed

    refreshed = await _refresh(migrator_session, export.id)
    assert refreshed.storage_deleted_at == already_cleaned_at


async def test_cleanup_is_idempotent_when_the_object_is_already_gone(migrator_session, moto_s3):
    """The exact crash-window this task's own idempotency is meant to
    survive: a previous sweep deleted the object but crashed before
    marking the row - `storage_deleted_at` is still unset, so this run
    must retry the deletion (a no-op against S3, per `delete_object`'s own
    idempotent design) and finish marking the row, not error out."""
    tenant = await _make_tenant(migrator_session)
    export = await _make_completed_export(
        migrator_session,
        moto_s3,
        tenant_id=tenant.id,
        expires_at=datetime.now(UTC) - timedelta(days=1),
        upload_object=False,
    )

    count = await ect._cleanup_expired_exports_async()
    assert count == 1

    refreshed = await _refresh(migrator_session, export.id)
    assert refreshed.storage_deleted_at is not None
