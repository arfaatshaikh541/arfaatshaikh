import uuid

from pydantic import BaseModel, Field

from app.modules.onboarding.models import OnboardingStepType


class OnboardingTemplateStepInput(BaseModel):
    step_type: OnboardingStepType
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    due_in_days: int | None = Field(default=None, ge=0, le=365)


class CreateOnboardingTemplateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = ""
    steps: list[OnboardingTemplateStepInput] = Field(default_factory=list)


class StartOnboardingCaseRequest(BaseModel):
    lead_id: uuid.UUID
    template_id: uuid.UUID | None = None
    name: str | None = Field(default=None, max_length=200)
