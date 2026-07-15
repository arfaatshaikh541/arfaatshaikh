import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.dependencies.entitlements import require_module
from app.dependencies.permissions import require_permission
from app.modules.deadlines import service as deadlines_service
from app.modules.deadlines.models import DeadlineStatus
from app.modules.deadlines.schemas import CreateDeadlineRequest

router = APIRouter(prefix="/tenant/deadlines", tags=["deadlines"])


def _deadline_to_dict(deadline) -> dict:
    return {
        "id": str(deadline.id), "lead_id": str(deadline.lead_id), "title": deadline.title, "description": deadline.description,
        "due_date": deadline.due_date.isoformat(), "status": deadline.status.value,
        "recurrence_interval_days": deadline.recurrence_interval_days,
        "completed_at": deadline.completed_at.isoformat() if deadline.completed_at else None,
    }


@router.get("")
def list_deadlines(
    lead_id: uuid.UUID | None = None, status: DeadlineStatus | None = None,
    ctx: TenantContext = Depends(require_permission("deadlines.manage")),
    _mod: TenantContext = Depends(require_module("deadline_tracking")), db: Session = Depends(get_db),
) -> list[dict]:
    deadlines = (
        deadlines_service.list_deadlines_for_lead(db, ctx.tenant_id, lead_id) if lead_id
        else deadlines_service.list_deadlines_for_tenant(db, ctx.tenant_id, status=status)
    )
    return [_deadline_to_dict(d) for d in deadlines]


@router.post("", status_code=201)
def create_deadline(
    payload: CreateDeadlineRequest, ctx: TenantContext = Depends(require_permission("deadlines.manage")),
    _mod: TenantContext = Depends(require_module("deadline_tracking")), db: Session = Depends(get_db),
) -> dict:
    deadline = deadlines_service.create_deadline(
        db, tenant_id=ctx.tenant_id, lead_id=payload.lead_id, title=payload.title, description=payload.description,
        due_date=payload.due_date, recurrence_interval_days=payload.recurrence_interval_days, created_by=ctx.user_id,
    )
    return _deadline_to_dict(deadline)


@router.post("/{deadline_id}/complete")
def complete_deadline(
    deadline_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("deadlines.manage")),
    _mod: TenantContext = Depends(require_module("deadline_tracking")), db: Session = Depends(get_db),
) -> dict:
    deadline = deadlines_service.get_deadline_or_404(db, ctx.tenant_id, deadline_id)
    deadline = deadlines_service.complete_deadline(db, tenant_id=ctx.tenant_id, deadline=deadline, actor_id=ctx.user_id)
    return _deadline_to_dict(deadline)
