import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.task import Task, TaskComment, TaskType


class TaskTypeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[TaskType]:
        stmt = select(TaskType).where(TaskType.tenant_id == tenant_id).order_by(TaskType.name)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id_for_tenant(
        self, tenant_id: uuid.UUID, task_type_id: uuid.UUID
    ) -> TaskType | None:
        stmt = select(TaskType).where(TaskType.tenant_id == tenant_id, TaskType.id == task_type_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, *, tenant_id: uuid.UUID, name: str) -> TaskType:
        task_type = TaskType(tenant_id=tenant_id, name=name)
        self.db.add(task_type)
        self.db.flush()
        return task_type


@dataclass
class TaskFilters:
    assigned_membership_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    status: str | None = None
    overdue_only: bool = False


@dataclass
class TaskPage:
    items: list[Task] = field(default_factory=list)
    total: int = 0


class TaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id_for_tenant(self, tenant_id: uuid.UUID, task_id: uuid.UUID) -> Task | None:
        stmt = select(Task).where(Task.tenant_id == tenant_id, Task.id == task_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_tenant(
        self, tenant_id: uuid.UUID, *, filters: TaskFilters, page: int, page_size: int
    ) -> TaskPage:
        from sqlalchemy import func

        stmt = select(Task).where(Task.tenant_id == tenant_id)
        if filters.assigned_membership_id:
            stmt = stmt.where(Task.assigned_membership_id == filters.assigned_membership_id)
        if filters.lead_id:
            stmt = stmt.where(Task.lead_id == filters.lead_id)
        if filters.status:
            stmt = stmt.where(Task.status == filters.status)
        if filters.overdue_only:
            stmt = stmt.where(
                Task.status == "open", Task.due_at.is_not(None), Task.due_at < utcnow()
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self.db.execute(count_stmt).scalar_one())

        stmt = (
            stmt.order_by(Task.due_at.is_(None), Task.due_at)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return TaskPage(items=items, total=total)

    def create(
        self,
        *,
        tenant_id: uuid.UUID,
        title: str,
        description: str | None,
        lead_id: uuid.UUID | None,
        task_type_id: uuid.UUID | None,
        assigned_membership_id: uuid.UUID | None,
        priority: str,
        due_at: datetime | None,
        created_by_user_id: uuid.UUID | None,
    ) -> Task:
        task = Task(
            tenant_id=tenant_id,
            title=title,
            description=description,
            lead_id=lead_id,
            task_type_id=task_type_id,
            assigned_membership_id=assigned_membership_id,
            priority=priority,
            due_at=due_at,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(task)
        self.db.flush()
        return task

    def complete(self, task: Task) -> Task:
        task.status = "completed"
        task.completed_at = utcnow()
        self.db.flush()
        return task

    def update(self, task: Task, **fields: object) -> Task:
        for key, value in fields.items():
            if value is not None:
                setattr(task, key, value)
        self.db.flush()
        return task


class TaskCommentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, task_id: uuid.UUID, author_user_id: uuid.UUID, body: str) -> TaskComment:
        comment = TaskComment(
            task_id=task_id, author_user_id=author_user_id, body=body, created_at=utcnow()
        )
        self.db.add(comment)
        self.db.flush()
        return comment

    def list_for_task(self, task_id: uuid.UUID) -> list[TaskComment]:
        stmt = (
            select(TaskComment)
            .where(TaskComment.task_id == task_id)
            .order_by(TaskComment.created_at)
        )
        return list(self.db.execute(stmt).scalars().all())
