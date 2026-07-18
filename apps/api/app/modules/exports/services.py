import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_client import enqueue_export
from app.core.exceptions import ConflictError
from app.core.storage import presigned_download_url
from app.modules.exports import repositories as exports_repo
from app.modules.exports.models import Export
from app.modules.exports.schemas import CreateExportRequest, ExportFiltersRequest
from app.modules.leads import repositories as leads_repo
from app.modules.leads.repositories import LeadListFilters


async def request_export(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    requested_by_user_id: uuid.UUID | None,
    request: CreateExportRequest,
) -> Export:
    """Persists the export's *selection* (what to export), not its
    resolved lead list - the actual lead ids are re-resolved by the
    Celery task at execution time, against the tenant's data as it exists
    when the job actually runs, not a snapshot frozen at request time.
    This is deliberate: an export queued behind a backlog should reflect
    any status/tag/assignment changes made in the meantime, the same way
    a campaign's task queue re-reads current state rather than replaying
    a stale plan."""
    selection: dict[str, object]
    if request.lead_ids is not None:
        selection = {"mode": "lead_ids", "lead_ids": [str(i) for i in request.lead_ids]}
    else:
        filters = request.filters or ExportFiltersRequest()
        selection = {"mode": "filters", "filters": filters.model_dump(mode="json")}

    export = await exports_repo.create_export(
        session,
        tenant_id=tenant_id,
        requested_by_user_id=requested_by_user_id,
        format=request.format,
        selection=selection,
    )
    await session.commit()
    enqueue_export(str(export.id))
    return export


async def resolve_lead_ids(
    session: AsyncSession, *, tenant_id: uuid.UUID, selection: dict
) -> list[uuid.UUID]:
    """Turns a persisted `Export.selection` back into a concrete lead id
    list - called by the Celery export task at execution time (see
    `request_export`'s docstring for why re-resolution, not a frozen
    snapshot, is deliberate)."""
    if selection.get("mode") == "lead_ids":
        return [uuid.UUID(i) for i in selection.get("lead_ids", [])]

    raw_filters = selection.get("filters", {})
    parsed = ExportFiltersRequest.model_validate(raw_filters)
    filters = LeadListFilters(
        statuses=parsed.status,
        assigned_to_user_id=parsed.assigned_to_user_id,
        unassigned_only=parsed.unassigned_only,
        tag=parsed.tag,
        opportunity_type=parsed.opportunity_type,
        category=parsed.category,
        city=parsed.city,
        country=parsed.country,
        area=parsed.area,
        min_score=parsed.min_score,
        max_score=parsed.max_score,
        search=parsed.search,
    )
    return await leads_repo.list_all_lead_ids_matching_filters(
        session,
        tenant_id=tenant_id,
        filters=filters,
        sort_by=parsed.sort_by,
        sort_dir=parsed.sort_dir,
    )


async def get_download_url(session: AsyncSession, export: Export) -> tuple[str, int, str]:
    if export.status != "completed" or not export.object_key:
        raise ConflictError("This export is not ready for download yet.")
    extension = export.format
    filename = f"gridkeep-leads-export-{export.id}.{extension}"
    expires_in_seconds = 900
    url = presigned_download_url(
        key=export.object_key, filename=filename, expires_in_seconds=expires_in_seconds
    )
    return url, expires_in_seconds, filename
