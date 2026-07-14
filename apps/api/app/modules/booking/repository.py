import uuid
from datetime import date as date_
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.booking.models import (
    Appointment,
    AppointmentStatus,
    AppointmentType,
    AvailabilityException,
    StaffAvailability,
)


class AppointmentTypeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, type_id: uuid.UUID) -> AppointmentType | None:
        return self.db.execute(
            select(AppointmentType).where(AppointmentType.tenant_id == tenant_id, AppointmentType.id == type_id)
        ).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID, *, active_only: bool = False) -> list[AppointmentType]:
        stmt = select(AppointmentType).where(AppointmentType.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(AppointmentType.is_active.is_(True))
        return list(self.db.execute(stmt.order_by(AppointmentType.sort_order)).scalars().all())

    def create(
        self, *, tenant_id: uuid.UUID, name: str, description: str = "", duration_minutes: int = 30, sort_order: int = 0
    ) -> AppointmentType:
        appointment_type = AppointmentType(
            tenant_id=tenant_id, name=name, description=description, duration_minutes=duration_minutes, sort_order=sort_order
        )
        self.db.add(appointment_type)
        self.db.flush()
        return appointment_type


class StaffAvailabilityRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_distinct_user_ids(self, tenant_id: uuid.UUID) -> list[uuid.UUID]:
        rows = self.db.execute(
            select(StaffAvailability.user_id).where(StaffAvailability.tenant_id == tenant_id, StaffAvailability.is_active.is_(True)).distinct()
        ).scalars().all()
        return list(rows)

    def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[StaffAvailability]:
        return list(
            self.db.execute(
                select(StaffAvailability)
                .where(StaffAvailability.tenant_id == tenant_id, StaffAvailability.user_id == user_id, StaffAvailability.is_active.is_(True))
                .order_by(StaffAvailability.day_of_week, StaffAvailability.start_time)
            )
            .scalars()
            .all()
        )

    def replace_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID, windows: list[dict]) -> list[StaffAvailability]:
        """Replaces this user's entire weekly availability with the given
        windows — simpler and less error-prone than a diff/merge for a
        small per-user table, and matches how the frontend always submits
        the full week at once."""
        existing = self.db.execute(
            select(StaffAvailability).where(StaffAvailability.tenant_id == tenant_id, StaffAvailability.user_id == user_id)
        ).scalars().all()
        for row in existing:
            self.db.delete(row)
        self.db.flush()

        created = []
        for window in windows:
            row = StaffAvailability(
                tenant_id=tenant_id, user_id=user_id, day_of_week=window["day_of_week"],
                start_time=window["start_time"], end_time=window["end_time"],
            )
            self.db.add(row)
            created.append(row)
        self.db.flush()
        return created


class AvailabilityExceptionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID, *, date_from: date_, date_to: date_) -> list[AvailabilityException]:
        return list(
            self.db.execute(
                select(AvailabilityException).where(
                    AvailabilityException.tenant_id == tenant_id, AvailabilityException.user_id == user_id,
                    AvailabilityException.date >= date_from, AvailabilityException.date <= date_to,
                )
            )
            .scalars()
            .all()
        )

    def create(self, *, tenant_id: uuid.UUID, user_id: uuid.UUID, date: date_, reason: str = "") -> AvailabilityException:
        exception = AvailabilityException(tenant_id=tenant_id, user_id=user_id, date=date, reason=reason)
        self.db.add(exception)
        self.db.flush()
        return exception

    def delete(self, tenant_id: uuid.UUID, exception_id: uuid.UUID) -> None:
        exception = self.db.execute(
            select(AvailabilityException).where(AvailabilityException.tenant_id == tenant_id, AvailabilityException.id == exception_id)
        ).scalar_one_or_none()
        if exception is not None:
            self.db.delete(exception)
            self.db.flush()


class AppointmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, appointment_id: uuid.UUID) -> Appointment | None:
        return self.db.execute(
            select(Appointment).where(Appointment.tenant_id == tenant_id, Appointment.id == appointment_id)
        ).scalar_one_or_none()

    def find_overlapping(
        self, tenant_id: uuid.UUID, staff_user_id: uuid.UUID, *, starts_at: datetime, ends_at: datetime, exclude_id: uuid.UUID | None = None
    ) -> Appointment | None:
        stmt = select(Appointment).where(
            Appointment.tenant_id == tenant_id, Appointment.staff_user_id == staff_user_id,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.starts_at < ends_at, Appointment.ends_at > starts_at,
        ).with_for_update()
        if exclude_id is not None:
            stmt = stmt.where(Appointment.id != exclude_id)
        return self.db.execute(stmt).scalars().first()

    def list_for_staff_in_range(self, tenant_id: uuid.UUID, staff_user_id: uuid.UUID, *, starts_at: datetime, ends_at: datetime) -> list[Appointment]:
        return list(
            self.db.execute(
                select(Appointment).where(
                    Appointment.tenant_id == tenant_id, Appointment.staff_user_id == staff_user_id,
                    Appointment.status == AppointmentStatus.SCHEDULED,
                    Appointment.starts_at < ends_at, Appointment.ends_at > starts_at,
                )
            )
            .scalars()
            .all()
        )

    def list_for_tenant(
        self, tenant_id: uuid.UUID, *, staff_user_id: uuid.UUID | None = None, lead_id: uuid.UUID | None = None,
        date_from: datetime | None = None, date_to: datetime | None = None, status: AppointmentStatus | None = None,
    ) -> list[Appointment]:
        stmt = select(Appointment).where(Appointment.tenant_id == tenant_id)
        if staff_user_id:
            stmt = stmt.where(Appointment.staff_user_id == staff_user_id)
        if lead_id:
            stmt = stmt.where(Appointment.lead_id == lead_id)
        if date_from:
            stmt = stmt.where(Appointment.ends_at >= date_from)
        if date_to:
            stmt = stmt.where(Appointment.starts_at <= date_to)
        if status:
            stmt = stmt.where(Appointment.status == status)
        return list(self.db.execute(stmt.order_by(Appointment.starts_at)).scalars().all())

    def list_due_for_reminder(self, *, before: datetime, tenant_id: uuid.UUID | None = None) -> list[Appointment]:
        stmt = select(Appointment).where(
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.starts_at <= before,
            Appointment.starts_at >= datetime.now(before.tzinfo),
            Appointment.reminder_sent_at.is_(None),
        )
        if tenant_id is not None:
            stmt = stmt.where(Appointment.tenant_id == tenant_id)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, **fields) -> Appointment:
        appointment = Appointment(**fields)
        self.db.add(appointment)
        self.db.flush()
        return appointment
