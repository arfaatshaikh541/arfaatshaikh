import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, model_validator


class ExportFiltersRequest(BaseModel):
    """Mirrors `leads.repositories.LeadListFilters` exactly - "export
    everything matching my current Lead Workspace view" replays the same
    filter shape the list endpoint already accepts."""

    status: list[str] | None = None
    assigned_to_user_id: uuid.UUID | None = None
    unassigned_only: bool = False
    tag: str | None = None
    opportunity_type: str | None = None
    category: str | None = None
    city: str | None = None
    country: str | None = None
    area: str | None = None
    min_score: float | None = None
    max_score: float | None = None
    search: str | None = None
    sort_by: str = "created_at"
    sort_dir: str = "desc"


class CreateExportRequest(BaseModel):
    format: str
    lead_ids: list[uuid.UUID] | None = None
    filters: ExportFiltersRequest | None = None

    @model_validator(mode="after")
    def _check_format_and_selection(self) -> Self:
        if self.format not in ("xlsx", "csv"):
            raise ValueError("format must be 'xlsx' or 'csv'.")
        if self.lead_ids is not None and self.filters is not None:
            raise ValueError("Provide either lead_ids or filters, not both.")
        return self


class ExportResponse(BaseModel):
    id: uuid.UUID
    format: str
    status: str
    row_count: int | None
    error_count: int
    file_size_bytes: int | None
    requested_by_user_id: uuid.UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, export) -> Self:
        return cls(
            id=export.id,
            format=export.format,
            status=export.status,
            row_count=export.row_count,
            error_count=export.error_count,
            file_size_bytes=export.file_size_bytes,
            requested_by_user_id=export.requested_by_user_id,
            started_at=export.started_at,
            completed_at=export.completed_at,
            error_message=export.error_message,
            created_at=export.created_at,
        )


class ExportListResponse(BaseModel):
    exports: list[ExportResponse]


class ExportDownloadResponse(BaseModel):
    url: str
    expires_in_seconds: int
    filename: str


class ExportErrorResponse(BaseModel):
    lead_id: uuid.UUID | None
    message: str


class ExportErrorListResponse(BaseModel):
    errors: list[ExportErrorResponse]
