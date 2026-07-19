"""`run_csv_import` - the Celery task that turns an uploaded, column-
mapped CSV file into real `Business` rows: download the file, parse each
row, feed it through the exact same `businesses.repositories.
upsert_business_from_discovery` -> `businesses.dedup.
process_new_business_for_duplicates` pipeline `worker.campaign_tasks`
already uses for campaign-discovered businesses (see
`csv_import.models`'s module docstring for why this reuses that pipeline
rather than a bespoke one), and record the result.

Each row runs inside its own `SAVEPOINT` (`session.begin_nested()`) so
one row's database-level failure (a rare edge case - most bad rows are
caught earlier by `parsing.build_record_or_raise` before any query runs)
rolls back only that row, not the whole import - the same "partial
completion" principle `worker.export_tasks` already applies to per-lead
export failures, applied here to per-row import failures.
"""

import hashlib
import uuid
from datetime import UTC, datetime

from app.core.db import AsyncSessionLocal, set_platform_bypass, set_tenant_context
from app.core.logging import configure_logging, get_logger
from app.core.storage import download_bytes
from app.modules.businesses import dedup as businesses_dedup
from app.modules.businesses import repositories as businesses_repo
from app.modules.businesses.normalize import normalize_address, normalize_name, normalize_phone
from app.modules.csv_import import repositories as csv_import_repo
from app.modules.csv_import.parsing import (
    CsvParseError,
    build_record_or_raise,
    read_headers_and_rows,
)
from app.modules.usage.services import commit_reservation

from worker.async_utils import run_db_task
from worker.celery_app import celery_app

logger = get_logger("gridkeep.worker.csv_import")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _source_native_id(record: dict) -> str:
    """A stable id derived from the row's own identifying fields, not a
    row index - so re-importing the same file (or a file with the same
    businesses in a different order) is idempotent at the source-record
    layer, the same "re-discovery updates the existing row" behavior a
    connector's own natural id already gives campaigns."""
    key = "|".join(
        [
            normalize_name(str(record.get("name", ""))),
            normalize_address(str(record.get("address", ""))) if record.get("address") else "",
            normalize_phone(str(record["phone"])) or "" if record.get("phone") else "",
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:40]


async def _finalize_failed(csv_import_id_str: str, message: str) -> None:
    csv_import_id = uuid.UUID(csv_import_id_str)
    async with AsyncSessionLocal() as session:
        await set_platform_bypass(session)
        csv_import = await csv_import_repo.get_csv_import(session, csv_import_id)
        if csv_import is None:
            return
        await set_tenant_context(session, csv_import.tenant_id)
        await csv_import_repo.mark_failed(
            session, csv_import, completed_at=_utcnow(), message=message
        )
        await session.commit()


async def _run_csv_import_async(csv_import_id_str: str) -> None:
    csv_import_id = uuid.UUID(csv_import_id_str)

    async with AsyncSessionLocal() as session:
        # Same reasoning as every other worker task (ADR-0007): the
        # tenant isn't known until this lookup finds it.
        await set_platform_bypass(session)
        csv_import = await csv_import_repo.get_csv_import_or_raise(session, csv_import_id)
        tenant_id = csv_import.tenant_id

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        csv_import = await csv_import_repo.get_csv_import_or_raise(session, csv_import_id)
        if csv_import.status in ("completed", "failed"):
            return  # already handled - a terminal state, unlike a campaign/export/
            # delivery task's single "pending" gate, "processing" here must stay
            # re-enterable: a retry after a mid-batch transient failure re-runs the
            # whole row loop, which is safe because `upsert_business_from_discovery`
            # is idempotent per row (keyed on a stable `source_native_id`, not a
            # row index) - re-processing an already-imported row just re-upserts it.
        await csv_import_repo.mark_processing(session, csv_import, started_at=_utcnow())
        await session.commit()
        # `set_tenant_context` uses SET LOCAL (see core.db's own
        # docstring) - scoped to the transaction the commit above just
        # ended, so it must be re-applied before any further RLS-
        # protected query in this session, exactly the class of bug
        # ADR-0007/`worker.campaign_tasks` already found and fixed once.
        await set_tenant_context(session, tenant_id)

        column_mapping = csv_import.column_mapping or {}
        file_bytes = download_bytes(key=csv_import.object_key)
        _headers, rows = read_headers_and_rows(file_bytes)

        imported_count = 0
        error_count = 0
        for row_number, row in enumerate(rows, start=1):
            try:
                record = build_record_or_raise(row, column_mapping, row_number=row_number)
            except CsvParseError as exc:
                await csv_import_repo.create_import_error(
                    session,
                    tenant_id=tenant_id,
                    csv_import_id=csv_import_id,
                    row_number=row_number,
                    message=str(exc),
                )
                error_count += 1
                continue

            record["source"] = "csv_import"
            record["source_native_id"] = _source_native_id(record)
            record["collected_at"] = _utcnow().isoformat()

            try:
                async with session.begin_nested():
                    business = await businesses_repo.upsert_business_from_discovery(
                        session, tenant_id=tenant_id, campaign_id=None, record=record
                    )
                    await businesses_dedup.process_new_business_for_duplicates(session, business)
                imported_count += 1
            except Exception as exc:  # noqa: BLE001 - one bad row must not abort
                # the whole import; every other kind of row-level failure
                # (a database constraint, an unexpected data shape) is
                # recorded and the import continues, per the module
                # docstring's partial-completion principle.
                logger.warning(
                    "csv_import_row_error",
                    csv_import_id=csv_import_id_str,
                    row_number=row_number,
                    error=str(exc),
                )
                await csv_import_repo.create_import_error(
                    session,
                    tenant_id=tenant_id,
                    csv_import_id=csv_import_id,
                    row_number=row_number,
                    message=str(exc)[:2000],
                )
                error_count += 1

        if csv_import.reservation_id is not None:
            await commit_reservation(
                session,
                reservation_id=csv_import.reservation_id,
                actual_amount=float(imported_count),
                created_by_user_id=csv_import.requested_by_user_id,
            )

        await csv_import_repo.mark_completed(
            session,
            csv_import,
            completed_at=_utcnow(),
            imported_count=imported_count,
            error_count=error_count,
        )
        await session.commit()


@celery_app.task(bind=True, name="worker.csv_import_tasks.run_csv_import", max_retries=2)
def run_csv_import(self, csv_import_id: str) -> None:
    configure_logging()
    try:
        run_db_task(_run_csv_import_async(csv_import_id))
    except Exception as exc:  # noqa: BLE001 - any unexpected failure (storage,
        # database, the file itself being unreadable) should fail the
        # import cleanly rather than leave it stuck "processing" forever,
        # while still retrying a bounded number of times for transient
        # issues (e.g. object storage briefly unreachable).
        logger.warning(
            "csv_import_task_error",
            csv_import_id=csv_import_id,
            error=str(exc),
            attempt=self.request.retries,
        )
        # Check retries-exhausted *before* calling retry() - see
        # docs/adr/0016: Celery's retry() re-raises the original `exc`
        # (not MaxRetriesExceededError) once retries are exhausted
        # whenever exc= is passed, so a try/except MaxRetriesExceededError
        # around this call never actually catches anything.
        if self.request.retries >= self.max_retries:
            run_db_task(_finalize_failed(csv_import_id, str(exc)))
        else:
            raise self.retry(exc=exc, countdown=min(60, 5 * (2**self.request.retries))) from exc
