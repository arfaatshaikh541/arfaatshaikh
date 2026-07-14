import uuid
from datetime import UTC, datetime, timedelta
from datetime import date as date_
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, RateLimitedError, ValidationFailedError
from app.modules.booking.models import Appointment, AppointmentStatus, AppointmentType
from app.modules.booking.repository import (
    AppointmentRepository,
    AppointmentTypeRepository,
    AvailabilityExceptionRepository,
    StaffAvailabilityRepository,
)
from app.modules.identity.models import MembershipStatus
from app.modules.identity.repository import MembershipRepository

MAX_SLOT_LOOKUP_DAYS = 31
DEFAULT_DURATION_MINUTES = 30


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _tenant_timezone(db: Session, tenant_id: uuid.UUID) -> ZoneInfo:
    from app.modules.tenancy import service as tenancy_service

    settings = tenancy_service.get_tenant_settings(db, tenant_id)
    tz_name = settings.timezone if settings else "Asia/Dubai"
    try:
        return ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001 — an invalid stored timezone must never crash slot computation
        return ZoneInfo("UTC")


# --- Appointment types -------------------------------------------------

def list_appointment_types(db: Session, tenant_id: uuid.UUID, *, active_only: bool = False) -> list[AppointmentType]:
    return AppointmentTypeRepository(db).list_for_tenant(tenant_id, active_only=active_only)


def create_appointment_type(
    db: Session, *, tenant_id: uuid.UUID, name: str, description: str = "", duration_minutes: int = DEFAULT_DURATION_MINUTES
) -> AppointmentType:
    existing = AppointmentTypeRepository(db).list_for_tenant(tenant_id)
    return AppointmentTypeRepository(db).create(
        tenant_id=tenant_id, name=name, description=description, duration_minutes=duration_minutes, sort_order=len(existing)
    )


# --- Availability --------------------------------------------------------

def assert_can_manage_availability(*, actor_id: uuid.UUID, actor_can_manage_others: bool, target_user_id: uuid.UUID) -> None:
    """A user may always manage their own availability; managing someone
    else's requires the `users.manage` permission (checked by the route,
    passed in as `actor_can_manage_others` — this function only enforces
    the resulting business rule, keeping permission-code knowledge in the
    route layer where every other module puts it)."""
    if actor_id == target_user_id or actor_can_manage_others:
        return
    raise ValidationFailedError("You may only manage your own availability.", code="cannot_manage_others_availability")


def get_weekly_availability(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list:
    return StaffAvailabilityRepository(db).list_for_user(tenant_id, user_id)


def set_weekly_availability(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, *, windows: list[dict]) -> list:
    for window in windows:
        if not (0 <= window["day_of_week"] <= 6):
            raise ValidationFailedError("day_of_week must be between 0 (Monday) and 6 (Sunday).", code="invalid_day_of_week")
        if window["start_time"] >= window["end_time"]:
            raise ValidationFailedError("start_time must be before end_time.", code="invalid_availability_window")
    return StaffAvailabilityRepository(db).replace_for_user(tenant_id, user_id, windows)


def add_availability_exception(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, *, date: date_, reason: str = ""):
    return AvailabilityExceptionRepository(db).create(tenant_id=tenant_id, user_id=user_id, date=date, reason=reason)


def list_availability_exceptions(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, *, date_from: date_, date_to: date_):
    return AvailabilityExceptionRepository(db).list_for_user(tenant_id, user_id, date_from=date_from, date_to=date_to)


def remove_availability_exception(db: Session, tenant_id: uuid.UUID, exception_id: uuid.UUID) -> None:
    AvailabilityExceptionRepository(db).delete(tenant_id, exception_id)


def list_bookable_staff(db: Session, tenant_id: uuid.UUID) -> list:
    """Staff members with at least one active weekly availability window —
    the public booking page's "who can I book with" list. Only id/name
    are ever exposed publicly (see the route), never email or other
    account details."""
    from app.modules.identity.repository import UserRepository

    user_repo = UserRepository(db)
    user_ids = StaffAvailabilityRepository(db).list_distinct_user_ids(tenant_id)
    users = [user_repo.get_by_id(uid) for uid in user_ids]
    return [u for u in users if u is not None]


# --- Slot computation ------------------------------------------------------

def compute_available_slots(
    db: Session, *, tenant_id: uuid.UUID, staff_user_id: uuid.UUID, appointment_type_id: uuid.UUID | None,
    date_from: date_, date_to: date_,
) -> list[dict]:
    """Deterministic: weekly availability windows, minus whole-day
    exceptions, minus existing scheduled appointments, sliced into
    appointment-duration increments, with anything already in the past
    excluded. Availability windows are naive clock times interpreted in
    the tenant's configured timezone and converted to UTC only for the
    final comparison/output — this keeps daylight-saving transitions
    correct without ever storing a timezone-ambiguous instant."""
    if (date_to - date_from).days > MAX_SLOT_LOOKUP_DAYS:
        raise ValidationFailedError(f"Date range cannot exceed {MAX_SLOT_LOOKUP_DAYS} days.", code="date_range_too_large")

    duration_minutes = DEFAULT_DURATION_MINUTES
    if appointment_type_id is not None:
        appointment_type = AppointmentTypeRepository(db).get(tenant_id, appointment_type_id)
        if appointment_type is not None:
            duration_minutes = appointment_type.duration_minutes
    duration = timedelta(minutes=duration_minutes)

    tz = _tenant_timezone(db, tenant_id)
    weekly = StaffAvailabilityRepository(db).list_for_user(tenant_id, staff_user_id)
    windows_by_day: dict[int, list] = {}
    for window in weekly:
        windows_by_day.setdefault(window.day_of_week, []).append(window)

    blocked_dates = {
        exc.date for exc in AvailabilityExceptionRepository(db).list_for_user(tenant_id, staff_user_id, date_from=date_from, date_to=date_to)
    }

    range_start_utc = datetime.combine(date_from, datetime.min.time(), tzinfo=tz).astimezone(UTC)
    range_end_utc = datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=tz).astimezone(UTC)
    existing = AppointmentRepository(db).list_for_staff_in_range(tenant_id, staff_user_id, starts_at=range_start_utc, ends_at=range_end_utc)

    now = _utcnow()
    slots: list[dict] = []
    current_date = date_from
    while current_date <= date_to:
        if current_date not in blocked_dates:
            for window in windows_by_day.get(current_date.weekday(), []):
                window_start = datetime.combine(current_date, window.start_time, tzinfo=tz).astimezone(UTC)
                window_end = datetime.combine(current_date, window.end_time, tzinfo=tz).astimezone(UTC)
                slot_start = window_start
                while slot_start + duration <= window_end:
                    slot_end = slot_start + duration
                    if slot_start > now and not any(slot_start < a.ends_at and slot_end > a.starts_at for a in existing):
                        slots.append({"start": slot_start, "end": slot_end})
                    slot_start = slot_end
        current_date += timedelta(days=1)

    return slots


