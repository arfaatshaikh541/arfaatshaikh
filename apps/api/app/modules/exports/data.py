"""Assembles the row-level data for a lead export - the one place that
maps `Lead`/`Business`/`LeadScore`/`LeadOpportunity`/`LeadRecommendation`/
`LeadNote`/`LeadAssignment`/`BusinessSourceRecord`/`EnrichmentEvidence`
onto the architecture's exact 31-column XLSX/CSV schema. Every lookup here
is batched across the whole set of leads being exported - the same "one
query per page, not one query per row" discipline `leads.repositories`'s
own list/detail batching already established in Milestone 6 (an export
can cover far more leads than one page of the Lead Workspace list ever
would). See docs/adr/0015 for the full column-by-column mapping.

Two columns - Opening Hours and Verification Status - are always empty.
Neither is ever collected anywhere in this codebase (no connector field,
no detector, and `LeadVerification` was explicitly deferred - see
docs/adr/0014's Consequences); leaving the column empty rather than
inventing a value is the same "never fabricate a missing field"
discipline `Business.email` already applies elsewhere in this schema.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.businesses import repositories as businesses_repo
from app.modules.enrichment import repositories as enrichment_repo
from app.modules.enrichment.models import EnrichmentEvidence
from app.modules.identity import repositories as identity_repo
from app.modules.leads import repositories as leads_repo

COLUMNS = (
    "Business Name",
    "Category",
    "Subcategory",
    "Country",
    "Region",
    "City",
    "Area",
    "Address",
    "Public Phone",
    "Public Email",
    "Website",
    "Google Maps URL",
    "Rating",
    "Review Count",
    "Opening Hours",
    "WhatsApp URL",
    "Facebook URL",
    "Instagram URL",
    "LinkedIn Company URL",
    "Detected Opportunities",
    "Recommended Service",
    "Lead Score",
    "Score Explanation",
    "Confidence",
    "Source",
    "Source URL",
    "Date Collected",
    "Verification Status",
    "Assigned User",
    "Lead Status",
    "Notes",
)

# Columns rendered as clickable hyperlinks in the XLSX sheet.
HYPERLINK_COLUMNS = frozenset(
    {
        "Website",
        "Google Maps URL",
        "WhatsApp URL",
        "Facebook URL",
        "Instagram URL",
        "LinkedIn Company URL",
        "Source URL",
    }
)


def humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _social_url(social: dict[str, EnrichmentEvidence], detector_type: str) -> str | None:
    evidence = social.get(detector_type)
    if evidence is None:
        return None
    url = evidence.structured_result.get("url")
    return str(url) if url else None


@dataclass
class ExportRow:
    lead_id: uuid.UUID
    business_id: uuid.UUID
    campaign_id: uuid.UUID | None
    values: dict[str, object]


async def build_export_rows(
    session: AsyncSession, *, tenant_id: uuid.UUID, lead_ids: list[uuid.UUID]
) -> tuple[list[ExportRow], list[tuple[uuid.UUID | None, str]]]:
    """Returns (rows, errors). `errors` covers any requested lead id that
    doesn't resolve to a canonical, tenant-owned lead (deleted, or its
    business lost a Milestone 5 merge since the export was requested) -
    each becomes an `ExportError` row rather than failing the export."""
    resolved = await leads_repo.list_leads_for_export(
        session, tenant_id=tenant_id, lead_ids=lead_ids
    )
    resolved_lead_ids = {row.lead.id for row in resolved}
    errors: list[tuple[uuid.UUID | None, str]] = [
        (
            lead_id,
            "Lead not found, or its business was merged into another business since the "
            "export was requested.",
        )
        for lead_id in lead_ids
        if lead_id not in resolved_lead_ids
    ]
    if not resolved:
        return [], errors

    lead_id_list = [row.lead.id for row in resolved]
    business_ids = [row.business.id for row in resolved]

    scores = await leads_repo.get_latest_scores_for_leads(session, lead_id_list)
    opportunities = await leads_repo.get_opportunities_for_leads(session, lead_id_list)
    recommendations = await leads_repo.get_recommendations_for_leads(session, lead_id_list)
    assignments = await leads_repo.get_open_assignments_for_leads(session, lead_id_list)
    notes = await leads_repo.get_latest_notes_for_leads(session, lead_id_list)
    source_records = await businesses_repo.list_latest_source_records_for_businesses(
        session, business_ids
    )
    campaign_ids = await businesses_repo.list_latest_campaign_ids_for_businesses(
        session, business_ids
    )
    social_evidence = await enrichment_repo.list_social_evidence_for_businesses(
        session, business_ids
    )

    assigned_user_ids = [a.assigned_to_user_id for a in assignments.values()]
    users = await identity_repo.list_users_by_ids(session, assigned_user_ids)

    rows: list[ExportRow] = []
    for row in resolved:
        lead = row.lead
        business = row.business
        score = scores.get(lead.id)
        lead_opportunities = opportunities.get(lead.id, [])
        lead_recommendations = recommendations.get(lead.id, [])
        assignment = assignments.get(lead.id)
        assigned_user = users.get(assignment.assigned_to_user_id) if assignment else None
        source_record = source_records.get(business.id)
        social = social_evidence.get(business.id, {})
        lead_notes = notes.get(lead.id, [])

        score_explanation = "; ".join(
            f"{factor.get('label', factor.get('key', ''))}: {factor.get('explanation', '')}"
            for factor in (score.factors if score else [])
        )
        confidence = (
            round(
                sum(float(r.confidence) for r in lead_recommendations) / len(lead_recommendations),
                2,
            )
            if lead_recommendations
            else None
        )
        notes_text = "\n".join(
            f"[{note.created_at.date().isoformat()}] {note.body}" for note in lead_notes
        )

        values: dict[str, object] = {
            "Business Name": business.name,
            "Category": business.category,
            "Subcategory": business.subcategory,
            "Country": business.country,
            "Region": business.region,
            "City": business.city,
            "Area": business.area,
            "Address": business.address,
            "Public Phone": business.phone,
            "Public Email": business.email,
            "Website": business.website,
            "Google Maps URL": business.google_maps_url,
            "Rating": float(business.rating) if business.rating is not None else None,
            "Review Count": business.review_count,
            "Opening Hours": None,
            "WhatsApp URL": _social_url(social, "whatsapp"),
            "Facebook URL": _social_url(social, "social_facebook"),
            "Instagram URL": _social_url(social, "social_instagram"),
            "LinkedIn Company URL": _social_url(social, "social_linkedin"),
            "Detected Opportunities": ", ".join(
                humanize(o.opportunity_type) for o in lead_opportunities
            ),
            "Recommended Service": ", ".join(
                humanize(r.recommendation_type) for r in lead_recommendations
            ),
            "Lead Score": float(score.total_score) if score else None,
            "Score Explanation": score_explanation or None,
            "Confidence": confidence,
            "Source": source_record.source if source_record else None,
            "Source URL": source_record.source_url if source_record else None,
            "Date Collected": source_record.collected_at if source_record else None,
            "Verification Status": None,
            "Assigned User": assigned_user.full_name if assigned_user else None,
            "Lead Status": humanize(lead.status),
            "Notes": notes_text or None,
        }
        rows.append(
            ExportRow(
                lead_id=lead.id,
                business_id=business.id,
                campaign_id=campaign_ids.get(business.id),
                values=values,
            )
        )
    return rows, errors
