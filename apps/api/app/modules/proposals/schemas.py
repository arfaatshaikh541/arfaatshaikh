import uuid
from datetime import date

from pydantic import BaseModel, Field


class LineItemInput(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: float = Field(default=1, gt=0)
    unit_price: float = Field(default=0, ge=0)


class CreateProposalTemplateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = ""
    terms: str = ""
    line_items: list[LineItemInput] = Field(default_factory=list)


class SetTemplateLineItemsRequest(BaseModel):
    line_items: list[LineItemInput]


class CreateProposalRequest(BaseModel):
    lead_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    template_id: uuid.UUID | None = None
    currency: str = Field(default="AED", min_length=3, max_length=3)
    tax_rate: float = Field(default=0, ge=0, le=100)
    terms: str = ""
    valid_until: date | None = None
    line_items: list[LineItemInput] | None = None


class SetProposalLineItemsRequest(BaseModel):
    line_items: list[LineItemInput]


class RejectProposalRequest(BaseModel):
    rejection_reason: str = Field(default="", max_length=500)


class AcceptProposalRequest(BaseModel):
    accepted_by_name: str = Field(min_length=1, max_length=200)
