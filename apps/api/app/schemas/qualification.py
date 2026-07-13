import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CustomFieldOptionOut(ORMModel):
    value: str
    label: str
    sort_order: int


class CustomFieldDefinitionOut(ORMModel):
    id: uuid.UUID
    field_key: str
    label: str
    field_type: str
    is_required: bool
    is_active: bool
    options: list[CustomFieldOptionOut] = Field(default_factory=list)


class QualificationRuleOut(ORMModel):
    id: uuid.UUID
    depends_on_question_id: uuid.UUID
    operator: str
    depends_on_value: str
    action: str


class QualificationQuestionOut(ORMModel):
    id: uuid.UUID
    sort_order: int
    is_required: bool
    help_text: str | None
    is_active: bool
    field_definition: CustomFieldDefinitionOut
    rules: list[QualificationRuleOut] = Field(default_factory=list)


class QualificationFormOut(ORMModel):
    id: uuid.UUID
    name: str
    is_default: bool
    is_active: bool
    questions: list[QualificationQuestionOut] = Field(default_factory=list)


class QualificationQuestionCreate(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    field_type: str
    is_required: bool = False
    help_text: str | None = None
    options: list[str] | None = None


class QualificationRuleCreate(BaseModel):
    question_id: uuid.UUID
    depends_on_question_id: uuid.UUID
    depends_on_value: str = Field(min_length=1, max_length=200)


class QuestionReorderRequest(BaseModel):
    question_ids: list[uuid.UUID]
