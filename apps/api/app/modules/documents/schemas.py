import uuid

from pydantic import BaseModel, Field


class CreateDocumentRequestRequest(BaseModel):
    lead_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    notify: bool = True


class ReviewDocumentRequestRequest(BaseModel):
    notes: str = Field(default="", max_length=2000)
