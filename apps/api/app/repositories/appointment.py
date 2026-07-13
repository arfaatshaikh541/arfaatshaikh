import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment

_ACTIVE_STATUSES = ("scheduled", "confirmed")


@dataclass
class AppointmentFilters:
    lead_id: uuid.UUID | None = None
    assigned_membership_id: uuid.UUID | None = None
    status: str | None = None


@dataclass
class AppointmentPage:
    items: list[Appointment] = field(default_factory=list)
    total: int = 0


class AppointmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id_for_tenant(
        self, tenant_id: uuid.UUID, appointment_id: uuid.UUID
    ) -> Appointment | None:
        stmt = select(Appointment).where(
            Appointment.tenant_id == tenant_id, Appointment.id == appointment_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_tenant(
        self, tenant_id: uuid.UUID, *, filters: AppointmentFilters, page: int, page_size: int
    ) -> AppointmentPage:
        stmt = select(Appointment).where(Appointment.tenant_id == tenant_id)
        if filters.lead_id:
            stmt = stmt.where(Appointment.lead_id == filters.lead_id)
        if filters.assigned_membership_id:
            stmt = stmt.where(Appointment.assigned_membership_id == filters.assigned_membership_id)
        if filters.status:
            stmt = stmt.where(Appointment.status == filters.status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self.db.execute(count_stmt).scalar_one())

        stmt = stmt.order_by(Appointment.starts_at).offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return AppointmentPage(items=items, total=total)

    def list_overlapping(
        self,
        tenant_id: uuid.UUID,
        *,
        assigned_membership_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
        exclude_appointment_id: uuid.UUID | None = None,
    ) -> list[Appointment]:
        """Non-cancelled/non-no-show appointments for this staff member that
        overlap [starts_at, ends_at) - the source of truth for both
        availability display and the server-side double-booking guard."""
        stmt = select(Appointment).where(
            Appointment.tenant_id == tenant_id,
            Appointment.assigned_membership_id == assigned_membership_id,
            Appointment.status.in_(_ACTIVE_STATUSES),
            Appointment.starts_at < ends_at,
            Appointment.ends_at > starts_at,
        )
        if exclude_appointment_id is not None:
            stmt = stmt.where(Appointment.id != exclude_appointment_id)
        return list(self.db.execute(stmt).scalars().all())

    def create(
        self,
        *,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID,
        assigned_membership_id: uuid.UUID | None,
        branch_id: uuid.UUID | None,
        service_id: uuid.UUID | None,
        starts_at: datetime,
        ends_at: datetime,
        location_type: str,
        notes: str | None,
        created_by_user_id: uuid.UUID | None,
    ) -> Appointment:
        appointment = Appointment(
            tenant_id=tenant_id,
            lead_id=lead_id,
            assigned_membership_id=assigned_membership_id,
            branch_id=branch_id,
            service_id=service_id,
            starts_at=starts_at,
            ends_at=ends_at,
            location_type=location_type,
            notes=notes,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(appointment)
        self.db.flush()
        return appointment

    def update(self, appointment: Appointment, **fields: object) -> Appointment:
        for key, value in fields.items():
            if value is not None:
                setattr(appointment, key, value)
        self.db.flush()
        return appointment
