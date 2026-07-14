import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.crm.models import TaskPriority, TaskStatus


class PipelineStageOut(BaseModel):
    id: uuid.UUID
    name: str
    sort_order: int
    is_won: bool
    is_lost: bool

    model_config = {"from_attributes": True}


class PipelineOut(BaseModel):
    id: uuid.UUID
    name: str
    is_default: bool
    stages: list[PipelineStageOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ChangeStageRequest(BaseModel):
    stage_id: uuid.UUID
    loss_reason: str | None = None


class CreateNoteRequest(BaseModel):
    body: str = Field(min_length=1)


class NoteOut(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID | None
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    assigned_user_id: uuid.UUID | None = None
    due_at: datetime | None = None
    priority: TaskPriority = TaskPriority.MEDIUM


class TaskOut(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID | None
    title: str
    description: str
    assigned_user_id: uuid.UUID | None
    due_at: datetime | None
    priority: TaskPriority
    status: TaskStatus
    completed_at: datetime | None
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskCommentRequest(BaseModel):
    body: str = Field(min_length=1)


class AddTagRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TagOut(BaseModel):
    id: uuid.UUID
    name: str
    color: str

    model_config = {"from_attributes": True}


class ActivityOut(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    activity_type: str
    summary: str
    metadata_json: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class AttachmentOut(BaseModel):
    id: uuid.UUID
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
