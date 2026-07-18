"""Orchestration for the Lead Workspace (Milestone 6): status changes,
assignment, notes, tags, bulk actions, and saved-view ownership.

Permission checks for a *single* action already happen at the route
layer via `require_permission` - this module handles the parts that
aren't a single fixed permission check: validating a status value,
recording history, and (for bulk actions) applying one action to many
leads inside one transaction so a partial failure can't leave some leads
changed and others not.

Lead status has no transition state machine - see `models.py`'s module
docstring and docs/adr/0014. `change_status`/`bulk_change_status` only
validate that the target is one of `LEAD_STATUSES`.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError, ValidationAppError
from app.modules.leads import repositories as repo
from app.modules.leads.models import LEAD_STATUSES, Lead, LeadNote, LeadTag


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def change_status(
    session: AsyncSession,
    *,
    lead_id: uuid.UUID,
    to_status: str,
    actor_user_id: uuid.UUID | None,
    note: str | None = None,
) -> Lead:
    if to_status not in LEAD_STATUSES:
        raise ValidationAppError(f"'{to_status}' is not a valid lead status.")
    lead = await repo.get_lead_or_raise(session, lead_id)
    if lead.status == to_status:
        return lead
    await repo.record_status_change(
        session,
        tenant_id=lead.tenant_id,
        lead_id=lead.id,
        from_status=lead.status,
        to_status=to_status,
        changed_by_user_id=actor_user_id,
        changed_at=_utcnow(),
        note=note,
    )
    lead.status = to_status
    return lead


async def bulk_change_status(
    session: AsyncSession,
    *,
    lead_ids: list[uuid.UUID],
    to_status: str,
    actor_user_id: uuid.UUID | None,
) -> list[Lead]:
    return [
        await change_status(session, lead_id=lid, to_status=to_status, actor_user_id=actor_user_id)
        for lid in lead_ids
    ]


async def assign_lead(
    session: AsyncSession,
    *,
    lead_id: uuid.UUID,
    assigned_to_user_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> Lead:
    lead = await repo.get_lead_or_raise(session, lead_id)
    now = _utcnow()
    open_assignment = await repo.get_open_assignment(session, lead_id)
    if open_assignment is not None:
        if open_assignment.assigned_to_user_id == assigned_to_user_id:
            return lead
        open_assignment.unassigned_at = now
    await repo.create_assignment(
        session,
        tenant_id=lead.tenant_id,
        lead_id=lead.id,
        assigned_to_user_id=assigned_to_user_id,
        assigned_by_user_id=actor_user_id,
        assigned_at=now,
    )
    lead.assigned_to_user_id = assigned_to_user_id
    return lead


async def unassign_lead(
    session: AsyncSession, *, lead_id: uuid.UUID, actor_user_id: uuid.UUID | None
) -> Lead:
    lead = await repo.get_lead_or_raise(session, lead_id)
    open_assignment = await repo.get_open_assignment(session, lead_id)
    if open_assignment is not None:
        open_assignment.unassigned_at = _utcnow()
    lead.assigned_to_user_id = None
    return lead


async def bulk_assign(
    session: AsyncSession,
    *,
    lead_ids: list[uuid.UUID],
    assigned_to_user_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> list[Lead]:
    return [
        await assign_lead(
            session,
            lead_id=lid,
            assigned_to_user_id=assigned_to_user_id,
            actor_user_id=actor_user_id,
        )
        for lid in lead_ids
    ]


async def add_note(
    session: AsyncSession, *, lead_id: uuid.UUID, author_user_id: uuid.UUID | None, body: str
) -> LeadNote:
    if not body.strip():
        raise ValidationAppError("Note body cannot be empty.")
    lead = await repo.get_lead_or_raise(session, lead_id)
    return await repo.create_note(
        session, tenant_id=lead.tenant_id, lead_id=lead.id, author_user_id=author_user_id, body=body
    )


async def add_tag(
    session: AsyncSession, *, lead_id: uuid.UUID, tag: str, actor_user_id: uuid.UUID | None
) -> LeadTag:
    normalized = tag.strip().lower()
    if not normalized:
        raise ValidationAppError("Tag cannot be empty.")
    lead = await repo.get_lead_or_raise(session, lead_id)
    return await repo.add_tag(
        session,
        tenant_id=lead.tenant_id,
        lead_id=lead.id,
        tag=normalized,
        created_by_user_id=actor_user_id,
    )


async def bulk_add_tag(
    session: AsyncSession, *, lead_ids: list[uuid.UUID], tag: str, actor_user_id: uuid.UUID | None
) -> None:
    for lead_id in lead_ids:
        await add_tag(session, lead_id=lead_id, tag=tag, actor_user_id=actor_user_id)


async def delete_saved_view(
    session: AsyncSession, *, view_id: uuid.UUID, actor_user_id: uuid.UUID, actor_can_edit: bool
) -> None:
    """Any tenant member with `leads.view` can create/see a saved view
    (they're shared tenant-wide, like everything else in this schema),
    but only its creator - or someone with the broader `leads.edit`
    permission - may delete it. `actor_can_edit` is the caller's own
    `leads.edit` membership already resolved by the route from
    `TenantContext.permissions`, not re-derived here."""
    view = await repo.get_saved_view_or_raise(session, view_id)
    if view.created_by_user_id != actor_user_id and not actor_can_edit:
        raise PermissionDeniedError("Only the creator of this saved view may delete it.")
    await session.delete(view)
