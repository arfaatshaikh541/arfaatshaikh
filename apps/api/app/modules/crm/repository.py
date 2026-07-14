import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.crm.models import (
    Activity,
    Attachment,
    LeadStageHistory,
    LeadTag,
    Note,
    Pipeline,
    PipelineStage,
    Tag,
    Task,
    TaskComment,
    TaskStatus,
)


class PipelineRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_default(self, tenant_id: uuid.UUID) -> Pipeline | None:
        return self.db.execute(
            select(Pipeline).where(Pipeline.tenant_id == tenant_id, Pipeline.is_default.is_(True))
        ).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[Pipeline]:
        return list(self.db.execute(select(Pipeline).where(Pipeline.tenant_id == tenant_id)).scalars().all())

    def create(self, *, tenant_id: uuid.UUID, name: str, is_default: bool = False) -> Pipeline:
        pipeline = Pipeline(tenant_id=tenant_id, name=name, is_default=is_default)
        self.db.add(pipeline)
        self.db.flush()
        return pipeline

    def list_stages(self, tenant_id: uuid.UUID, pipeline_id: uuid.UUID) -> list[PipelineStage]:
        return list(
            self.db.execute(
                select(PipelineStage)
                .where(PipelineStage.tenant_id == tenant_id, PipelineStage.pipeline_id == pipeline_id)
                .order_by(PipelineStage.sort_order)
            )
            .scalars()
            .all()
        )

    def get_stage(self, tenant_id: uuid.UUID, stage_id: uuid.UUID) -> PipelineStage | None:
        return self.db.execute(
            select(PipelineStage).where(PipelineStage.tenant_id == tenant_id, PipelineStage.id == stage_id)
        ).scalar_one_or_none()

    def create_stage(
        self, *, tenant_id: uuid.UUID, pipeline_id: uuid.UUID, name: str, sort_order: int,
        is_won: bool = False, is_lost: bool = False,
    ) -> PipelineStage:
        stage = PipelineStage(
            tenant_id=tenant_id, pipeline_id=pipeline_id, name=name, sort_order=sort_order, is_won=is_won, is_lost=is_lost
        )
        self.db.add(stage)
        self.db.flush()
        return stage


class LeadStageHistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, from_stage_id, to_stage_id: uuid.UUID,
        changed_by, loss_reason: str | None = None,
    ) -> LeadStageHistory:
        entry = LeadStageHistory(
            tenant_id=tenant_id, lead_id=lead_id, from_stage_id=from_stage_id, to_stage_id=to_stage_id,
            changed_by=changed_by, loss_reason=loss_reason,
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_for_lead(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[LeadStageHistory]:
        return list(
            self.db.execute(
                select(LeadStageHistory)
                .where(LeadStageHistory.tenant_id == tenant_id, LeadStageHistory.lead_id == lead_id)
                .order_by(LeadStageHistory.created_at)
            )
            .scalars()
            .all()
        )


class TagRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[Tag]:
        return list(self.db.execute(select(Tag).where(Tag.tenant_id == tenant_id)).scalars().all())

    def get_by_name(self, tenant_id: uuid.UUID, name: str) -> Tag | None:
        return self.db.execute(select(Tag).where(Tag.tenant_id == tenant_id, Tag.name == name)).scalar_one_or_none()

    def create(self, *, tenant_id: uuid.UUID, name: str, color: str = "#6b7280") -> Tag:
        tag = Tag(tenant_id=tenant_id, name=name, color=color)
        self.db.add(tag)
        self.db.flush()
        return tag

    def add_to_lead(self, tenant_id: uuid.UUID, lead_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        existing = self.db.execute(
            select(LeadTag).where(LeadTag.lead_id == lead_id, LeadTag.tag_id == tag_id)
        ).scalar_one_or_none()
        if existing is None:
            self.db.add(LeadTag(tenant_id=tenant_id, lead_id=lead_id, tag_id=tag_id))
            self.db.flush()

    def remove_from_lead(self, lead_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        existing = self.db.execute(
            select(LeadTag).where(LeadTag.lead_id == lead_id, LeadTag.tag_id == tag_id)
        ).scalar_one_or_none()
        if existing is not None:
            self.db.delete(existing)
            self.db.flush()

    def list_for_lead(self, lead_id: uuid.UUID) -> list[Tag]:
        return list(
            self.db.execute(select(Tag).join(LeadTag, LeadTag.tag_id == Tag.id).where(LeadTag.lead_id == lead_id))
            .scalars()
            .all()
        )


class NoteRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, author_id, body: str) -> Note:
        note = Note(tenant_id=tenant_id, lead_id=lead_id, author_id=author_id, body=body)
        self.db.add(note)
        self.db.flush()
        return note

    def list_for_lead(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[Note]:
        return list(
            self.db.execute(
                select(Note).where(Note.tenant_id == tenant_id, Note.lead_id == lead_id).order_by(Note.created_at.desc())
            )
            .scalars()
            .all()
        )


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, task_id: uuid.UUID) -> Task | None:
        return self.db.execute(select(Task).where(Task.tenant_id == tenant_id, Task.id == task_id)).scalar_one_or_none()

    def create(self, **fields) -> Task:
        task = Task(**fields)
        self.db.add(task)
        self.db.flush()
        return task

    def list_for_lead(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[Task]:
        return list(
            self.db.execute(
                select(Task).where(Task.tenant_id == tenant_id, Task.lead_id == lead_id).order_by(Task.created_at.desc())
            )
            .scalars()
            .all()
        )

    def list_for_tenant(self, tenant_id: uuid.UUID, *, assigned_user_id: uuid.UUID | None = None, status: TaskStatus | None = None):
        stmt = select(Task).where(Task.tenant_id == tenant_id)
        if assigned_user_id:
            stmt = stmt.where(Task.assigned_user_id == assigned_user_id)
        if status:
            stmt = stmt.where(Task.status == status)
        return list(self.db.execute(stmt.order_by(Task.due_at.asc().nulls_last())).scalars().all())


class TaskCommentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, tenant_id: uuid.UUID, task_id: uuid.UUID, author_id, body: str) -> TaskComment:
        comment = TaskComment(tenant_id=tenant_id, task_id=task_id, author_id=author_id, body=body)
        self.db.add(comment)
        self.db.flush()
        return comment

    def list_for_task(self, tenant_id: uuid.UUID, task_id: uuid.UUID) -> list[TaskComment]:
        return list(
            self.db.execute(
                select(TaskComment).where(TaskComment.tenant_id == tenant_id, TaskComment.task_id == task_id).order_by(TaskComment.created_at)
            )
            .scalars()
            .all()
        )


class ActivityRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, actor_id, activity_type: str, summary: str, metadata_json: dict | None = None) -> Activity:
        activity = Activity(
            tenant_id=tenant_id, lead_id=lead_id, actor_id=actor_id, activity_type=activity_type,
            summary=summary, metadata_json=metadata_json or {},
        )
        self.db.add(activity)
        self.db.flush()
        return activity

    def list_for_lead(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[Activity]:
        return list(
            self.db.execute(
                select(Activity)
                .where(Activity.tenant_id == tenant_id, Activity.lead_id == lead_id)
                .order_by(Activity.created_at.desc())
            )
            .scalars()
            .all()
        )


class AttachmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, uploaded_by, file_name: str, content_type: str, size_bytes: int, storage_key: str) -> Attachment:
        attachment = Attachment(
            tenant_id=tenant_id, lead_id=lead_id, uploaded_by=uploaded_by, file_name=file_name,
            content_type=content_type, size_bytes=size_bytes, storage_key=storage_key,
        )
        self.db.add(attachment)
        self.db.flush()
        return attachment

    def list_for_lead(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[Attachment]:
        return list(
            self.db.execute(
                select(Attachment).where(Attachment.tenant_id == tenant_id, Attachment.lead_id == lead_id).order_by(Attachment.created_at.desc())
            )
            .scalars()
            .all()
        )

    def get(self, tenant_id: uuid.UUID, attachment_id: uuid.UUID) -> Attachment | None:
        return self.db.execute(
            select(Attachment).where(Attachment.tenant_id == tenant_id, Attachment.id == attachment_id)
        ).scalar_one_or_none()