# --- Appointments ------------------------------------------------------

def _default_context(lead, tenant, staff_user, appointment_type, appointment: Appointment) -> dict:
    # Rendered in UTC, not the tenant's local timezone — same convention
    # already used for Milestone 3's task-reminder merge fields.
    starts_at = appointment.starts_at
    return {
        "first_name": lead.first_name if lead else "",
        "last_name": lead.last_name if lead else "",
        "reference_number": lead.reference_number if lead else "",
        "tenant_name": tenant.name,
        "staff_name": f"{staff_user.first_name} {staff_user.last_name}" if staff_user else "",
        "appointment_type_name": appointment_type.name if appointment_type else "",
        "appointment_date": starts_at.date().isoformat(),
        "appointment_time": starts_at.strftime("%H:%M UTC"),
        "location": appointment.location,
    }


def create_appointment(
    db: Session, *, tenant_id: uuid.UUID, staff_user_id: uuid.UUID, starts_at: datetime, appointment_type_id: uuid.UUID | None = None,
    lead_id: uuid.UUID | None = None, title: str | None = None, location: str = "", notes: str = "",
    created_by: uuid.UUID | None = None,
) -> Appointment:
    _validate_membership(db, tenant_id, staff_user_id)

    duration_minutes = DEFAULT_DURATION_MINUTES
    appointment_type = None
    if appointment_type_id is not None:
        appointment_type = AppointmentTypeRepository(db).get(tenant_id, appointment_type_id)
        if appointment_type is not None:
            duration_minutes = appointment_type.duration_minutes
    ends_at = starts_at + timedelta(minutes=duration_minutes)

    if starts_at <= _utcnow():
        raise ValidationFailedError("Cannot book an appointment in the past.", code="appointment_in_the_past")

    conflict = AppointmentRepository(db).find_overlapping(tenant_id, staff_user_id, starts_at=starts_at, ends_at=ends_at)
    if conflict is not None:
        raise ConflictError("This time slot is no longer available.", code="slot_unavailable")

    appointment = AppointmentRepository(db).create(
        tenant_id=tenant_id, lead_id=lead_id, staff_user_id=staff_user_id, appointment_type_id=appointment_type_id,
        title=title or (appointment_type.name if appointment_type else "Appointment"), starts_at=starts_at, ends_at=ends_at,
        location=location, notes=notes, created_by=created_by,
    )

    from app.modules.audit.service import log_event
    from app.modules.identity.repository import UserRepository
    from app.modules.leads.repository import LeadRepository
    from app.modules.tenancy import service as tenancy_service

    log_event(db, tenant_id=tenant_id, actor_user_id=created_by, action="appointment.booked", entity_type="appointment", entity_id=appointment.id)

    lead = LeadRepository(db).get(tenant_id, lead_id) if lead_id else None
    if lead is not None:
        from app.modules.crm.service import record_activity

        record_activity(
            db, tenant_id=tenant_id, lead_id=lead_id, actor_id=created_by, activity_type="appointment.booked",
            summary=f"Appointment booked for {starts_at.strftime('%Y-%m-%d %H:%M UTC')}",
        )

    recipient = lead.email if lead and lead.email else None
    if recipient:
        staff_user = UserRepository(db).get_by_id(staff_user_id)
        tenant = tenancy_service.get_tenant_or_404(db, tenant_id)
        from app.modules.communications.models import EmailTriggerEvent
        from app.modules.communications.service import send_templated_email

        send_templated_email(
            db, tenant_id=tenant_id, trigger_event=EmailTriggerEvent.APPOINTMENT_BOOKED, recipient=recipient,
            lead_id=lead_id, context=_default_context(lead, tenant, staff_user, appointment_type, appointment),
        )
    return appointment


