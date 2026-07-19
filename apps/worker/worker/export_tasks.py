"""`run_export` - the Celery task that turns a persisted `Export` request
into an actual XLSX/CSV file: re-resolve the lead selection against
current data, assemble every row (business, score, opportunities,
recommendations, assignment, notes, source provenance, social evidence),
build the workbook/CSV, upload it to object storage, and record the
result. Modeled directly on `worker.enrichment_tasks.run_business_
enrichment` - same two-phase "look up tenant with the bypass in place,
then do the real work under tenant RLS" shape, same bounded-retry-then-
fail-cleanly error handling.

A lead that fails to resolve (deleted, or its business lost a dedup merge
between request and execution) does not fail the whole export - it is
recorded as an `ExportError` row and the export still completes with
whatever rows *did* resolve. This is what "partial completion" means for
an export (see docs/adr/0015): the job either fully fails (couldn't reach
object storage, couldn't query the database at all) or completes with an
accurate row/error count, never silently drops rows without saying so.
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal, set_platform_bypass, set_tenant_context
from app.core.logging import configure_logging, get_logger
from app.core.storage import object_key_for_export, upload_bytes
from app.modules.campaigns import repositories as campaigns_repo
from app.modules.exports import repositories as exports_repo
from app.modules.exports import services as exports_services
from app.modules.exports.data import build_export_rows
from app.modules.exports.workbook import build_csv, build_xlsx

from worker.async_utils import run_db_task
from worker.celery_app import celery_app
from worker.retry import default_backoff, retry_or_finalize

logger = get_logger("gridkeep.worker.exports")

_CONTENT_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _run_export_async(export_id_str: str) -> None:
    export_id = uuid.UUID(export_id_str)

    async with AsyncSessionLocal() as session:
        # Same reasoning as worker.enrichment_tasks/worker.campaign_tasks
        # (ADR-0007): the tenant isn't known until this lookup finds it.
        await set_platform_bypass(session)
        export = await exports_repo.get_export_or_raise(session, export_id)
        tenant_id = export.tenant_id

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        export = await exports_repo.get_export_or_raise(session, export_id)
        if export.status != "pending":
            return  # duplicate delivery or already handled by another worker
        await exports_repo.mark_processing(session, export, started_at=_utcnow())
        lead_ids = await exports_services.resolve_lead_ids(
            session, tenant_id=tenant_id, selection=export.selection
        )
        rows, resolution_errors = await build_export_rows(
            session, tenant_id=tenant_id, lead_ids=lead_ids
        )

        campaign_ids = {row.campaign_id for row in rows if row.campaign_id is not None}
        campaigns_by_id = await campaigns_repo.list_campaigns_by_ids(session, list(campaign_ids))

        if export.format == "xlsx":
            file_bytes = build_xlsx(
                rows,
                [
                    (str(lead_id) if lead_id else None, message)
                    for lead_id, message in resolution_errors
                ],
                campaigns_by_id=campaigns_by_id,
            )
        else:
            file_bytes = build_csv(rows)

        for lead_id, message in resolution_errors:
            await exports_repo.create_export_error(
                session, tenant_id=tenant_id, export_id=export_id, lead_id=lead_id, message=message
            )

        key = object_key_for_export(
            tenant_id=str(tenant_id), export_id=str(export_id), extension=export.format
        )
        file_size = upload_bytes(
            key=key, data=file_bytes, content_type=_CONTENT_TYPES[export.format]
        )

        now = _utcnow()
        retention_days = get_settings().export_retention_days
        await exports_repo.mark_completed(
            session,
            export,
            completed_at=now,
            object_key=key,
            file_size_bytes=file_size,
            row_count=len(rows),
            error_count=len(resolution_errors),
            expires_at=now + timedelta(days=retention_days),
        )
        await session.commit()


@celery_app.task(bind=True, name="worker.export_tasks.run_export", max_retries=3)
def run_export(self, export_id: str) -> None:
    configure_logging()
    try:
        run_db_task(_run_export_async(export_id))
    except Exception as exc:  # noqa: BLE001 - any unexpected failure (DB, storage,
        # workbook generation) should fail the export cleanly rather than
        # leave it stuck "processing" forever, while still retrying a
        # bounded number of times for transient issues (e.g. object
        # storage briefly unreachable).
        logger.warning(
            "export_task_error", export_id=export_id, error=str(exc), attempt=self.request.retries
        )
        error = exc  # `except ... as exc` unbinds exc when this block exits;
        # the lambda below is a deferred closure, so it must capture a
        # plain local name instead (see worker.retry's own docstring).
        retry_or_finalize(
            self,
            exc=exc,
            finalize=lambda: _finalize_failed_after_error(export_id, str(error)),
            countdown=default_backoff(self.request.retries),
            task_name="run_export",
            task_id=export_id,
        )


async def _finalize_failed_after_error(export_id_str: str, message: str) -> None:
    export_id = uuid.UUID(export_id_str)
    async with AsyncSessionLocal() as session:
        await set_platform_bypass(session)
        export = await exports_repo.get_export(session, export_id)
        if export is None:
            return
        await set_tenant_context(session, export.tenant_id)
        await exports_repo.mark_failed(session, export, completed_at=_utcnow(), message=message)
        await session.commit()
