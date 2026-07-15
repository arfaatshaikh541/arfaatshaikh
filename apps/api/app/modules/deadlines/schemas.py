import uuid
from datetime import date

from pydantic import BaseModel, Field


class CreateDeadlineRequest(BaseModel):
    lead_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    due_date: date
    recurrence_interval_days: int | None = Field(default=None, ge=1, le=3650)
