import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.schemas.qualification import QualificationQuestionOut


class PublicServiceOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None


class PublicFormConfigOut(BaseModel):
    tenant_name: str
    brand_primary_color: str
    brand_secondary_color: str
    logo_url: str | None
    services: list[PublicServiceOut]
    questions: list[QualificationQuestionOut]
    privacy_text: str | None


class PublicAnswerInput(BaseModel):
    question_id: uuid.UUID
    value: object


class PublicEnquirySubmitRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = None
    company: str | None = Field(default=None, max_length=200)
    service_id: uuid.UUID | None = None
    preferred_contact_method: str | None = None
    consent_given: bool = False
    answers: list[PublicAnswerInput] = Field(default_factory=list)

    # Honeypot: a hidden field real visitors never fill in. Named
    # innocuously so scrapers/bots are more likely to auto-fill it.
    website: str = Field(default="", max_length=200)

    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_term: str | None = None
    utm_content: str | None = None
    referrer_url: str | None = None


class PublicEnquirySubmitResponse(BaseModel):
    reference_number: str | None
    message: str
