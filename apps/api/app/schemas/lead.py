import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class LeadAnswerOut(ORMModel):
    id: uuid.UUID
    question_id: uuid.UUID | None
    question_label_snapshot: str
    field_type_snapshot: str
    value: object


class LeadOut(ORMModel):
    id: uuid.UUID
    reference_number: str
    first_name: str
    last_name: str
    phone: str | None
    email: str | None
    company: str | None
    service_id: uuid.UUID | None
    branch_id: uuid.UUID | None
    stage_id: uuid.UUID
    source: str
    priority: str
    score: int
    score_reasons: list = Field(default_factory=list)
    estimated_value: float | None
    assigned_membership_id: uuid.UUID | None
    preferred_contact_method: str | None
    next_follow_up_at: datetime | None
    consent_given: bool
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    is_possible_duplicate: bool
    duplicate_of_lead_id: uuid.UUID | None
    loss_reason_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class LeadDetailOut(LeadOut):
    answers: list[LeadAnswerOut] = Field(default_factory=list)
    tag_ids: list[uuid.UUID] = Field(default_factory=list)


class LeadListOut(ORMModel):
    items: list[LeadOut]
    total: int
    page: int
    page_size: int


class LeadCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    service_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    priority: str = "standard"
    estimated_value: float | None = None
    preferred_contact_method: str | None = None
    consent_given: bool = False


class LeadUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    service_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    priority: str | None = None
    estimated_value: float | None = None
    preferred_contact_method: str | None = None
    next_follow_up_at: datetime | None = None


class LeadStageChangeRequest(BaseModel):
    to_stage_id: uuid.UUID
    loss_reason_id: uuid.UUID | None = None
    reason: str | None = None


class LeadAssignRequest(BaseModel):
    membership_id: uuid.UUID | None = None


class LeadTagRequest(BaseModel):
    tag_id: uuid.UUID


class LeadNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class LeadNoteOut(ORMModel):
    id: uuid.UUID
    author_user_id: uuid.UUID | None
    body: str
    created_at: datetime


class LeadBulkStageChangeRequest(BaseModel):
    lead_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    to_stage_id: uuid.UUID
    loss_reason_id: uuid.UUID | None = None


class LeadBulkAssignRequest(BaseModel):
    lead_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    membership_id: uuid.UUID | None = None


class BulkActionResult(BaseModel):
    updated: list[uuid.UUID]
    failed: list[uuid.UUID]


class TimelineEntryOut(ORMModel):
    id: uuid.UUID
    event_type: str
    actor_user_id: uuid.UUID | None
    entity_type: str | None
    entity_id: str | None
    event_metadata: dict
    created_at: datetime
