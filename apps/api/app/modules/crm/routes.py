import uuid

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.dependencies.entitlements import require_module
from app.dependencies.permissions import require_permission
from app.dependencies.tenant import get_tenant_context
from app.modules.crm import service as crm_service
from app.modules.crm.schemas import (
    AddTagRequest,
    ChangeStageRequest,
    CreateNoteRequest,
    CreateTaskRequest,
    TaskCommentRequest,
)

pipelines_router = APIRouter(prefix="/tenant/pipelines", tags=["pipelines"])
leads_crm_router = APIRouter(prefix="/tenant/leads", tags=["leads-crm"])
tasks_router = APIRouter(prefix="/tenant/tasks", tags=["tasks"])
tags_router = APIRouter(prefix="/tenant/tags", tags=["tags"])


@pipelines_router.get("")
def list_pipelines(
    ctx: TenantContext = Depends(require_permission("leads.view")),
    _mod: TenantContext = Depends(require_module("crm")),
    db: Session = Depends(get_db),
) -> list[dict]:
    pipelines = crm_service.list_pipelines(db, ctx.tenant_id)
    return [
        {
            "id": str(p.id), "name": p.name, "is_default": p.is_default,
            "stages": [
                {"id": str(s.id), "name": s.name, "sort_order": s.sort_order, "is_won": s.is_won, "is_lost": s.is_lost}
                for s in crm_service.list_stages(db, ctx.tenant_id, p.id)
            ],
        }
        for p in pipelines
    ]


@leads_crm_router.post("/{lead_id}/stage")
def change_stage(
    lead_id: uuid.UUID, payload: ChangeStageRequest,
    ctx: TenantContext = Depends(require_permission("leads.update")),
    _mod: TenantContext = Depends(require_module("crm")),
    db: Session = Depends(get_db),
) -> dict:
    crm_service.change_stage(
        db, tenant_id=ctx.tenant_id, lead_id=lead_id, new_stage_id=payload.stage_id,
        actor_id=ctx.user_id, loss_reason=payload.loss_reason,
    )
    return {"status": "ok"}


