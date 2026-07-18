import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel


class BusinessResponse(BaseModel):
    id: uuid.UUID
    name: str
    category: str | None
    subcategory: str | None
    address: str | None
    country: str | None
    region: str | None
    city: str | None
    area: str | None
    latitude: float | None
    longitude: float | None
    phone: str | None
    email: str | None
    website: str | None
    canonical_domain: str | None
    google_place_id: str | None
    google_maps_url: str | None
    rating: float | None
    review_count: int | None
    business_status: str | None
    field_provenance: dict
    created_at: datetime

    @classmethod
    def from_model(cls, business) -> Self:
        return cls(
            id=business.id,
            name=business.name,
            category=business.category,
            subcategory=business.subcategory,
            address=business.address,
            country=business.country,
            region=business.region,
            city=business.city,
            area=business.area,
            latitude=float(business.latitude) if business.latitude is not None else None,
            longitude=float(business.longitude) if business.longitude is not None else None,
            phone=business.phone,
            email=business.email,
            website=business.website,
            canonical_domain=business.canonical_domain,
            google_place_id=business.google_place_id,
            google_maps_url=business.google_maps_url,
            rating=float(business.rating) if business.rating is not None else None,
            review_count=business.review_count,
            business_status=business.business_status,
            field_provenance=business.field_provenance,
            created_at=business.created_at,
        )