def get_appointment_or_404(db: Session, tenant_id: uuid.UUID, appointment_id: uuid.UUID) -> Appointment:
    appointment = AppointmentRepository(db).get(tenant_id, appointment_id)
    if appointment is None:
        raise NotFoundError("Appointment not found.")
    return appointment


def cancel_appointment(db: Session, *, tenant_id: uuid.UUID, appointment: Appointment, reason: str | None, actor_id: uuid.UUID | None) -> Appointment:
    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancelled_reason = reason
    db.add(appointment)
    db.flush()

    from app.modules.audit.service import log_event

    log_event(db, tenant_id=tenant_id, actor_user_id=actor_id, action="appointment.cancelled", entity_type="appointment", entity_id=appointment.id)

    if appointment.lead_id:
        from app.modules.crm.service import record_activity

        record_activity(
            db, tenant_id=tenant_id, lead_id=appointment.lead_id, actor_id=actor_id,
            activity_type="appointment.cancelled", summary="Appointment cancelled",
        )

    _notify_cancellation(db, tenant_id=tenant_id, appointment=appointment)
    return appointment


def _notify_cancellation(db: Session, *, tenant_id: uuid.UUID, appointment: Appointment) -> None:
    from app.modules.identity.repository import UserRepository
    from app.modules.leads.repository import LeadRepository
    from app.modules.tenancy import service as tenancy_service

    lead = LeadRepository(db).get(tenant_id, appointment.lead_id) if appointment.lead_id else None
    if lead is None or not lead.email:
        return
    staff_user = UserRepository(db).get_by_id(appointment.staff_user_id)
    tenant = tenancy_service.get_tenant_or_404(db, tenant_id)
    appointment_type = AppointmentTypeRepository(db).get(tenant_id, appointment.appointment_type_id) if appointment.appointment_type_id else None
    from app.modules.communications.models import EmailTriggerEvent
    from app.modules.communications.service import send_templated_email

    send_templated_email(
        db, tenant_id=tenant_id, trigger_event=EmailTriggerEvent.APPOINTMENT_CANCELLED, recipient=lead.email,
        lead_id=appointment.lead_id, context=_default_context(lead, tenant, staff_user, appointment_type, appointment),
    )


PUBLIC_BOOKING_THROTTLE_MAX_ATTEMPTS = 10
PUBLIC_BOOKING_THROTTLE_WINDOW_SECONDS = 10 * 60
BOOKING_SOURCE_CODE = "booking"


