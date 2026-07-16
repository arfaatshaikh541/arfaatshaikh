from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class BackupJobSummary(BaseModel):
    asset_id: uuid.UUID
    job_name: str
    last_run_status: str | None
    last_run_at: datetime | None
    immutable: bool | None
    is_stale: bool
    score: int


class ResilienceSummaryRead(BaseModel):
    recovery_confidence_score: int | None
    backup_job_total: int
    backup_jobs_immutable: int
    backup_jobs_stale: int
    backup_jobs_failed: int
    jobs: list[BackupJobSummary]
