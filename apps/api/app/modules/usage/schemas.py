import uuid
from datetime import datetime

from pydantic import BaseModel


class WalletBalanceResponse(BaseModel):
    tenant_id: uuid.UUID
    balance: float
    available: float


class CreditTransactionResponse(BaseModel):
    id: uuid.UUID
    amount: float
    type: str
    reference: str | None
    created_at: datetime
