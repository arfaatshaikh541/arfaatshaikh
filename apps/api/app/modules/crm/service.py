import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.storage import build_storage_key, get_storage_adapter
from app.modules.audit.service import log_event
from app.modules.crm.models import Activity, Attachment, Note, Pipeline, PipelineStage, Task, TaskComment, TaskStatus
from app.modules.crm.repository import (
    ActivityRepository,
    AttachmentRepository,
    LeadStageHistoryRepository,
    NoteRepository,
    PipelineRepository,
    TagRepository,
    TaskCommentRepository,
    TaskRepository,
)
from app.modules.leads.repository import LeadRepository

DEFAULT_STAGE_NAMES = [
    ("New", False, False),
    ("Contacted", False, False),
    ("Qualified", False, False),
    ("Consultation Booked", False, False),
    ("Proposal Sent", False, False),
    ("Follow-Up", False, False),
    ("Won", True, False),
    ("Lost", False, True),
    ("Nurture", False, False),
    ("Archived", False, False),
]

ALLOWED_ATTACHMENT_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
}
MAX_ATTACHMENT_SIZE_BYTES = 20 * 1024 * 1024


def ensure_default_pipeline(db: Session, tenant_id: uuid.UUID) -> tuple[Pipeline | None, PipelineStage | None]:
    """Idempotent: returns the tenant's default pipeline and its first
    stage, creating both (with the ten spec-default stage names) if this
    tenant doesn't have one yet."""
    pipeline_repo = PipelineRepository(db)
    pipeline = pipeline_repo.get_default(tenant_id)
    if pipeline is None:
        pipeline = pipeline_repo.create(tenant_id=tenant_id, name="Default Pipeline", is_default=True)
        for index, (name, is_won, is_lost) in enumerate(DEFAULT_STAGE_NAMES):
            pipeline_repo.create_stage(tenant_id=tenant_id, pipeline_id=pipeline.id, name=name, sort_order=index, is_won=is_won, is_lost=is_lost)

    stages = pipeline_repo.list_stages(tenant_id, pipeline.id)
    return pipeline, (stages[0] if stages else None)


def list_pipelines(db: Session, tenant_id: uuid.UUID) -> list[Pipeline]:
    return PipelineRepository(db).list_for_tenant(tenant_id)


def list_stages(db: Session, tenant_id: uuid.UUID, pipeline_id: uuid.UUID) -> list[PipelineStage]:
    return PipelineRepository(db).list_stages(tenant_id, pipeline_id)


def record_activity(
    db: Session, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, actor_id: uuid.UUID | None,
    activity_type: str, summary: str, metadata_json: dict | None = None,
) -> Activity:
    return ActivityRepository(db).create(
        tenant_id=tenant_id, lead_id=lead_id, actor_id=actor_id, activity_type=activity_type,
        summary=summary, metadata_json=metadata_json,
    )


