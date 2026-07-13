"""Pure computation of open appointment slots: tenant business hours
(local time, per weekday) minus existing non-cancelled appointments for
the requested staff member. No slot rows are persisted - this is
recomputed on every request from the same data the double-booking guard
in AppointmentService checks against, so the two can never disagree."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.repositories.appointment import AppointmentRepository
from app.repositories.tenant import TenantRepository

WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

DEFAULT_BUSINESS_HOURS: dict[str, dict[str, str] | None] = {
    "sun": {"start": "09:00", "end": "18:00"},
    "mon": {"start": "09:00", "end": "18:00"},
    "tue": {"start": "09:00", "end": "18:00"},
    "wed": {"start": "09:00", "end": "18:00"},
    "thu": {"start": "09:00", "end": "18:00"},
    "fri": None,
    "sat": None,
}


@dataclass
class TimeSlot:
    starts_at: datetime
    ends_at: datetime


class AvailabilityService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.tenants = TenantRepository(db)
        self.appointments = AppointmentRepository(db)

    def get_business_hours(self, tenant_id: uuid.UUID) -> dict[str, dict[str, str] | None]:
        settings = self.tenants.get_settings(tenant_id)
        if settings is not None and settings.business_hours:
            return settings.business_hours
        return DEFAULT_BUSINESS_HOURS

    def _tenant_timezone(self, tenant_id: uuid.UUID) -> ZoneInfo:
        tenant = self.tenants.get_by_id(tenant_id)
        return ZoneInfo(tenant.timezone if tenant else "Asia/Dubai")

    def available_slots(
        self,
        tenant_id: uuid.UUID,
        *,
        assigned_membership_id: uuid.UUID | None,
        on_date: date_type,
        duration_minutes: int = 30,
    ) -> list[TimeSlot]:
        if duration_minutes <= 0:
            return []
        tz = self._tenant_timezone(tenant_id)
        hours = self.get_business_hours(tenant_id)
        window = hours.get(WEEKDAY_KEYS[on_date.weekday()])
        if not window:
            return []

        day_start = datetime.combine(on_date, time.fromisoformat(window["start"]), tzinfo=tz)
        day_end = datetime.combine(on_date, time.fromisoformat(window["end"]), tzinfo=tz)
        step = timedelta(minutes=duration_minutes)

        candidates: list[TimeSlot] = []
        cursor = day_start
        while cursor + step <= day_end:
            candidates.append(TimeSlot(starts_at=cursor, ends_at=cursor + step))
            cursor += step

        if assigned_membership_id is None:
            return candidates

        busy = self.appointments.list_overlapping(
            tenant_id,
            assigned_membership_id=assigned_membership_id,
            starts_at=day_start,
            ends_at=day_end,
        )
        return [
            slot
            for slot in candidates
            if not any(slot.starts_at < b.ends_at and slot.ends_at > b.starts_at for b in busy)
        ]
