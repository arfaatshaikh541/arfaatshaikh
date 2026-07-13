import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class TaskTypeOut(ORMModel):
    id: uuid.UUID
    name: str


class TaskTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TaskOut(ORMModel):
    id: uuid.UUID
    lead_id: uuid.UUID | None
    task_type_id: uuid.UUID | None
    title: str
    description: str | None
    assigned_membership_id: uuid.UUID | None
    priority: str
    status: str
    due_at: datetime | None
    completed_at: datetime | None
    created_by_user_id: uuid.UUID | None
    created_at: datetime
    is_overdue: bool = False


class TaskListOut(ORMModel):
    items: list[TaskOut]
    total: int
    page: int
    page_size: int


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    lead_id: uuid.UUID | None = None
    task_type_id: uuid.UUID | None = None
    assigned_membership_id: uuid.UUID | None = None
    priority: str = "normal"
    due_at: datetime | None = None


class TaskCommentOut(ORMModel):
    id: uuid.UUID
    author_user_id: uuid.UUID
    body: str
    created_at: datetime


class TaskCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
