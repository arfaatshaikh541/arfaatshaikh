"""Builds the JSON payload delivered to an `Integration`'s webhook for
one lead - real data read through the same repository functions the
Lead Workspace detail page (`GET /leads/{id}`) already uses, never a
re-derivation. `_json_safe` converts UUIDs/Decimals/datetimes to
JSON-native types once, at the boundary, rather than scattering
`str(...)`/`float(...)` calls through the payload construction itself.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.businesses import repositories as businesses_repo
from app.modules.identity import repositories as identity_repo
from app.modules.leads import repositories as leads_repo
from app.modules.leads.models import Lead


def _json_safe(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


async def build_lead_payload(session: AsyncSession, lead: Lead) -> dict:
    business = await businesses_repo.get_business_or_raise(session, lead.business_id)
    score = await leads_repo.get_latest_score_for_lead(session, lead.id)
    opportunities = await leads_repo.list_opportunities_for_lead(session, lead.id)
    recommendations = await leads_repo.list_recommendations_for_lead(session, lead.id)
    tags = await leads_repo.list_tags(session, lead.id)
    notes = await leads_repo.list_notes(session, lead.id)

    assigned_user = None
    if lead.assigned_to_user_id is not None:
        user = await identity_repo.get_user_by_id(session, lead.assigned_to_user_id)
        if user is not None:
            assigned_user = {"id": user.id, "full_name": user.full_name, "email": user.email}

    payload = {
        "event": "lead.pushed",
        "lead": {
            "id": lead.id,
            "status": lead.status,
            "created_at": lead.created_at,
            "assigned_to": assigned_user,
            "business": {
                "id": business.id,
                "name": business.name,
                "category": business.category,
                "subcategory": business.subcategory,
                "country": business.country,
                "region": business.region,
                "city": business.city,
                "area": business.area,
                "address": business.address,
                "phone": business.phone,
                "email": business.email,
                "website": business.website,
                "google_maps_url": business.google_maps_url,
                "rating": business.rating,
                "review_count": business.review_count,
            },
            "score": (
                {
                    "total_score": score.total_score,
                    "max_score": score.max_score,
                    "algorithm_version": score.algorithm_version,
                    "factors": score.factors,
                    "calculated_at": score.calculated_at,
                }
                if score
                else None
            ),
            "opportunities": [
                {
                    "opportunity_type": o.opportunity_type,
                    "confidence": o.confidence,
                    "evidence_reference": o.evidence_reference,
                }
                for o in opportunities
            ],
            "recommendations": [
                {"recommendation_type": r.recommendation_type, "confidence": r.confidence}
                for r in recommendations
            ],
            "tags": tags,
            "notes": [{"body": n.body, "created_at": n.created_at} for n in notes],
        },
    }
    return _json_safe(payload)
