import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field


class CreateAppointmentTypeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = ""
    duration_minutes: int = Field(default=30, gt=0, le=480)


class AvailabilityWindow(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time


class SetWeeklyAvailabilityRequest(BaseModel):
    windows: list[AvailabilityWindow]


class AddAvailabilityExceptionRequest(BaseModel):
    date: date
    reason: str = ""


class CreateAppointmentRequest(BaseModel):
    staff_user_id: uuid.UUID
    starts_at: datetime
    appointment_type_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    title: str | None = None
    location: str = ""
    notes: str = ""


class CancelAppointmentRequest(BaseModel):
    reason: str | None = None


class PublicBookingRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    staff_user_id: uuid.UUID
    appointment_type_id: uuid.UUID | None = None
    starts_at: datetime
    notes: str = ""
    # Honeypot — same convention as public lead capture.
    website: str = Field(default="", max_length=200)
