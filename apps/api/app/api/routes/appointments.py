from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import MembershipContext, require_permission
from app.db.session import get_db
from app.repositories.appointment import AppointmentFilters
from app.schemas.appointment import (
    AppointmentCancelRequest,
    AppointmentCreate,
    AppointmentListOut,
    AppointmentOut,
    AppointmentRescheduleRequest,
    TimeSlotOut,
)
from app.services.appointment_service import AppointmentService
from app.services.availability_service import AvailabilityService

router = APIRouter(prefix="/tenants/me/appointments", tags=["appointments"])


@router.get("/available-slots", response_model=list[TimeSlotOut])
def get_available_slots(
    on_date: date,
    assigned_membership_id: uuid.UUID | None = None,
    duration_minutes: int = Query(default=30, ge=5, le=480),
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("appointments.manage")),
) -> list[TimeSlotOut]:
    slots = AvailabilityService(db).available_slots(
        ctx.tenant_id,
        assigned_membership_id=assigned_membership_id,
        on_date=on_date,
        duration_minutes=duration_minutes,
    )
    return [TimeSlotOut(starts_at=s.starts_at, ends_at=s.ends_at) for s in slots]


@router.get("", response_model=AppointmentListOut)
def list_appointments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    lead_id: uuid.UUID | None = None,
    assigned_membership_id: uuid.UUID | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("appointments.manage")),
) -> AppointmentListOut:
    filters = AppointmentFilters(
        lead_id=lead_id, assigned_membership_id=assigned_membership_id, status=status
    )
    result = AppointmentService(db).list(
        ctx.tenant_id, filters=filters, page=page, page_size=page_size
    )
    return AppointmentListOut(
        items=[AppointmentOut.model_validate(a) for a in result.items],
        total=result.total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=AppointmentOut, status_code=201)
def create_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("appointments.manage")),
) -> AppointmentOut:
    appointment = AppointmentService(db).create(
        ctx.tenant_id, created_by_user_id=ctx.user.id, **payload.model_dump()
    )
    db.commit()
    return AppointmentOut.model_validate(appointment)


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("appointments.manage")),
) -> AppointmentOut:
    appointment = AppointmentService(db).get_or_404(ctx.tenant_id, appointment_id)
    return AppointmentOut.model_validate(appointment)


@router.post("/{appointment_id}/reschedule", response_model=AppointmentOut)
def reschedule_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentRescheduleRequest,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("appointments.manage")),
) -> AppointmentOut:
    appointment = AppointmentService(db).reschedule(
        ctx.tenant_id, appointment_id, starts_at=payload.starts_at, ends_at=payload.ends_at
    )
    db.commit()
    return AppointmentOut.model_validate(appointment)


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentCancelRequest,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("appointments.manage")),
) -> AppointmentOut:
    appointment = AppointmentService(db).cancel(
        ctx.tenant_id, appointment_id, reason=payload.reason
    )
    db.commit()
    return AppointmentOut.model_validate(appointment)


@router.post("/{appointment_id}/confirm", response_model=AppointmentOut)
def confirm_appointment(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("appointments.manage")),
) -> AppointmentOut:
    appointment = AppointmentService(db).confirm(ctx.tenant_id, appointment_id)
    db.commit()
    return AppointmentOut.model_validate(appointment)


@router.post("/{appointment_id}/complete", response_model=AppointmentOut)
def complete_appointment(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("appointments.manage")),
) -> AppointmentOut:
    appointment = AppointmentService(db).complete(ctx.tenant_id, appointment_id)
    db.commit()
    return AppointmentOut.model_validate(appointment)


@router.post("/{appointment_id}/no-show", response_model=AppointmentOut)
def mark_appointment_no_show(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("appointments.manage")),
) -> AppointmentOut:
    appointment = AppointmentService(db).mark_no_show(ctx.tenant_id, appointment_id)
    db.commit()
    return AppointmentOut.model_validate(appointment)
