import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field


class CreateIntegrationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    webhook_url: str = Field(min_length=1, max_length=1000)
    webhook_secret: str = Field(min_length=8, max_length=500)


class UpdateIntegrationRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    webhook_url: str | None = Field(default=None, min_length=1, max_length=1000)
    webhook_secret: str | None = Field(default=None, min_length=8, max_length=500)
    enabled: bool | None = None


class IntegrationResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    webhook_url: str
    enabled: bool
    created_by_user_id: uuid.UUID | None
    created_at: datetime

    @classmethod
    def from_model(cls, integration) -> Self:
        return cls(
            id=integration.id,
            name=integration.name,
            type=integration.type,
            webhook_url=integration.webhook_url,
            enabled=integration.enabled,
            created_by_user_id=integration.created_by_user_id,
            created_at=integration.created_at,
        )


class IntegrationListResponse(BaseModel):
    integrations: list[IntegrationResponse]


class DeliveryResponse(BaseModel):
    id: uuid.UUID
    integration_id: uuid.UUID
    lead_id: uuid.UUID | None
    status: str
    http_status_code: int | None
    response_snippet: str | None
    error_message: str | None
    attempt_count: int
    delivered_at: datetime | None
    created_at: datetime

    @classmethod
    def from_model(cls, delivery) -> Self:
        return cls(
            id=delivery.id,
            integration_id=delivery.integration_id,
            lead_id=delivery.lead_id,
            status=delivery.status,
            http_status_code=delivery.http_status_code,
            response_snippet=delivery.response_snippet,
            error_message=delivery.error_message,
            attempt_count=delivery.attempt_count,
            delivered_at=delivery.delivered_at,
            created_at=delivery.created_at,
        )


class DeliveryListResponse(BaseModel):
    deliveries: list[DeliveryResponse]


class BulkPushRequest(BaseModel):
    lead_ids: list[uuid.UUID] = Field(min_length=1)
