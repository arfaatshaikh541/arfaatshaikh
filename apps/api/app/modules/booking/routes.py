import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.core.errors import NotFoundError
from app.dependencies.entitlements import require_module
from app.dependencies.permissions import require_permission
from app.dependencies.tenant import get_tenant_context
from app.modules.booking import service as booking_service
from app.modules.booking.models import AppointmentStatus
from app.modules.booking.schemas import (
    AddAvailabilityExceptionRequest,
    CancelAppointmentRequest,
    CreateAppointmentRequest,
    CreateAppointmentTypeRequest,
    PublicBookingRequest,
    SetWeeklyAvailabilityRequest,
)
from app.modules.tenancy import service as tenancy_service

public_router = APIRouter(prefix="/public/booking", tags=["public-booking"])
router = APIRouter(prefix="/tenant/appointments", tags=["appointments"])
appointment_types_router = APIRouter(prefix="/tenant/appointment-types", tags=["appointment-types"])
availability_router = APIRouter(prefix="/tenant/availability", tags=["availability"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _appointment_to_dict(appointment) -> dict:
    return {
        "id": str(appointment.id), "lead_id": str(appointment.lead_id) if appointment.lead_id else None,
        "staff_user_id": str(appointment.staff_user_id),
        "appointment_type_id": str(appointment.appointment_type_id) if appointment.appointment_type_id else None,
        "title": appointment.title, "starts_at": appointment.starts_at.isoformat(), "ends_at": appointment.ends_at.isoformat(),
        "status": appointment.status.value, "location": appointment.location, "notes": appointment.notes,
        "cancelled_reason": appointment.cancelled_reason,
        "created_by": str(appointment.created_by) if appointment.created_by else None,
    }


# --- Public booking ---------------------------------------------------

@public_router.get("/{token}/appointment-types")
def public_appointment_types(token: str, db: Session = Depends(get_db)) -> dict:
    tenant = tenancy_service.resolve_tenant_by_capture_token(db, token)
    if tenant is None:
        raise NotFoundError("Not found.")
    types = booking_service.list_appointment_types(db, tenant.id, active_only=True)
    return {
        "tenant_name": tenant.name,
        "appointment_types": [{"id": str(t.id), "name": t.name, "description": t.description, "duration_minutes": t.duration_minutes} for t in types],
    }


@public_router.get("/{token}/staff")
def public_bookable_staff(token: str, db: Session = Depends(get_db)) -> list[dict]:
    tenant = tenancy_service.resolve_tenant_by_capture_token(db, token)
    if tenant is None:
        raise NotFoundError("Not found.")
    staff = booking_service.list_bookable_staff(db, tenant.id)
    return [{"id": str(u.id), "first_name": u.first_name, "last_name": u.last_name} for u in staff]


@public_router.get("/{token}/slots")
def public_available_slots(
    token: str, staff_user_id: uuid.UUID, date_from: date, date_to: date, appointment_type_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    tenant = tenancy_service.resolve_tenant_by_capture_token(db, token)
    if tenant is None:
        raise NotFoundError("Not found.")
    from app.core.db import set_rls_context

    set_rls_context(db, tenant_id=tenant.id, is_platform_admin=False)
    slots = booking_service.compute_available_slots(
        db, tenant_id=tenant.id, staff_user_id=staff_user_id, appointment_type_id=appointment_type_id,
        date_from=date_from, date_to=date_to,
    )
    return [{"start": s["start"].isoformat(), "end": s["end"].isoformat()} for s in slots]


@public_router.post("/{token}/book", status_code=201)
def public_book_appointment(token: str, payload: PublicBookingRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    appointment = booking_service.book_public_appointment(db, token=token, ip_address=_client_ip(request), payload=payload)
    if appointment is None:
        return {"status": "received"}
    return {"status": "received", "appointment_id": str(appointment.id), "starts_at": appointment.starts_at.isoformat()}


# --- Tenant appointment types --------------------------------------------

@appointment_types_router.get("")
def list_appointment_types(
    ctx: TenantContext = Depends(get_tenant_context), _mod: TenantContext = Depends(require_module("booking")), db: Session = Depends(get_db)
) -> list[dict]:
    return [
        {"id": str(t.id), "name": t.name, "description": t.description, "duration_minutes": t.duration_minutes, "is_active": t.is_active}
        for t in booking_service.list_appointment_types(db, ctx.tenant_id)
    ]


@appointment_types_router.post("", status_code=201)
def create_appointment_type(
    payload: CreateAppointmentTypeRequest, ctx: TenantContext = Depends(require_permission("availability.manage")),
    _mod: TenantContext = Depends(require_module("booking")), db: Session = Depends(get_db),
) -> dict:
    appointment_type = booking_service.create_appointment_type(
        db, tenant_id=ctx.tenant_id, name=payload.name, description=payload.description, duration_minutes=payload.duration_minutes
    )
    return {"id": str(appointment_type.id), "name": appointment_type.name}


# --- Tenant availability --------------------------------------------------

@availability_router.get("/{user_id}")
def get_availability(
    user_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("appointments.view")),
    _mod: TenantContext = Depends(require_module("booking")), db: Session = Depends(get_db),
) -> list[dict]:
    windows = booking_service.get_weekly_availability(db, ctx.tenant_id, user_id)
    return [{"id": str(w.id), "day_of_week": w.day_of_week, "start_time": w.start_time.isoformat(), "end_time": w.end_time.isoformat()} for w in windows]


@availability_router.put("/{user_id}")
def set_availability(
    user_id: uuid.UUID, payload: SetWeeklyAvailabilityRequest,
    ctx: TenantContext = Depends(require_permission("appointments.manage")),
    _mod: TenantContext = Depends(require_module("booking")), db: Session = Depends(get_db),
) -> dict:
    booking_service.assert_can_manage_availability(
        actor_id=ctx.user_id, actor_can_manage_others=ctx.has_permission("users.manage"), target_user_id=user_id
    )
    booking_service.set_weekly_availability(
        db, ctx.tenant_id, user_id, windows=[w.model_dump() for w in payload.windows]
    )
    return {"status": "ok"}


@availability_router.get("/{user_id}/exceptions")
def list_exceptions(
    user_id: uuid.UUID, date_from: date, date_to: date, ctx: TenantContext = Depends(require_permission("appointments.view")),
    _mod: TenantContext = Depends(require_module("booking")), db: Session = Depends(get_db),
) -> list[dict]:
    exceptions = booking_service.list_availability_exceptions(db, ctx.tenant_id, user_id, date_from=date_from, date_to=date_to)
    return [{"id": str(e.id), "date": e.date.isoformat(), "reason": e.reason} for e in exceptions]


@availability_router.post("/{user_id}/exceptions", status_code=201)
def add_exception(
    user_id: uuid.UUID, payload: AddAvailabilityExceptionRequest,
    ctx: TenantContext = Depends(require_permission("appointments.manage")),
    _mod: TenantContext = Depends(require_module("booking")), db: Session = Depends(get_db),
) -> dict:
    booking_service.assert_can_manage_availability(
        actor_id=ctx.user_id, actor_can_manage_others=ctx.has_permission("users.manage"), target_user_id=user_id
    )
    exception = booking_service.add_availability_exception(db, ctx.tenant_id, user_id, date=payload.date, reason=payload.reason)
    return {"id": str(exception.id)}


@availability_router.delete("/exceptions/{exception_id}", status_code=204)
def remove_exception(
    exception_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("appointments.manage")),
    _mod: TenantContext = Depends(require_module("booking")), db: Session = Depends(get_db),
) -> None:
    booking_service.remove_availability_exception(db, ctx.tenant_id, exception_id)


# --- Tenant appointments --------------------------------------------------

@router.get("")
def list_appointments(
    staff_user_id: uuid.UUID | None = None, lead_id: uuid.UUID | None = None,
    date_from: datetime | None = None, date_to: datetime | None = None, status: AppointmentStatus | None = None,
    ctx: TenantContext = Depends(require_permission("appointments.view")),
    _mod: TenantContext = Depends(require_module("booking")), db: Session = Depends(get_db),
) -> list[dict]:
    appointments = booking_service.list_appointments(
        db, ctx.tenant_id, staff_user_id=staff_user_id, lead_id=lead_id, date_from=date_from, date_to=date_to, status=status
    )
    return [_appointment_to_dict(a) for a in appointments]


@router.post("", status_code=201)
def create_appointment(
    payload: CreateAppointmentRequest, ctx: TenantContext = Depends(require_permission("appointments.manage")),
    _mod: TenantContext = Depends(require_module("booking")), db: Session = Depends(get_db),
) -> dict:
    appointment = booking_service.create_appointment(
        db, tenant_id=ctx.tenant_id, staff_user_id=payload.staff_user_id, starts_at=payload.starts_at,
        appointment_type_id=payload.appointment_type_id, lead_id=payload.lead_id, title=payload.title,
        location=payload.location, notes=payload.notes, created_by=ctx.user_id,
    )
    return _appointment_to_dict(appointment)


@router.get("/slots")
def available_slots(
    staff_user_id: uuid.UUID, date_from: date, date_to: date, appointment_type_id: uuid.UUID | None = None,
    ctx: TenantContext = Depends(require_permission("appointments.view")),
    _mod: TenantContext = Depends(require_module("booking")), db: Session = Depends(get_db),
) -> list[dict]:
    slots = booking_service.compute_available_slots(
        db, tenant_id=ctx.tenant_id, staff_user_id=staff_user_id, appointment_type_id=appointment_type_id,
        date_from=date_from, date_to=date_to,
    )
    return [{"start": s["start"].isoformat(), "end": s["end"].isoformat()} for s in slots]


@router.post("/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: uuid.UUID, payload: CancelAppointmentRequest, ctx: TenantContext = Depends(require_permission("appointments.manage")),
    _mod: TenantContext = Depends(require_module("booking")), db: Session = Depends(get_db),
) -> dict:
    appointment = booking_service.get_appointment_or_404(db, ctx.tenant_id, appointment_id)
    booking_service.cancel_appointment(db, tenant_id=ctx.tenant_id, appointment=appointment, reason=payload.reason, actor_id=ctx.user_id)
    return {"status": "ok"}


@router.post("/{appointment_id}/complete")
def complete_appointment(
    appointment_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("appointments.manage")),
    _mod: TenantContext = Depends(require_module("booking")), db: Session = Depends(get_db),
) -> dict:
    appointment = booking_service.get_appointment_or_404(db, ctx.tenant_id, appointment_id)
    booking_service.complete_appointment(db, tenant_id=ctx.tenant_id, appointment=appointment, actor_id=ctx.user_id)
    return {"status": "ok"}


@router.post("/{appointment_id}/no-show")
def mark_no_show(
    appointment_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("appointments.manage")),
    _mod: TenantContext = Depends(require_module("booking")), db: Session = Depends(get_db),
) -> dict:
    appointment = booking_service.get_appointment_or_404(db, ctx.tenant_id, appointment_id)
    booking_service.mark_no_show(db, tenant_id=ctx.tenant_id, appointment=appointment, actor_id=ctx.user_id)
    return {"status": "ok"}
