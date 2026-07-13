from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import MembershipContext, require_permission
from app.api.serializers import build_lead_detail_out
from app.db.session import get_db
from app.repositories.lead import LeadFilters
from app.schemas.common import MessageResponse
from app.schemas.lead import (
    BulkActionResult,
    LeadAssignRequest,
    LeadBulkAssignRequest,
    LeadBulkStageChangeRequest,
    LeadCreate,
    LeadDetailOut,
    LeadListOut,
    LeadNoteCreate,
    LeadNoteOut,
    LeadOut,
    LeadStageChangeRequest,
    LeadTagRequest,
    LeadUpdate,
    TimelineEntryOut,
)
from app.services.lead_service import LeadService

router = APIRouter(prefix="/tenants/me/leads", tags=["leads"])


@router.get("", response_model=LeadListOut)
def list_leads(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    stage_id: uuid.UUID | None = None,
    service_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    source: str | None = None,
    priority: str | None = None,
    assigned_membership_id: uuid.UUID | None = None,
    tag_id: uuid.UUID | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("leads.view")),
) -> LeadListOut:
    filters = LeadFilters(
        stage_id=stage_id,
        service_id=service_id,
        branch_id=branch_id,
        source=source,
        priority=priority,
        assigned_membership_id=assigned_membership_id,
        tag_id=tag_id,
        search=search,
    )
    result = LeadService(db).list_leads(
        ctx.tenant_id, filters=filters, page=page, page_size=page_size
    )
    return LeadListOut(
        items=[LeadOut.model_validate(lead) for lead in result.items],
        total=result.total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=LeadDetailOut, status_code=201)
def create_lead(
    payload: LeadCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("leads.create")),
) -> LeadDetailOut:
    lead = LeadService(db).create(
        ctx.tenant_id, actor_user_id=ctx.user.id, source="manual", **payload.model_dump()
    )
    db.commit()
    return build_lead_detail_out(lead)


@router.post("/bulk/stage", response_model=BulkActionResult)
def bulk_change_stage(
    payload: LeadBulkStageChangeRequest,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("leads.update")),
) -> BulkActionResult:
    result = LeadService(db).bulk_change_stage(
        ctx.tenant_id,
        payload.lead_ids,
        actor_user_id=ctx.user.id,
        to_stage_id=payload.to_stage_id,
        loss_reason_id=payload.loss_reason_id,
    )
    db.commit()
    return BulkActionResult(**result)


@router.post("/bulk/assign", response_model=BulkActionResult)
def bulk_assign(
    payload: LeadBulkAssignRequest,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("leads.assign")),
) -> BulkActionResult:
    result = LeadService(db).bulk_assign(
        ctx.tenant_id,
        payload.lead_ids,
        actor_user_id=ctx.user.id,
        membership_id=payload.membership_id,
    )
    db.commit()
    return BulkActionResult(**result)


# NOTE: routes below use a dynamic {lead_id} path segment and must stay
# registered after the static "/bulk/..." routes above - FastAPI matches
# routes in registration order, and "/bulk/stage" would otherwise be
# captured by "/{lead_id}/stage" with lead_id="bulk".


@router.get("/{lead_id}", response_model=LeadDetailOut)
def get_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("leads.view")),
) -> LeadDetailOut:
    lead = LeadService(db).get_or_404(ctx.tenant_id, lead_id)
    return build_lead_detail_out(lead)


@router.patch("/{lead_id}", response_model=LeadDetailOut)
def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("leads.update")),
) -> LeadDetailOut:
    lead = LeadService(db).update(
        ctx.tenant_id, lead_id, actor_user_id=ctx.user.id, **payload.model_dump(exclude_unset=True)
    )
    db.commit()
    return build_lead_detail_out(lead)


@router.post("/{lead_id}/stage", response_model=LeadDetailOut)
def change_lead_stage(
    lead_id: uuid.UUID,
    payload: LeadStageChangeRequest,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("leads.update")),
) -> LeadDetailOut:
    lead = LeadService(db).change_stage(
        ctx.tenant_id,
        lead_id,
        actor_user_id=ctx.user.id,
        to_stage_id=payload.to_stage_id,
        loss_reason_id=payload.loss_reason_id,
        reason=payload.reason,
    )
    db.commit()
    return build_lead_detail_out(lead)


@router.post("/{lead_id}/assign", response_model=LeadDetailOut)
def assign_lead(
    lead_id: uuid.UUID,
    payload: LeadAssignRequest,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("leads.assign")),
) -> LeadDetailOut:
    lead = LeadService(db).assign(
        ctx.tenant_id, lead_id, actor_user_id=ctx.user.id, membership_id=payload.membership_id
    )
    db.commit()
    return build_lead_detail_out(lead)


@router.get("/{lead_id}/notes", response_model=list[LeadNoteOut])
def list_lead_notes(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("leads.view")),
) -> list[LeadNoteOut]:
    service = LeadService(db)
    service.get_or_404(ctx.tenant_id, lead_id)
    notes = service.notes.list_for_lead(lead_id)
    return [LeadNoteOut.model_validate(n) for n in notes]


@router.post("/{lead_id}/notes", response_model=LeadNoteOut, status_code=201)
def add_lead_note(
    lead_id: uuid.UUID,
    payload: LeadNoteCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("leads.update")),
) -> LeadNoteOut:
    note = LeadService(db).add_note(
        ctx.tenant_id, lead_id, actor_user_id=ctx.user.id, body=payload.body
    )
    db.commit()
    return LeadNoteOut.model_validate(note)


@router.post("/{lead_id}/tags", response_model=MessageResponse)
def add_lead_tag(
    lead_id: uuid.UUID,
    payload: LeadTagRequest,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("leads.update")),
) -> MessageResponse:
    LeadService(db).add_tag(
        ctx.tenant_id, lead_id, actor_user_id=ctx.user.id, tag_id=payload.tag_id
    )
    db.commit()
    return MessageResponse(message="Tag added.")


@router.delete("/{lead_id}/tags/{tag_id}", response_model=MessageResponse)
def remove_lead_tag(
    lead_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("leads.update")),
) -> MessageResponse:
    LeadService(db).remove_tag(ctx.tenant_id, lead_id, actor_user_id=ctx.user.id, tag_id=tag_id)
    db.commit()
    return MessageResponse(message="Tag removed.")


@router.get("/{lead_id}/timeline", response_model=list[TimelineEntryOut])
def get_lead_timeline(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("leads.view")),
) -> list[TimelineEntryOut]:
    entries = LeadService(db).get_timeline(ctx.tenant_id, lead_id)
    return [TimelineEntryOut.model_validate(e) for e in entries]
