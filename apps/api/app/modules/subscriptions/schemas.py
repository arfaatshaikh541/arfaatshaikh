import uuid
from datetime import datetime

from pydantic import BaseModel


class SubscriptionResponse(BaseModel):
    tenant_id: uuid.UUID
    plan_key: str
    plan_name: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    entitlements: dict
