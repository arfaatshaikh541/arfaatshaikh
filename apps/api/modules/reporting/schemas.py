from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ComplianceFrameworkSummary(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    score: int


class ExecutiveSummaryRead(BaseModel):
    generated_at: datetime
    asset_total: int
    security_score: int
    open_findings_total: int
    open_findings_by_severity: dict[str, int]
    open_incidents_total: int
    open_incidents_by_severity: dict[str, int]
    recovery_confidence_score: int | None
    backup_job_total: int
    compliance_overall_score: int | None
    compliance_frameworks: list[ComplianceFrameworkSummary]
