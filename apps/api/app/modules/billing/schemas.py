import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CheckoutSessionRequest(BaseModel):
    plan_key: str = Field(min_length=1, max_length=100)


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class PortalSessionResponse(BaseModel):
    portal_url: str


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    stripe_invoice_id: str
    status: str
    amount_due: float
    amount_paid: float
    currency: str
    hosted_invoice_url: str | None
    invoice_pdf_url: str | None
    period_start: datetime | None
    period_end: datetime | None
    paid_at: datetime | None
    created_at: datetime


class InvoiceListResponse(BaseModel):
    invoices: list[InvoiceResponse]