def book_public_appointment(db: Session, *, token: str, ip_address: str, payload) -> Appointment | None:
    """Public, unauthenticated: resolves the tenant from its capture
    token (same mechanism as public lead capture), finds or creates a
    lead from the submitted contact details, then books the appointment.
    Returns None only when the honeypot field was filled in — the caller
    must respond with the same generic success body either way."""
    from app.core.db import set_rls_context
    from app.core.rate_limit import is_rate_limited
    from app.modules.entitlements import service as entitlements_service
    from app.modules.leads.repository import LeadRepository, LeadSourceRepository
    from app.modules.leads.service import DUPLICATE_WINDOW, generate_reference_number
    from app.modules.tenancy import service as tenancy_service

    tenant = tenancy_service.resolve_tenant_by_capture_token(db, token)
    if tenant is None:
        raise NotFoundError("Not found.")

    throttle_key = f"throttle:booking:{tenant.id}:{ip_address}"
    limited, retry_after = is_rate_limited(
        throttle_key, max_attempts=PUBLIC_BOOKING_THROTTLE_MAX_ATTEMPTS, window_seconds=PUBLIC_BOOKING_THROTTLE_WINDOW_SECONDS
    )
    if limited:
        raise RateLimitedError(f"Too many requests. Try again in {retry_after} seconds.", code="booking_rate_limited")

    if payload.website:
        return None

    set_rls_context(db, tenant_id=tenant.id, is_platform_admin=False)
    entitlements_service.assert_module_enabled(db, tenant.id, "booking")

    lead_repo = LeadRepository(db)
    lead = lead_repo.find_possible_duplicate(tenant.id, email=payload.email, phone=payload.phone, within=DUPLICATE_WINDOW)
    if lead is None:
        from app.modules.crm.service import ensure_default_pipeline

        source_repo = LeadSourceRepository(db)
        source = source_repo.get_by_code(tenant.id, BOOKING_SOURCE_CODE)
        if source is None:
            source = source_repo.create(tenant_id=tenant.id, code=BOOKING_SOURCE_CODE, name="Booking")
        pipeline, first_stage = ensure_default_pipeline(db, tenant.id)
        lead = lead_repo.create(
            tenant_id=tenant.id, reference_number=generate_reference_number(tenant.slug), first_name=payload.first_name,
            last_name=payload.last_name, email=payload.email, phone=payload.phone, source_id=source.id,
            pipeline_id=pipeline.id if pipeline else None, stage_id=first_stage.id if first_stage else None,
        )
        from app.modules.crm.service import record_activity

        record_activity(db, tenant_id=tenant.id, lead_id=lead.id, actor_id=None, activity_type="lead.created", summary="Lead created from public booking")

    return create_appointment(
        db, tenant_id=tenant.id, staff_user_id=payload.staff_user_id, starts_at=payload.starts_at,
        appointment_type_id=payload.appointment_type_id, lead_id=lead.id, notes=payload.notes, created_by=None,
    )


def complete_appointment(db: Session, *, tenant_id: uuid.UUID, appointment: Appointment, actor_id: uuid.UUID | None) -> Appointment:
    appointment.status = AppointmentStatus.COMPLETED
    db.add(appointment)
    db.flush()
    if appointment.lead_id:
        from app.modules.crm.service import record_activity

        record_activity(
            db, tenant_id=tenant_id, lead_id=appointment.lead_id, actor_id=actor_id,
            activity_type="appointment.completed", summary="Appointment completed",
        )
    return appointment


def mark_no_show(db: Session, *, tenant_id: uuid.UUID, appointment: Appointment, actor_id: uuid.UUID | None) -> Appointment:
    appointment.status = AppointmentStatus.NO_SHOW
    db.add(appointment)
    db.flush()
    if appointment.lead_id:
        from app.modules.crm.service import record_activity

        record_activity(db, tenant_id=tenant_id, lead_id=appointment.lead_id, actor_id=actor_id, activity_type="appointment.no_show", summary="Marked as no-show")
    return appointment


def list_appointments(db: Session, tenant_id: uuid.UUID, **filters) -> list[Appointment]:
    return AppointmentRepository(db).list_for_tenant(tenant_id, **filters)


def send_appointment_reminders_for_tenant(db: Session, *, tenant_id: uuid.UUID, before: datetime) -> int:
    from app.modules.identity.repository import UserRepository
    from app.modules.leads.repository import LeadRepository
    from app.modules.tenancy.repository import TenantRepository

    tenant = TenantRepository(db).get(tenant_id)
    if tenant is None:
        return 0

    lead_repo = LeadRepository(db)
    user_repo = UserRepository(db)
    reminded = 0
    for appointment in AppointmentRepository(db).list_due_for_reminder(before=before, tenant_id=tenant_id):
        lead = lead_repo.get(tenant_id, appointment.lead_id) if appointment.lead_id else None
        if lead is not None and lead.email:
            staff_user = user_repo.get_by_id(appointment.staff_user_id)
            appointment_type = AppointmentTypeRepository(db).get(tenant_id, appointment.appointment_type_id) if appointment.appointment_type_id else None
            from app.modules.communications.models import EmailTriggerEvent
            from app.modules.communications.service import send_templated_email

            sent = send_templated_email(
                db, tenant_id=tenant_id, trigger_event=EmailTriggerEvent.APPOINTMENT_REMINDER, recipient=lead.email,
                lead_id=appointment.lead_id, context=_default_context(lead, tenant, staff_user, appointment_type, appointment),
            )
            if sent is not None:
                reminded += 1
        appointment.reminder_sent_at = _utcnow()
        db.add(appointment)
    return reminded


def _validate_membership(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    membership = MembershipRepository(db).get(tenant_id, user_id)
    if membership is None or membership.status != MembershipStatus.ACTIVE:
        raise ValidationFailedError("Selected staff member is not an active member of this tenant.", code="invalid_staff_member")
