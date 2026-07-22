"""Explainable, versioned lead scoring - opportunity detection,
recommended-service mapping, and the score itself.

**Opportunity detection never invents a problem.** Every opportunity is
either a direct 1:1 read of one `EnrichmentEvidence` row (the detector
already observed it - see `worker.crawler.detectors`) or a direct read of
a `Business` field (`no_website` when `business.website` is `None`,
`low_review_activity` from the business's own real `rating`/
`review_count`) - never a guess. `evidence_reference` on every
`LeadOpportunity` points at exactly what was observed, so a human can
verify it.

**Recommended services are a data-driven rule table**
(`OPPORTUNITY_RECOMMENDATIONS`), not restaurant-specific if/else branches
- the architecture's explicit requirement ("do not hardcode restaurants
into core architecture", "support opportunity rules by industry"). Every
opportunity type here is generic (any business can be missing online
booking, not just restaurants); a future per-industry override would key
off `Business.category` without changing this module's shape.

**The score itself** is the architecture's own worked example, replicated
almost exactly: 7 factors summing to 100, each with a plain-language
explanation built from the real values that produced it and an
`evidence` dict pointing at what was checked. See docs/adr/0013 for the
full reasoning behind each factor's weight and the confidence numbers
used elsewhere in this module - nothing here is an "unexplained
AI-generated number."
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.businesses import repositories as businesses_repo
from app.modules.businesses.models import Business
from app.modules.campaigns import repositories as campaigns_repo
from app.modules.enrichment import repositories as enrichment_repo
from app.modules.enrichment.models import BusinessEnrichment, EnrichmentEvidence
from app.modules.leads import repositories as leads_repo
from app.modules.leads.models import SCORING_ALGORITHM_VERSION, Lead, LeadOpportunity

# Detector types (worker.crawler.detectors / worker.enrichment_tasks) that
# translate directly, 1:1, into an opportunity of the same name - each
# one *is* a real, already-observed EnrichmentEvidence row.
_EVIDENCE_OPPORTUNITY_TYPES = frozenset(
    {
        "website_unavailable",
        "ssl_failure",
        "missing_mobile_viewport",
        "missing_online_booking",
        "missing_online_ordering",
        "missing_whatsapp",
        "missing_contact_form",
        "missing_contact_method",
        "weak_page_metadata",
        "outdated_copyright_year",
    }
)

# opportunity_type -> recommendation_type(s). Generic across every
# category/industry by construction - see module docstring. A
# recommendation type not reachable from any rule here today
# ("crm_implementation") is left in the architecture's vocabulary but
# deliberately unmapped rather than force-fit to an opportunity that
# doesn't actually evidence it.
OPPORTUNITY_RECOMMENDATIONS: dict[str, tuple[str, ...]] = {
    "no_website": ("website_development",),
    "website_unavailable": ("website_development",),
    "ssl_failure": ("website_development",),
    "outdated_copyright_year": ("website_development", "digital_marketing_audit"),
    "missing_mobile_viewport": ("mobile_website_optimisation",),
    "weak_page_metadata": ("digital_marketing_audit",),
    "missing_online_booking": ("booking_automation",),
    "missing_online_ordering": ("online_ordering",),
    "missing_whatsapp": ("whatsapp_automation",),
    "missing_contact_form": ("website_development",),
    "missing_contact_method": ("website_development", "chatbot_implementation"),
    "missing_social_links": ("digital_marketing_audit",),
    "low_review_activity": ("review_management_workflow",),
}


async def _detect_opportunities(
    session: AsyncSession, business: Business, *, now: datetime
) -> tuple[list[dict[str, Any]], BusinessEnrichment | None, list[EnrichmentEvidence]]:
    opportunities: list[dict[str, Any]] = []
    enrichment: BusinessEnrichment | None = None
    evidence_rows: list[EnrichmentEvidence] = []

    if not business.website:
        opportunities.append(
            {
                "opportunity_type": "no_website",
                "confidence": 0.95,
                "evidence_reference": {"business_field": "website", "observed_value": None},
                "detected_at": now,
            }
        )
    else:
        enrichment = await enrichment_repo.get_latest_enrichment_for_business(session, business.id)
        if enrichment is not None and enrichment.status == "completed":
            evidence_rows = await enrichment_repo.list_evidence_for_enrichment(
                session, enrichment.id
            )
            evidence_by_type = {e.detector_type: e for e in evidence_rows}
            for detector_type in _EVIDENCE_OPPORTUNITY_TYPES & evidence_by_type.keys():
                evidence = evidence_by_type[detector_type]
                opportunities.append(
                    {
                        "opportunity_type": detector_type,
                        "confidence": float(evidence.confidence),
                        "evidence_reference": {
                            "evidence_id": str(evidence.id),
                            "source_url": evidence.source_url,
                        },
                        "detected_at": now,
                    }
                )
            if not any(e.detector_type.startswith("social_") for e in evidence_rows):
                opportunities.append(
                    {
                        "opportunity_type": "missing_social_links",
                        "confidence": 0.6,
                        "evidence_reference": {
                            "enrichment_id": str(enrichment.id),
                            "pages_checked": enrichment.pages_crawled,
                        },
                        "detected_at": now,
                    }
                )

    weak_reviews = business.review_count is not None and business.review_count < 20
    weak_rating = business.rating is not None and float(business.rating) < 3.5
    if weak_reviews or weak_rating:
        opportunities.append(
            {
                "opportunity_type": "low_review_activity",
                "confidence": 0.7,
                "evidence_reference": {
                    "business_field": "review_count/rating",
                    "review_count": business.review_count,
                    "rating": float(business.rating) if business.rating is not None else None,
                },
                "detected_at": now,
            }
        )

    return opportunities, enrichment, evidence_rows


def _build_recommendations(
    persisted_opportunities: list[LeadOpportunity], *, now: datetime
) -> list[dict[str, Any]]:
    ids_by_type: dict[str, list[str]] = {}
    confidences_by_type: dict[str, list[float]] = {}
    for opportunity in persisted_opportunities:
        for recommendation_type in OPPORTUNITY_RECOMMENDATIONS.get(
            opportunity.opportunity_type, ()
        ):
            ids_by_type.setdefault(recommendation_type, []).append(str(opportunity.id))
            confidences_by_type.setdefault(recommendation_type, []).append(
                float(opportunity.confidence)
            )

    recommendations = []
    for recommendation_type, opportunity_ids in ids_by_type.items():
        confidences = confidences_by_type[recommendation_type]
        recommendations.append(
            {
                "recommendation_type": recommendation_type,
                "confidence": round(sum(confidences) / len(confidences), 2),
                "supporting_opportunity_ids": opportunity_ids,
                "recommended_at": now,
            }
        )
    return recommendations


def _factor(
    key: str, label: str, score: float, max_score: float, explanation: str, evidence: dict
) -> dict:
    return {
        "key": key,
        "label": label,
        "score": round(max(0.0, min(score, max_score)), 2),
        "max_score": max_score,
        "explanation": explanation,
        "evidence": evidence,
    }


async def _compute_factors(
    session: AsyncSession,
    business: Business,
    *,
    opportunities: list[dict[str, Any]],
    enrichment: BusinessEnrichment | None,
    evidence_rows: list[EnrichmentEvidence],
    now: datetime,
) -> list[dict]:
    factors = []

    campaign_id = await businesses_repo.get_latest_campaign_id_for_business(session, business.id)
    campaign_filter = (
        await campaigns_repo.get_filter_for_campaign(session, campaign_id) if campaign_id else None
    )
    if campaign_filter is None:
        factors.append(
            _factor(
                "category_and_location_match",
                "Category and location match",
                0.0,
                20.0,
                "No originating campaign filter is available for this business to compare against.",
                {"campaign_filter_found": False},
            )
        )
    else:
        category_target = campaign_filter.category or campaign_filter.industry
        category_matched = bool(
            business.category
            and category_target
            and business.category.strip().lower() == category_target.strip().lower()
        )
        category_score = 10.0 if category_matched else 0.0
        location_score = 0.0
        location_notes = []
        if (
            business.country
            and campaign_filter.country.strip().lower() == business.country.strip().lower()
        ):
            location_score += 4.0
            location_notes.append(f"country matches ({business.country})")
        if business.city and campaign_filter.city.strip().lower() == business.city.strip().lower():
            location_score += 3.0
            location_notes.append(f"city matches ({business.city})")
        if campaign_filter.area:
            if (
                business.area
                and campaign_filter.area.strip().lower() == business.area.strip().lower()
            ):
                location_score += 3.0
                location_notes.append(f"area matches ({business.area})")
        else:
            location_score += 3.0  # not requested by the campaign - not held against the lead
        factors.append(
            _factor(
                "category_and_location_match",
                "Category and location match",
                category_score + location_score,
                20.0,
                f"Category {'matches' if category_matched else 'does not match'} the campaign's "
                f"target ({category_target!r}); location: {', '.join(location_notes) or 'no match'}.",
                {
                    "business_category": business.category,
                    "target_category": category_target,
                    "business_location": {
                        "country": business.country,
                        "city": business.city,
                        "area": business.area,
                    },
                },
            )
        )

    status_score = (
        8.0
        if business.business_status == "operational"
        else (4.0 if business.business_status is None else 0.0)
    )
    review_score = 0.0
    if business.rating is not None:
        review_score += min(4.0, round(float(business.rating) / 5 * 4, 2))
    if business.review_count is not None:
        if business.review_count >= 50:
            review_score += 3.0
        elif business.review_count >= 20:
            review_score += 2.0
        elif business.review_count > 0:
            review_score += 1.0
    factors.append(
        _factor(
            "business_status_and_reviews",
            "Business status and review activity",
            status_score + review_score,
            15.0,
            f"Business status is {business.business_status or 'unknown'}; "
            f"rating {business.rating if business.rating is not None else 'unknown'} "
            f"across {business.review_count if business.review_count is not None else 'an unknown number of'} reviews.",
            {
                "business_status": business.business_status,
                "rating": float(business.rating) if business.rating is not None else None,
                "review_count": business.review_count,
            },
        )
    )

    contact_score = (7.0 if business.phone else 0.0) + (8.0 if business.website else 0.0)
    factors.append(
        _factor(
            "public_contact_availability",
            "Public contact availability",
            contact_score,
            15.0,
            f"Public phone {'available' if business.phone else 'not available'}; "
            f"website {'available' if business.website else 'not available'}.",
            {"has_phone": bool(business.phone), "has_website": bool(business.website)},
        )
    )

    opportunity_confidence_sum = sum(o["confidence"] for o in opportunities)
    factors.append(
        _factor(
            "commercial_opportunity",
            "Visible commercial opportunity",
            opportunity_confidence_sum * 4.0,
            20.0,
            f"{len(opportunities)} evidence-based commercial opportunity(ies) detected "
            "- more detected gaps make this a stronger lead to pitch services to, not a weaker one.",
            {"opportunity_types": [o["opportunity_type"] for o in opportunities]},
        )
    )

    has_whatsapp = any(e.detector_type == "whatsapp" for e in evidence_rows)
    factors.append(
        _factor(
            "whatsapp_presence",
            "WhatsApp presence",
            10.0 if has_whatsapp else 8.0,
            10.0,
            f"Public WhatsApp link {'found' if has_whatsapp else 'not found'} on the crawled pages.",
            {"whatsapp_found": has_whatsapp},
        )
    )

    if enrichment is None:
        enrichment_score = 0.0
        enrichment_explanation = "No enrichment run has been completed for this business yet."
    elif enrichment.status != "completed":
        enrichment_score = 2.0
        enrichment_explanation = (
            f"Latest enrichment run did not complete (status: {enrichment.status})."
        )
    elif evidence_rows:
        avg_confidence = sum(float(e.confidence) for e in evidence_rows) / len(evidence_rows)
        enrichment_score = round(min(10.0, avg_confidence * 10), 2)
        enrichment_explanation = (
            f"Enrichment completed with {len(evidence_rows)} findings across "
            f"{enrichment.pages_crawled} pages, average confidence {round(avg_confidence, 2)}."
        )
    else:
        enrichment_score = 5.0
        enrichment_explanation = (
            f"Enrichment completed ({enrichment.pages_crawled} pages checked) but found no signals."
        )
    factors.append(
        _factor(
            "enrichment_confidence",
            "Enrichment confidence",
            enrichment_score,
            10.0,
            enrichment_explanation,
            {"enrichment_status": enrichment.status if enrichment else None},
        )
    )

    reference_time = business.updated_at or business.created_at
    age_days = max(0.0, (now - reference_time).total_seconds() / 86400)
    if age_days <= 7:
        freshness_score = 10.0
    elif age_days >= 90:
        freshness_score = 0.0
    else:
        freshness_score = round(10.0 * (1 - (age_days - 7) / (90 - 7)), 2)
    factors.append(
        _factor(
            "freshness",
            "Data freshness",
            freshness_score,
            10.0,
            f"Business data was last updated {round(age_days, 1)} day(s) ago.",
            {"age_days": round(age_days, 1)},
        )
    )

    return factors


async def score_lead(
    session: AsyncSession, business_id: uuid.UUID
) -> tuple[Lead, dict, list[LeadOpportunity], list[dict]]:
    """Scores one business: detects opportunities, maps them to
    recommendations, computes the versioned factor breakdown, and
    persists all of it (a new `LeadScore` row every call - see
    models.py). Returns `(lead, score_row_as_dict, opportunities,
    recommendation_rows_as_dicts)` for the route layer to serialize."""
    business = await businesses_repo.get_business_or_raise(session, business_id)
    now = datetime.now(UTC)

    opportunities_data, enrichment, evidence_rows = await _detect_opportunities(
        session, business, now=now
    )

    lead = await leads_repo.get_or_create_lead(
        session, tenant_id=business.tenant_id, business_id=business.id
    )

    persisted_opportunities = await leads_repo.replace_opportunities(
        session, tenant_id=business.tenant_id, lead_id=lead.id, opportunities=opportunities_data
    )
    recommendations_data = _build_recommendations(persisted_opportunities, now=now)
    persisted_recommendations = await leads_repo.replace_recommendations(
        session,
        tenant_id=business.tenant_id,
        lead_id=lead.id,
        recommendations=recommendations_data,
    )

    factors = await _compute_factors(
        session,
        business,
        opportunities=opportunities_data,
        enrichment=enrichment,
        evidence_rows=evidence_rows,
        now=now,
    )
    total_score = round(sum(f["score"] for f in factors), 2)
    max_score = sum(f["max_score"] for f in factors)

    score = await leads_repo.create_score(
        session,
        tenant_id=business.tenant_id,
        lead_id=lead.id,
        algorithm_version=SCORING_ALGORITHM_VERSION,
        total_score=total_score,
        max_score=max_score,
        factors=factors,
        calculated_at=now,
    )

    score_dict = {
        "total_score": total_score,
        "max_score": max_score,
        "algorithm_version": SCORING_ALGORITHM_VERSION,
        "factors": factors,
        "calculated_at": now,
        "id": score.id,
    }
    recommendations_out = [
        {
            "id": r.id,
            "recommendation_type": r.recommendation_type,
            "confidence": float(r.confidence),
            "supporting_opportunity_ids": r.supporting_opportunity_ids,
            "recommended_at": r.recommended_at,
        }
        for r in persisted_recommendations
    ]
    return lead, score_dict, persisted_opportunities, recommendations_out


async def score_businesses_for_campaign(
    session: AsyncSession, campaign_id: uuid.UUID
) -> list[tuple[Lead, dict, list[LeadOpportunity], list[dict]]]:
    """Scores every canonical (non-merged-away) business this campaign
    discovered, one at a time through `score_lead` - the same pure
    computation the single-business endpoint uses, no network/crawl
    involved, so a whole campaign's worth of businesses can be scored
    synchronously in one call. Callers commit once after this returns,
    same as a single `score_lead` call - this function itself never
    commits, so a caller scoring many businesses gets one transaction,
    not one per business."""
    businesses = await businesses_repo.list_businesses_for_campaign(session, campaign_id)
    return [await score_lead(session, business.id) for business in businesses]
