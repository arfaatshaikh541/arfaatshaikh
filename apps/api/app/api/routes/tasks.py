from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import MembershipContext, require_permission
from app.api.serializers import build_task_out
from app.db.session import get_db
from app.repositories.task import TaskFilters
from app.schemas.task import (
    TaskCommentCreate,
    TaskCommentOut,
    TaskCreate,
    TaskListOut,
    TaskOut,
    TaskTypeCreate,
    TaskTypeOut,
)
from app.services.task_service import TaskService

router = APIRouter(prefix="/tenants/me/tasks", tags=["tasks"])
task_types_router = APIRouter(prefix="/tenants/me/task-types", tags=["tasks"])


@router.get("", response_model=TaskListOut)
def list_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    assigned_membership_id: uuid.UUID | None = None,
    lead_id: uuid.UUID | None = None,
    status: str | None = None,
    overdue_only: bool = False,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("tasks.view")),
) -> TaskListOut:
    filters = TaskFilters(
        assigned_membership_id=assigned_membership_id,
        lead_id=lead_id,
        status=status,
        overdue_only=overdue_only,
    )
    result = TaskService(db).list_tasks(
        ctx.tenant_id, filters=filters, page=page, page_size=page_size
    )
    return TaskListOut(
        items=[build_task_out(t) for t in result.items],
        total=result.total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("tasks.manage")),
) -> TaskOut:
    task = TaskService(db).create(
        ctx.tenant_id, created_by_user_id=ctx.user.id, **payload.model_dump()
    )
    db.commit()
    return build_task_out(task)


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("tasks.view")),
) -> TaskOut:
    task = TaskService(db).get_or_404(ctx.tenant_id, task_id)
    return build_task_out(task)


@router.post("/{task_id}/complete", response_model=TaskOut)
def complete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("tasks.manage")),
) -> TaskOut:
    task = TaskService(db).complete(ctx.tenant_id, task_id)
    db.commit()
    return build_task_out(task)


@router.get("/{task_id}/comments", response_model=list[TaskCommentOut])
def list_task_comments(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("tasks.view")),
) -> list[TaskCommentOut]:
    comments = TaskService(db).list_comments(ctx.tenant_id, task_id)
    return [TaskCommentOut.model_validate(c) for c in comments]


@router.post("/{task_id}/comments", response_model=TaskCommentOut, status_code=201)
def add_task_comment(
    task_id: uuid.UUID,
    payload: TaskCommentCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("tasks.manage")),
) -> TaskCommentOut:
    comment = TaskService(db).add_comment(
        ctx.tenant_id, task_id, author_user_id=ctx.user.id, body=payload.body
    )
    db.commit()
    return TaskCommentOut.model_validate(comment)


@task_types_router.get("", response_model=list[TaskTypeOut])
def list_task_types(
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("tasks.view")),
) -> list[TaskTypeOut]:
    task_types = TaskService(db).list_task_types(ctx.tenant_id)
    return [TaskTypeOut.model_validate(t) for t in task_types]


@task_types_router.post("", response_model=TaskTypeOut, status_code=201)
def create_task_type(
    payload: TaskTypeCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("tasks.manage")),
) -> TaskTypeOut:
    task_type = TaskService(db).create_task_type(ctx.tenant_id, name=payload.name)
    db.commit()
    return TaskTypeOut.model_validate(task_type)
