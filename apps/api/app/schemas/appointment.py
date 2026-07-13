import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AppointmentOut(ORMModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    assigned_membership_id: uuid.UUID | None
    branch_id: uuid.UUID | None
    service_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime
    status: str
    location_type: str
    notes: str | None
    cancellation_reason: str | None
    created_by_user_id: uuid.UUID | None
    created_at: datetime


class AppointmentListOut(ORMModel):
    items: list[AppointmentOut]
    total: int
    page: int
    page_size: int


class AppointmentCreate(BaseModel):
    lead_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    assigned_membership_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    location_type: str = "in_person"
    notes: str | None = None


class AppointmentRescheduleRequest(BaseModel):
    starts_at: datetime
    ends_at: datetime


class AppointmentCancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class TimeSlotOut(BaseModel):
    starts_at: datetime
    ends_at: datetime


class AvailableSlotsQuery(BaseModel):
    assigned_membership_id: uuid.UUID | None = None
    on_date: date
    duration_minutes: int = 30
