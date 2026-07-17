"""Canonical, provider-neutral request/response shapes every connector
speaks in - a connector translates its own provider's native format to
and from these, so campaign orchestration never depends on a specific
provider's field names."""

from dataclasses import asdict, dataclass, field
from typing import Literal

WebsiteRequirement = Literal["any", "required", "missing"]


@dataclass
class SearchQuery:
    industry: str
    country: str
    city: str
    result_limit: int
    category: str | None = None
    subcategory: str | None = None
    region: str | None = None
    area: str | None = None
    radius_km: float | None = None
    min_rating: float | None = None
    min_reviews: int | None = None
    must_have_phone: bool = False
    website_requirement: WebsiteRequirement = "any"
    business_status: str | None = None
    page_size: int = 20
    cursor: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BusinessRecord:
    source: str
    source_native_id: str
    name: str
    collected_at: str  # ISO 8601 timestamp
    category: str | None = None
    address: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None
    area: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    phone: str | None = None
    website: str | None = None
    google_maps_url: str | None = None
    rating: float | None = None
    review_count: int | None = None
    business_status: str | None = None
    source_url: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SearchPage:
    businesses: list[BusinessRecord] = field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False
    page_number: int = 0

    def to_dict(self) -> dict:
        return {
            "businesses": [b.to_dict() for b in self.businesses],
            "next_cursor": self.next_cursor,
            "has_more": self.has_more,
            "page_number": self.page_number,
        }
