import uuid
from datetime import datetime

from pydantic import BaseModel


class EnrichmentResponse(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    status: str
    pages_crawled: int
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None


class EvidenceResponse(BaseModel):
    id: uuid.UUID
    detector_type: str
    source_url: str
    structured_result: dict
    confidence: float
    supporting_snippet: str | None
    collected_at: datetime