@leads_crm_router.get("/{lead_id}/history")
def get_stage_history(
    lead_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("leads.view")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> list[dict]:
    return [
        {
            "id": str(h.id), "from_stage_id": str(h.from_stage_id) if h.from_stage_id else None,
            "to_stage_id": str(h.to_stage_id), "changed_by": str(h.changed_by) if h.changed_by else None,
            "loss_reason": h.loss_reason, "created_at": h.created_at.isoformat(),
        }
        for h in crm_service.list_stage_history(db, ctx.tenant_id, lead_id)
    ]


@leads_crm_router.get("/{lead_id}/timeline")
def get_timeline(
    lead_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("leads.view")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> list[dict]:
    return [
        {
            "id": str(a.id), "actor_id": str(a.actor_id) if a.actor_id else None, "activity_type": a.activity_type,
            "summary": a.summary, "metadata": a.metadata_json, "created_at": a.created_at.isoformat(),
        }
        for a in crm_service.list_timeline(db, ctx.tenant_id, lead_id)
    ]


@leads_crm_router.get("/{lead_id}/notes")
def list_notes(
    lead_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("leads.view")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> list[dict]:
    return [
        {"id": str(n.id), "author_id": str(n.author_id) if n.author_id else None, "body": n.body, "created_at": n.created_at.isoformat()}
        for n in crm_service.list_notes(db, ctx.tenant_id, lead_id)
    ]


@leads_crm_router.post("/{lead_id}/notes", status_code=201)
def add_note(
    lead_id: uuid.UUID, payload: CreateNoteRequest,
    ctx: TenantContext = Depends(require_permission("leads.update")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    note = crm_service.add_note(db, tenant_id=ctx.tenant_id, lead_id=lead_id, author_id=ctx.user_id, body=payload.body)
    return {"id": str(note.id)}


@leads_crm_router.get("/{lead_id}/tags")
def list_lead_tags(
    lead_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("leads.view")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> list[dict]:
    return [{"id": str(t.id), "name": t.name, "color": t.color} for t in crm_service.list_tags_for_lead(db, lead_id)]


@leads_crm_router.post("/{lead_id}/tags", status_code=201)
def add_tag(
    lead_id: uuid.UUID, payload: AddTagRequest,
    ctx: TenantContext = Depends(require_permission("leads.update")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    tag = crm_service.add_tag_to_lead(db, tenant_id=ctx.tenant_id, lead_id=lead_id, tag_name=payload.name, actor_id=ctx.user_id)
    return {"id": str(tag.id), "name": tag.name}


@leads_crm_router.delete("/{lead_id}/tags/{tag_id}", status_code=204)
def remove_tag(
    lead_id: uuid.UUID, tag_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.update")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> None:
    crm_service.remove_tag_from_lead(db, tenant_id=ctx.tenant_id, lead_id=lead_id, tag_id=tag_id, actor_id=ctx.user_id)


@leads_crm_router.get("/{lead_id}/attachments")
def list_attachments(
    lead_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("documents.view")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> list[dict]:
    return [
        {
            "id": str(a.id), "file_name": a.file_name, "content_type": a.content_type, "size_bytes": a.size_bytes,
            "uploaded_by": str(a.uploaded_by) if a.uploaded_by else None, "created_at": a.created_at.isoformat(),
        }
        for a in crm_service.list_attachments(db, ctx.tenant_id, lead_id)
    ]


@leads_crm_router.post("/{lead_id}/attachments", status_code=201)
async def upload_attachment(
    lead_id: uuid.UUID, file: UploadFile,
    ctx: TenantContext = Depends(require_permission("documents.upload")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    content = await file.read()
    attachment = crm_service.upload_attachment(
        db, tenant_id=ctx.tenant_id, lead_id=lead_id, uploaded_by=ctx.user_id,
        file_name=file.filename or "upload", content_type=file.content_type or "application/octet-stream", content=content,
    )
    return {"id": str(attachment.id), "file_name": attachment.file_name}


@leads_crm_router.get("/{lead_id}/attachments/{attachment_id}/download-url")
def get_attachment_download_url(
    lead_id: uuid.UUID, attachment_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("documents.view")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    url = crm_service.get_attachment_download_url(db, ctx.tenant_id, attachment_id)
    return {"url": url}


@leads_crm_router.get("/{lead_id}/tasks")
def list_lead_tasks(
    lead_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("tasks.view")), db: Session = Depends(get_db)
) -> list[dict]:
    return [_task_to_dict(t) for t in crm_service.list_tasks_for_lead(db, ctx.tenant_id, lead_id)]


@leads_crm_router.post("/{lead_id}/tasks", status_code=201)
def create_lead_task(
    lead_id: uuid.UUID, payload: CreateTaskRequest,
    ctx: TenantContext = Depends(require_permission("tasks.manage")),
    _mod: TenantContext = Depends(require_module("tasks")), db: Session = Depends(get_db),
) -> dict:
    task = crm_service.create_task(
        db, tenant_id=ctx.tenant_id, lead_id=lead_id, title=payload.title, description=payload.description,
        assigned_user_id=payload.assigned_user_id, created_by=ctx.user_id, due_at=payload.due_at, priority=payload.priority,
    )
    return {"id": str(task.id)}


def _task_to_dict(task) -> dict:
    return {
        "id": str(task.id), "lead_id": str(task.lead_id) if task.lead_id else None, "title": task.title,
        "description": task.description, "assigned_user_id": str(task.assigned_user_id) if task.assigned_user_id else None,
        "due_at": task.due_at.isoformat() if task.due_at else None, "priority": task.priority.value,
        "status": task.status.value, "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "source": task.source, "created_at": task.created_at.isoformat(),
    }


@tasks_router.get("")
def list_tasks(
    assigned_user_id: uuid.UUID | None = None, ctx: TenantContext = Depends(require_permission("tasks.view")),
    db: Session = Depends(get_db),
) -> list[dict]:
    return [_task_to_dict(t) for t in crm_service.list_tasks_for_tenant(db, ctx.tenant_id, assigned_user_id=assigned_user_id)]


@tasks_router.post("/{task_id}/complete")
def complete_task(
    task_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("tasks.manage")), db: Session = Depends(get_db)
) -> dict:
    crm_service.complete_task(db, tenant_id=ctx.tenant_id, task_id=task_id, actor_id=ctx.user_id)
    return {"status": "ok"}


@tasks_router.post("/{task_id}/comments", status_code=201)
def add_task_comment(
    task_id: uuid.UUID, payload: TaskCommentRequest,
    ctx: TenantContext = Depends(require_permission("tasks.manage")), db: Session = Depends(get_db),
) -> dict:
    comment = crm_service.add_task_comment(db, tenant_id=ctx.tenant_id, task_id=task_id, author_id=ctx.user_id, body=payload.body)
    return {"id": str(comment.id)}


@tags_router.get("")
def list_tags(ctx: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": str(t.id), "name": t.name, "color": t.color} for t in crm_service.list_tags_for_tenant(db, ctx.tenant_id)]
