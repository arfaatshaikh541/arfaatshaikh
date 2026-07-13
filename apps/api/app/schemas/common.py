import uuid

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    message: str


class PaginatedResponse(ORMModel):
    total: int
    page: int
    page_size: int


class IDPath(BaseModel):
    id: uuid.UUID
