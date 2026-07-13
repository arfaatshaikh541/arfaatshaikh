import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class MessageTemplateOut(ORMModel):
    id: uuid.UUID
    key: str
    subject: str
    body: str
    is_active: bool


class MessageTemplateCreate(BaseModel):
    key: str
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)


class MessageTemplateUpdate(BaseModel):
    subject: str | None = None
    body: str | None = None
    is_active: bool | None = None


class NotificationOut(ORMModel):
    id: uuid.UUID
    title: str
    body: str | None
    related_entity_type: str | None
    related_entity_id: str | None
    is_read: bool
    created_at: datetime
