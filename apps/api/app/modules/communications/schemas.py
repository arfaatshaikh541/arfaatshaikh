import uuid

from pydantic import BaseModel, Field

from app.modules.communications.models import EmailDeliveryStatus, EmailTriggerEvent


class CreateEmailTemplateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    trigger_event: EmailTriggerEvent
    trigger_stage_outcome: str | None = Field(default=None, max_length=10)
    subject: str = Field(min_length=1, max_length=300)
    body_text: str = Field(min_length=1)
    body_html: str | None = None


class UpdateEmailTemplateRequest(BaseModel):
    name: str | None = None
    subject: str | None = None
    body_text: str | None = None
    body_html: str | None = None
    is_active: bool | None = None


class DeliveryLogOut(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID | None
    lead_id: uuid.UUID | None
    recipient: str
    subject: str
    status: EmailDeliveryStatus
    attempt_count: int
    last_error: str | None
    sent_at: str | None
    created_at: str

    model_config = {"from_attributes": True}
