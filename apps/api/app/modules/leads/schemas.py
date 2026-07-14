import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.modules.leads.models import ConsentStatus, LeadPriority, PreferredContactMethod, QualificationQuestionType


class QualificationAnswerInput(BaseModel):
    question_id: uuid.UUID
    value: Any


class PublicLeadCaptureRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    company: str | None = Field(default=None, max_length=200)
    service_id: uuid.UUID | None = None
    preferred_contact_method: PreferredContactMethod | None = None
    consent_given: bool = False
    answers: list[QualificationAnswerInput] = Field(default_factory=list)
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=100)
    # Honeypot: a real visitor never fills this hidden field in; a bot
    # filling every field usually does. Left populated = silently drop.
    website: str = Field(default="", max_length=200)

    @field_validator("email")
    @classmethod
    def email_or_none(cls, value: str | None) -> str | None:
        return value or None


class ManualLeadCreateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    service_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    preferred_contact_method: PreferredContactMethod | None = None
    priority: LeadPriority = LeadPriority.MEDIUM
    estimated_value: float | None = None


class LeadUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    service_id: uuid.UUID | None = None
    priority: LeadPriority | None = None
    estimated_value: float | None = None
    preferred_contact_method: PreferredContactMethod | None = None
    next_follow_up_at: str | None = None
    consent_status: ConsentStatus | None = None


class AssignLeadRequest(BaseModel):
    assigned_user_id: uuid.UUID | None = None


class CreateServiceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = ""
    category_id: uuid.UUID | None = None


class CreateQualificationFormRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    service_id: uuid.UUID | None = None


class ReorderQuestionsRequest(BaseModel):
    question_ids: list[uuid.UUID]


class ChangeStageRequest(BaseModel):
    stage_id: uuid.UUID
    loss_reason: str | None = None


class LeadSummary(BaseModel):
    id: uuid.UUID
    reference_number: str
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    company: str | None
    service_id: uuid.UUID | None
    stage_id: uuid.UUID | None
    priority: LeadPriority
    assigned_user_id: uuid.UUID | None
    is_possible_duplicate: bool
    created_at: str

    model_config = {"from_attributes": True}


class QuestionOptionOut(BaseModel):
    id: uuid.UUID
    label: str
    value: str

    model_config = {"from_attributes": True}


class QuestionOut(BaseModel):
    id: uuid.UUID
    label: str
    question_type: QualificationQuestionType
    is_required: bool
    sort_order: int
    maps_to_field: str | None
    options: list[QuestionOptionOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PublicQualificationFormOut(BaseModel):
    tenant_name: str
    services: list[dict]
    form_id: uuid.UUID | None
    questions: list[QuestionOut]


class CreateQuestionRequest(BaseModel):
    label: str = Field(min_length=1, max_length=300)
    question_type: QualificationQuestionType
    is_required: bool = False
    maps_to_field: str | None = None
    options: list[str] = Field(default_factory=list)
