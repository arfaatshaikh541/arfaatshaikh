"""CampaignJob and CampaignTask.

A CampaignJob represents one execution attempt of a campaign's search
against its connector. A CampaignTask is one page of that search - the
unit of idempotent, retryable background work. Pagination cursor state
lives on CampaignJob.current_cursor rather than a separate SearchCursor
table (see docs/adr/0008) since Milestone 2 runs exactly one sequential
cursor stream per job.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPKMixin

CAMPAIGN_JOB_STATUSES = ("queued", "running", "paused", "completed", "failed", "cancelled")
CAMPAIGN_TASK_STATUSES = ("pending", "running", "succeeded", "failed", "cancelled")


class CampaignJob(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "campaign_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_campaign_jobs_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "campaign_id"],
            ["campaigns.tenant_id", "campaigns.id"],
            name="fk_campaign_jobs_tenant_campaign",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False, index=True)
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    current_cursor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CampaignTask(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "campaign_tasks"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_campaign_tasks_idempotency_key"),
        ForeignKeyConstraint(
            ["tenant_id", "campaign_id"],
            ["campaigns.tenant_id", "campaigns.id"],
            name="fk_campaign_tasks_tenant_campaign",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "job_id"],
            ["campaign_jobs.tenant_id", "campaign_jobs.id"],
            name="fk_campaign_tasks_tenant_job",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(150), nullable=False)
    page_number: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    cursor_in: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cursor_out: Mapped[str | None] = mapped_column(String(100), nullable=True)
    businesses_found: Mapped[int] = mapped_column(default=0, nullable=False)
    result_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
