import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ServiceCategoryOut(ORMModel):
    id: uuid.UUID
    name: str
    sort_order: int


class ServiceCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    sort_order: int = 0


class ServiceOut(ORMModel):
    id: uuid.UUID
    category_id: uuid.UUID | None
    name: str
    slug: str
    description: str | None
    is_active: bool
    sort_order: int


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    category_id: uuid.UUID | None = None
    description: str | None = None
    sort_order: int = 0


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class BranchOut(ORMModel):
    id: uuid.UUID
    name: str
    is_active: bool


class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class TagOut(ORMModel):
    id: uuid.UUID
    name: str
    color: str


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: str = "#6B7280"


class LossReasonOut(ORMModel):
    id: uuid.UUID
    label: str
    sort_order: int


class LossReasonCreate(BaseModel):
    label: str = Field(min_length=1, max_length=150)
    sort_order: int = 0


class PipelineStageOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    sort_order: int
    is_won: bool
    is_lost: bool
    is_system: bool


class PipelineStageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    is_won: bool = False
    is_lost: bool = False


class PipelineStageReorderRequest(BaseModel):
    stage_ids: list[uuid.UUID]
