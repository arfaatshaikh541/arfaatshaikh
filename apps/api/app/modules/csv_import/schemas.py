import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel


class CsvImportPreviewResponse(BaseModel):
    id: uuid.UUID
    status: str
    original_filename: str
    detected_headers: list[str]
    sample_rows: list[dict]
    row_count: int
    mappable_fields: list[str]

    @classmethod
    def from_model(cls, csv_import, *, mappable_fields: list[str]) -> Self:
        return cls(
            id=csv_import.id,
            status=csv_import.status,
            original_filename=csv_import.original_filename,
            detected_headers=csv_import.detected_headers,
            sample_rows=csv_import.sample_rows,
            row_count=csv_import.row_count,
            mappable_fields=mappable_fields,
        )


class StartCsvImportRequest(BaseModel):
    column_mapping: dict[str, str]


class CsvImportResponse(BaseModel):
    id: uuid.UUID
    status: str
    original_filename: str
    row_count: int
    imported_count: int
    error_count: int
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, csv_import) -> Self:
        return cls(
            id=csv_import.id,
            status=csv_import.status,
            original_filename=csv_import.original_filename,
            row_count=csv_import.row_count,
            imported_count=csv_import.imported_count,
            error_count=csv_import.error_count,
            started_at=csv_import.started_at,
            completed_at=csv_import.completed_at,
            error_message=csv_import.error_message,
            created_at=csv_import.created_at,
        )


class CsvImportListResponse(BaseModel):
    imports: list[CsvImportResponse]


class CsvImportErrorResponse(BaseModel):
    row_number: int
    message: str


class CsvImportErrorListResponse(BaseModel):
    errors: list[CsvImportErrorResponse]