def list_timeline(db: Session, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[Activity]:
    return ActivityRepository(db).list_for_lead(tenant_id, lead_id)


def change_stage(db: Session, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, new_stage_id: uuid.UUID, actor_id: uuid.UUID | None, loss_reason: str | None = None):
    lead = LeadRepository(db).get(tenant_id, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found.")
    new_stage = PipelineRepository(db).get_stage(tenant_id, new_stage_id)
    if new_stage is None:
        raise NotFoundError("Pipeline stage not found.")

    old_stage_id = lead.stage_id
    lead.stage_id = new_stage.id
    db.add(lead)
    db.flush()

    LeadStageHistoryRepository(db).create(
        tenant_id=tenant_id, lead_id=lead_id, from_stage_id=old_stage_id, to_stage_id=new_stage.id,
        changed_by=actor_id, loss_reason=loss_reason,
    )
    record_activity(
        db, tenant_id=tenant_id, lead_id=lead_id, actor_id=actor_id, activity_type="lead.stage_changed",
        summary=f"Stage changed to {new_stage.name}", metadata_json={"to_stage": new_stage.name, "loss_reason": loss_reason},
    )
    log_event(db, tenant_id=tenant_id, actor_user_id=actor_id, action="lead.stage_changed", entity_type="lead", entity_id=lead_id, after={"stage": new_stage.name})

    if lead.email and (new_stage.is_won or new_stage.is_lost):
        from app.modules.communications.models import EmailTriggerEvent
        from app.modules.communications.service import send_templated_email
        from app.modules.tenancy import service as tenancy_service

        tenant = tenancy_service.get_tenant_or_404(db, tenant_id)
        send_templated_email(
            db, tenant_id=tenant_id, trigger_event=EmailTriggerEvent.STAGE_CHANGED, recipient=lead.email,
            lead_id=lead.id, stage_outcome="won" if new_stage.is_won else "lost",
            context={
                "first_name": lead.first_name, "last_name": lead.last_name, "company": lead.company or "",
                "reference_number": lead.reference_number, "tenant_name": tenant.name, "stage_name": new_stage.name,
            },
        )

    from app.modules.workflow_automation.models import WorkflowTriggerEvent
    from app.modules.workflow_automation.service import evaluate_triggers_for_lead

    evaluate_triggers_for_lead(
        db, tenant_id=tenant_id, trigger_event=WorkflowTriggerEvent.STAGE_CHANGED, lead=lead,
        context={"stage_name": new_stage.name},
    )
    return lead


def list_stage_history(db: Session, tenant_id: uuid.UUID, lead_id: uuid.UUID):
    return LeadStageHistoryRepository(db).list_for_lead(tenant_id, lead_id)


def add_note(db: Session, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, author_id: uuid.UUID | None, body: str) -> Note:
    note = NoteRepository(db).create(tenant_id=tenant_id, lead_id=lead_id, author_id=author_id, body=body)
    record_activity(db, tenant_id=tenant_id, lead_id=lead_id, actor_id=author_id, activity_type="note.added", summary="Note added")
    return note


def list_notes(db: Session, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[Note]:
    return NoteRepository(db).list_for_lead(tenant_id, lead_id)


def create_task(
    db: Session, *, tenant_id: uuid.UUID, lead_id: uuid.UUID | None, title: str, description: str = "",
    assigned_user_id: uuid.UUID | None = None, created_by: uuid.UUID | None = None,
    due_at: datetime | None = None, priority=None, source: str = "manual",
) -> Task:
    from app.modules.crm.models import TaskPriority

    task = TaskRepository(db).create(
        tenant_id=tenant_id, lead_id=lead_id, title=title, description=description,
        assigned_user_id=assigned_user_id, created_by=created_by, due_at=due_at,
        priority=priority or TaskPriority.MEDIUM, source=source,
    )
    if lead_id:
        record_activity(db, tenant_id=tenant_id, lead_id=lead_id, actor_id=created_by, activity_type="task.created", summary=f"Task created: {title}")
    return task


def complete_task(db: Session, *, tenant_id: uuid.UUID, task_id: uuid.UUID, actor_id: uuid.UUID | None) -> Task:
    from datetime import datetime as _dt

    task = TaskRepository(db).get(tenant_id, task_id)
    if task is None:
        raise NotFoundError("Task not found.")
    task.status = TaskStatus.COMPLETED
    task.completed_at = _dt.now(UTC)
    db.add(task)
    db.flush()
    if task.lead_id:
        record_activity(db, tenant_id=tenant_id, lead_id=task.lead_id, actor_id=actor_id, activity_type="task.completed", summary=f"Task completed: {task.title}")
    return task


def list_tasks_for_lead(db: Session, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[Task]:
    return TaskRepository(db).list_for_lead(tenant_id, lead_id)


def list_tasks_for_tenant(db: Session, tenant_id: uuid.UUID, *, assigned_user_id: uuid.UUID | None = None, status: TaskStatus | None = None):
    return TaskRepository(db).list_for_tenant(tenant_id, assigned_user_id=assigned_user_id, status=status)


def add_task_comment(db: Session, *, tenant_id: uuid.UUID, task_id: uuid.UUID, author_id: uuid.UUID | None, body: str) -> TaskComment:
    task = TaskRepository(db).get(tenant_id, task_id)
    if task is None:
        raise NotFoundError("Task not found.")
    return TaskCommentRepository(db).create(tenant_id=tenant_id, task_id=task_id, author_id=author_id, body=body)


def add_tag_to_lead(db: Session, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, tag_name: str, actor_id: uuid.UUID | None):
    tag_repo = TagRepository(db)
    tag = tag_repo.get_by_name(tenant_id, tag_name)
    if tag is None:
        tag = tag_repo.create(tenant_id=tenant_id, name=tag_name)
    tag_repo.add_to_lead(tenant_id, lead_id, tag.id)
    record_activity(db, tenant_id=tenant_id, lead_id=lead_id, actor_id=actor_id, activity_type="tag.added", summary=f"Tag added: {tag.name}")

    lead = LeadRepository(db).get(tenant_id, lead_id)
    if lead is not None:
        from app.modules.workflow_automation.models import WorkflowTriggerEvent
        from app.modules.workflow_automation.service import evaluate_triggers_for_lead

        evaluate_triggers_for_lead(
            db, tenant_id=tenant_id, trigger_event=WorkflowTriggerEvent.TAG_ADDED, lead=lead, context={"tag_name": tag.name}
        )
    return tag


def remove_tag_from_lead(db: Session, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, tag_id: uuid.UUID, actor_id: uuid.UUID | None) -> None:
    TagRepository(db).remove_from_lead(lead_id, tag_id)
    record_activity(db, tenant_id=tenant_id, lead_id=lead_id, actor_id=actor_id, activity_type="tag.removed", summary="Tag removed")


def list_tags_for_lead(db: Session, lead_id: uuid.UUID):
    return TagRepository(db).list_for_lead(lead_id)


def list_tags_for_tenant(db: Session, tenant_id: uuid.UUID):
    return TagRepository(db).list_for_tenant(tenant_id)


def upload_attachment(
    db: Session, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, uploaded_by: uuid.UUID | None,
    file_name: str, content_type: str, content: bytes,
) -> Attachment:
    if content_type not in ALLOWED_ATTACHMENT_CONTENT_TYPES:
        raise ForbiddenError(f"File type '{content_type}' is not allowed.", code="attachment_type_not_allowed")
    if len(content) > MAX_ATTACHMENT_SIZE_BYTES:
        raise ConflictError("File exceeds the maximum allowed size of 20MB.", code="attachment_too_large")

    lead = LeadRepository(db).get(tenant_id, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found.")

    storage_key = build_storage_key(tenant_id=tenant_id, module="leads", entity_id=lead_id, filename=file_name)
    get_storage_adapter().save(storage_key, content, content_type)

    attachment = AttachmentRepository(db).create(
        tenant_id=tenant_id, lead_id=lead_id, uploaded_by=uploaded_by, file_name=file_name,
        content_type=content_type, size_bytes=len(content), storage_key=storage_key,
    )
    record_activity(db, tenant_id=tenant_id, lead_id=lead_id, actor_id=uploaded_by, activity_type="attachment.uploaded", summary=f"File uploaded: {file_name}")
    return attachment


def list_attachments(db: Session, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[Attachment]:
    return AttachmentRepository(db).list_for_lead(tenant_id, lead_id)


def get_attachment_download_url(db: Session, tenant_id: uuid.UUID, attachment_id: uuid.UUID) -> str:
    attachment = AttachmentRepository(db).get(tenant_id, attachment_id)
    if attachment is None:
        raise NotFoundError("Attachment not found.")
    return get_storage_adapter().get_download_url(attachment.storage_key)
