from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.task import TASK_PRIORITIES, Task, TaskComment, TaskType
from app.repositories.lead import LeadRepository
from app.repositories.membership import MembershipRepository
from app.repositories.task import (
    TaskCommentRepository,
    TaskFilters,
    TaskPage,
    TaskRepository,
    TaskTypeRepository,
)
from app.services.errors import NotFoundError, ValidationError


class TaskService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.tasks = TaskRepository(db)
        self.task_types = TaskTypeRepository(db)
        self.comments = TaskCommentRepository(db)
        self.memberships = MembershipRepository(db)
        self.leads = LeadRepository(db)

    def get_or_404(self, tenant_id: uuid.UUID, task_id: uuid.UUID) -> Task:
        task = self.tasks.get_by_id_for_tenant(tenant_id, task_id)
        if task is None:
            raise NotFoundError("Task not found.")
        return task

    def list_tasks(
        self, tenant_id: uuid.UUID, *, filters: TaskFilters, page: int, page_size: int
    ) -> TaskPage:
        return self.tasks.list_for_tenant(
            tenant_id, filters=filters, page=page, page_size=page_size
        )

    def create(
        self,
        tenant_id: uuid.UUID,
        *,
        created_by_user_id: uuid.UUID | None,
        title: str,
        description: str | None = None,
        lead_id: uuid.UUID | None = None,
        task_type_id: uuid.UUID | None = None,
        assigned_membership_id: uuid.UUID | None = None,
        priority: str = "normal",
        due_at: datetime | None = None,
    ) -> Task:
        if priority not in TASK_PRIORITIES:
            raise ValidationError(f"Unknown task priority '{priority}'.")
        if lead_id is not None and self.leads.get_by_id_for_tenant(tenant_id, lead_id) is None:
            raise ValidationError("Lead does not belong to this tenant.")
        if (
            task_type_id is not None
            and self.task_types.get_by_id_for_tenant(tenant_id, task_type_id) is None
        ):
            raise ValidationError("Task type does not belong to this tenant.")
        if assigned_membership_id is not None:
            if self.memberships.get_by_id_for_tenant(tenant_id, assigned_membership_id) is None:
                raise ValidationError("Assignee does not belong to this tenant.")
        return self.tasks.create(
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

    def complete(self, tenant_id: uuid.UUID, task_id: uuid.UUID) -> Task:
        task = self.get_or_404(tenant_id, task_id)
        return self.tasks.complete(task)

    def add_comment(
        self, tenant_id: uuid.UUID, task_id: uuid.UUID, *, author_user_id: uuid.UUID, body: str
    ) -> TaskComment:
        task = self.get_or_404(tenant_id, task_id)
        return self.comments.create(task_id=task.id, author_user_id=author_user_id, body=body)

    def list_comments(self, tenant_id: uuid.UUID, task_id: uuid.UUID) -> list[TaskComment]:
        task = self.get_or_404(tenant_id, task_id)
        return self.comments.list_for_task(task.id)

    # -- task types --------------------------------------------------------

    def list_task_types(self, tenant_id: uuid.UUID) -> list[TaskType]:
        return self.task_types.list_for_tenant(tenant_id)

    def create_task_type(self, tenant_id: uuid.UUID, *, name: str) -> TaskType:
        return self.task_types.create(tenant_id=tenant_id, name=name)

    # -- default automation -------------------------------------------------

    def create_qualified_callback_task(
        self, tenant_id: uuid.UUID, *, lead_id: uuid.UUID, assigned_membership_id: uuid.UUID | None
    ) -> Task:
        """Default automation: moving a lead into a qualified-flagged stage
        creates a callback task for whoever it's assigned to (or unassigned,
        for a manager to triage). See Module 9 default automations."""
        return self.tasks.create(
            tenant_id=tenant_id,
            title="Call back qualified lead",
            description="This lead was just marked as qualified - reach out within 24 hours.",
            lead_id=lead_id,
            task_type_id=None,
            assigned_membership_id=assigned_membership_id,
            priority="high",
            due_at=utcnow() + timedelta(hours=24),
            created_by_user_id=None,
        )
