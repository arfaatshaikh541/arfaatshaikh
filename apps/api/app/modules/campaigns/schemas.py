import uuid
from datetime import datetime

from pydantic import BaseModel, Field

WEBSITE_REQUIREMENTS = ("any", "required", "missing")


class CreateCampaignRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_key: str = Field(default="mock", max_length=50)
    result_limit: int = Field(ge=1, le=5000)
    industry: str = Field(min_length=1, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    subcategory: str | None = Field(default=None, max_length=100)
    country: str = Field(min_length=1, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    area: str | None = Field(default=None, max_length=100)
    radius_km: float | None = Field(default=None, ge=0)
    min_rating: float | None = Field(default=None, ge=0, le=5)
    min_reviews: int | None = Field(default=None, ge=0)
    must_have_phone: bool = False
    website_requirement: str = Field(default="any")
    business_status: str | None = Field(default=None, max_length=50)


class CampaignFilterResponse(BaseModel):
    industry: str
    category: str | None
    subcategory: str | None
    country: str
    region: str | None
    city: str
    area: str | None
    radius_km: float | None
    min_rating: float | None
    min_reviews: int | None
    must_have_phone: bool
    website_requirement: str
    business_status: str | None


class CampaignResponse(BaseModel):
    id: uuid.UUID
    name: str
    source_key: str
    status: str
    result_limit: int
    created_at: datetime


class CampaignDetailResponse(CampaignResponse):
    filter: CampaignFilterResponse
    estimated_credits: float | None
    estimated_results: int | None


class EstimateResponse(BaseModel):
    campaign_id: uuid.UUID
    estimated_credits: float
    estimated_results: int
    calculated_at: datetime
    available_balance: float


class ProgressResponse(BaseModel):
    campaign_id: uuid.UUID
    status: str
    job_status: str | None
    total_tasks: int
    succeeded_tasks: int
    failed_tasks: int
    pending_tasks: int
    businesses_found: int


class CampaignEventResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    from_status: str | None
    to_status: str | None
    message: str | None
    created_at: datetime


class CampaignErrorResponse(BaseModel):
    id: uuid.UUID
    error_type: str
    message: str
    created_at: datetime
