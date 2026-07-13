import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.pipeline_stages import DEFAULT_PIPELINE_STAGES
from app.models.pipeline import LossReason, PipelineStage, Tag


class PipelineStageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_defaults_for_tenant(self, tenant_id: uuid.UUID) -> dict[str, PipelineStage]:
        stages: dict[str, PipelineStage] = {}
        for index, default in enumerate(DEFAULT_PIPELINE_STAGES):
            stage = PipelineStage(
                tenant_id=tenant_id,
                name=default.name,
                slug=default.slug,
                sort_order=index,
                is_won=default.is_won,
                is_lost=default.is_lost,
                is_system=True,
            )
            self.db.add(stage)
            stages[default.slug] = stage
        self.db.flush()
        return stages

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[PipelineStage]:
        stmt = (
            select(PipelineStage)
            .where(PipelineStage.tenant_id == tenant_id)
            .order_by(PipelineStage.sort_order)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id_for_tenant(
        self, tenant_id: uuid.UUID, stage_id: uuid.UUID
    ) -> PipelineStage | None:
        stmt = select(PipelineStage).where(
            PipelineStage.tenant_id == tenant_id, PipelineStage.id == stage_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_slug_for_tenant(self, tenant_id: uuid.UUID, slug: str) -> PipelineStage | None:
        stmt = select(PipelineStage).where(
            PipelineStage.tenant_id == tenant_id, PipelineStage.slug == slug
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        slug: str,
        sort_order: int,
        is_won: bool,
        is_lost: bool,
    ) -> PipelineStage:
        stage = PipelineStage(
            tenant_id=tenant_id,
            name=name,
            slug=slug,
            sort_order=sort_order,
            is_won=is_won,
            is_lost=is_lost,
            is_system=False,
        )
        self.db.add(stage)
        self.db.flush()
        return stage


class TagRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[Tag]:
        stmt = select(Tag).where(Tag.tenant_id == tenant_id).order_by(Tag.name)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id_for_tenant(self, tenant_id: uuid.UUID, tag_id: uuid.UUID) -> Tag | None:
        stmt = select(Tag).where(Tag.tenant_id == tenant_id, Tag.id == tag_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, *, tenant_id: uuid.UUID, name: str, color: str) -> Tag:
        tag = Tag(tenant_id=tenant_id, name=name, color=color)
        self.db.add(tag)
        self.db.flush()
        return tag


class LossReasonRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[LossReason]:
        stmt = (
            select(LossReason)
            .where(LossReason.tenant_id == tenant_id)
            .order_by(LossReason.sort_order)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id_for_tenant(self, tenant_id: uuid.UUID, reason_id: uuid.UUID) -> LossReason | None:
        stmt = select(LossReason).where(
            LossReason.tenant_id == tenant_id, LossReason.id == reason_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, *, tenant_id: uuid.UUID, label: str, sort_order: int = 0) -> LossReason:
        reason = LossReason(tenant_id=tenant_id, label=label, sort_order=sort_order)
        self.db.add(reason)
        self.db.flush()
        return reason
