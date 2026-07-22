"""Tests for `app.modules.leads.scoring` - opportunity detection,
recommendation mapping, and the versioned/explainable score itself
(Milestone 5, see docs/adr/0013).

Same raw-session-against-real-Postgres pattern as
`test_campaign_engine.py`/`test_deduplication.py`.
"""

import uuid
from datetime import UTC, datetime

import pytest
from app.core.db import set_tenant_context
from app.modules.businesses import dedup
from app.modules.businesses import repositories as businesses_repo
from app.modules.campaigns import repositories as campaigns_repo
from app.modules.enrichment import repositories as enrichment_repo
from app.modules.leads import repositories as leads_repo
from app.modules.leads import scoring
from app.modules.leads.models import SCORING_ALGORITHM_VERSION
from app.modules.tenancy import repositories as tenancy_repo
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.helpers import migrator_asyncpg_url

pytestmark = pytest.mark.asyncio


def _session_factory():
    engine = create_async_engine(migrator_asyncpg_url())
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


async def _make_tenant(session):
    return await tenancy_repo.create_tenant(
        session, name="Scoring Test Co", slug=f"score-{uuid.uuid4().hex[:10]}"
    )


async def _make_campaign_with_filter(session, tenant_id, **filter_overrides):
    campaign = await campaigns_repo.create_campaign(
        session,
        tenant_id=tenant_id,
        name="Scoring Test Campaign",
        source_key="mock",
        result_limit=10,
        created_by_user_id=None,
    )
    defaults = dict(
        industry="Restaurants",
        category="Restaurants",
        subcategory=None,
        country="United Arab Emirates",
        region=None,
        city="Dubai",
        area="Dubai Marina",
        radius_km=None,
        min_rating=3.5,
        min_reviews=20,
        must_have_phone=True,
        website_requirement="any",
        business_status=None,
    )
    defaults.update(filter_overrides)
    await campaigns_repo.create_filter(
        session, tenant_id=tenant_id, campaign_id=campaign.id, **defaults
    )
    return campaign


async def _discover(session, *, tenant_id, campaign_id, native_id, **fields):
    record = {
        "source": "mock",
        "source_native_id": native_id,
        "source_url": f"https://mock-source.example.com/place/{native_id}",
        "collected_at": datetime.now(UTC).isoformat(),
        "name": fields.pop("name", "Golden Cafe Corner"),
        **fields,
    }
    return await businesses_repo.upsert_business_from_discovery(
        session, tenant_id=tenant_id, campaign_id=campaign_id, record=record
    )


async def test_business_with_no_website_gets_no_website_opportunity():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            campaign = await _make_campaign_with_filter(session, tenant.id)
            business = await _discover(
                session,
                tenant_id=tenant.id,
                campaign_id=campaign.id,
                native_id="nw-1",
                name="Golden Cafe Corner",
                website=None,
            )
            await session.commit()

            lead, score, opportunities, recommendations = await scoring.score_lead(
                session, business.id
            )
            await session.commit()

            assert lead.status == "new"
            assert lead.business_id == business.id
            opportunity_types = {o.opportunity_type for o in opportunities}
            assert "no_website" in opportunity_types

            recommendation_types = {r["recommendation_type"] for r in recommendations}
            assert "website_development" in recommendation_types
    finally:
        await engine.dispose()


async def test_score_never_exceeds_max_and_factors_sum_to_total():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            campaign = await _make_campaign_with_filter(session, tenant.id)
            business = await _discover(
                session,
                tenant_id=tenant.id,
                campaign_id=campaign.id,
                native_id="fs-1",
                name="Golden Cafe Corner",
                category="Restaurants",
                country="United Arab Emirates",
                city="Dubai",
                area="Dubai Marina",
                phone="+1-206-555-0100",
                website="https://www.goldencafecorner.example.com",
                rating=4.8,
                review_count=120,
                business_status="operational",
            )
            await session.commit()

            _lead, score, _opportunities, _recommendations = await scoring.score_lead(
                session, business.id
            )
            await session.commit()

            assert score["max_score"] == 100.0
            assert 0.0 <= score["total_score"] <= 100.0
            assert score["algorithm_version"] == SCORING_ALGORITHM_VERSION
            factor_sum = round(sum(f["score"] for f in score["factors"]), 2)
            assert factor_sum == score["total_score"]
            for factor in score["factors"]:
                assert 0.0 <= factor["score"] <= factor["max_score"]
    finally:
        await engine.dispose()


async def test_category_and_location_match_scores_full_when_everything_matches():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            campaign = await _make_campaign_with_filter(
                session,
                tenant.id,
                category="Restaurants",
                country="United Arab Emirates",
                city="Dubai",
                area="Dubai Marina",
            )
            business = await _discover(
                session,
                tenant_id=tenant.id,
                campaign_id=campaign.id,
                native_id="cl-1",
                name="Golden Cafe Corner",
                category="Restaurants",
                country="United Arab Emirates",
                city="Dubai",
                area="Dubai Marina",
            )
            await session.commit()

            _lead, score, _opportunities, _recommendations = await scoring.score_lead(
                session, business.id
            )
            await session.commit()

            factor = next(f for f in score["factors"] if f["key"] == "category_and_location_match")
            assert factor["score"] == factor["max_score"] == 20.0
    finally:
        await engine.dispose()


async def test_category_and_location_match_scores_zero_without_a_campaign_filter():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            business = await _discover(
                session,
                tenant_id=tenant.id,
                campaign_id=None,
                native_id="nc-1",
                name="Golden Cafe Corner",
            )
            await session.commit()

            _lead, score, _opportunities, _recommendations = await scoring.score_lead(
                session, business.id
            )
            await session.commit()

            factor = next(f for f in score["factors"] if f["key"] == "category_and_location_match")
            assert factor["score"] == 0.0
            assert factor["evidence"]["campaign_filter_found"] is False
    finally:
        await engine.dispose()


async def test_missing_signals_from_completed_enrichment_become_opportunities():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            campaign = await _make_campaign_with_filter(session, tenant.id)
            business = await _discover(
                session,
                tenant_id=tenant.id,
                campaign_id=campaign.id,
                native_id="ev-1",
                name="Golden Cafe Corner",
                website="https://www.goldencafecorner.example.com",
                phone="+1-206-555-0100",
            )
            enrichment = await enrichment_repo.create_enrichment(
                session, tenant_id=tenant.id, business_id=business.id
            )
            enrichment.status = "completed"
            enrichment.pages_crawled = 3
            now = datetime.now(UTC)
            await enrichment_repo.record_evidence(
                session,
                tenant_id=tenant.id,
                business_id=business.id,
                enrichment_id=enrichment.id,
                detector_type="missing_online_booking",
                source_url="https://www.goldencafecorner.example.com/",
                structured_result={"pages_checked": 3},
                confidence=0.6,
                collected_at=now,
            )
            await enrichment_repo.record_evidence(
                session,
                tenant_id=tenant.id,
                business_id=business.id,
                enrichment_id=enrichment.id,
                detector_type="missing_whatsapp",
                source_url="https://www.goldencafecorner.example.com/",
                structured_result={"pages_checked": 3},
                confidence=0.6,
                collected_at=now,
            )
            await enrichment_repo.record_evidence(
                session,
                tenant_id=tenant.id,
                business_id=business.id,
                enrichment_id=enrichment.id,
                detector_type="contact_email",
                source_url="https://www.goldencafecorner.example.com/",
                structured_result={"email": "hi@goldencafecorner.example.com"},
                confidence=0.95,
                collected_at=now,
            )
            await session.commit()

            lead, score, opportunities, recommendations = await scoring.score_lead(
                session, business.id
            )
            await session.commit()

            opportunity_types = {o.opportunity_type for o in opportunities}
            assert "missing_online_booking" in opportunity_types
            assert "missing_whatsapp" in opportunity_types
            # No online-booking/WhatsApp evidence rows were EVER found
            # (positive presence, not absence) - so the missing_social_links
            # business-level check also fires (no social_* evidence rows
            # present at all).
            assert "missing_social_links" in opportunity_types
            # contact_email is a positive-presence signal, not a problem -
            # must never itself become an "opportunity".
            assert "contact_email" not in opportunity_types

            recommendation_types = {r["recommendation_type"] for r in recommendations}
            assert "booking_automation" in recommendation_types
            assert "whatsapp_automation" in recommendation_types

            whatsapp_factor = next(f for f in score["factors"] if f["key"] == "whatsapp_presence")
            assert whatsapp_factor["score"] == 8.0  # missing - small deduction, not zero

            enrichment_factor = next(
                f for f in score["factors"] if f["key"] == "enrichment_confidence"
            )
            assert enrichment_factor["score"] > 0.0

            _ = lead
    finally:
        await engine.dispose()


async def test_low_review_activity_opportunity_is_evidence_based():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            campaign = await _make_campaign_with_filter(session, tenant.id)
            business = await _discover(
                session,
                tenant_id=tenant.id,
                campaign_id=campaign.id,
                native_id="lr-1",
                name="Golden Cafe Corner",
                review_count=3,
                rating=3.0,
            )
            await session.commit()

            _lead, _score, opportunities, recommendations = await scoring.score_lead(
                session, business.id
            )
            await session.commit()

            opportunity = next(
                o for o in opportunities if o.opportunity_type == "low_review_activity"
            )
            assert opportunity.evidence_reference["review_count"] == 3
            assert opportunity.evidence_reference["rating"] == 3.0

            recommendation_types = {r["recommendation_type"] for r in recommendations}
            assert "review_management_workflow" in recommendation_types
    finally:
        await engine.dispose()


async def test_rescoring_reuses_the_same_lead_and_appends_score_history():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            campaign = await _make_campaign_with_filter(session, tenant.id)
            business = await _discover(
                session,
                tenant_id=tenant.id,
                campaign_id=campaign.id,
                native_id="rs-1",
                name="Golden Cafe Corner",
                website=None,
            )
            await session.commit()

            first_lead, _first_score, _o, _r = await scoring.score_lead(session, business.id)
            await session.commit()

            second_lead, _second_score, _o2, _r2 = await scoring.score_lead(session, business.id)
            await session.commit()

            assert first_lead.id == second_lead.id  # not a duplicate Lead

            scores = await leads_repo.list_scores_for_lead(session, first_lead.id)
            assert len(scores) == 2  # append-only history, not overwritten
    finally:
        await engine.dispose()


async def test_rescoring_replaces_stale_opportunities_not_accumulates_them():
    """An opportunity no longer detected (the business added a website
    since the last score) must stop being listed - `replace_opportunities`
    reflects current state, it doesn't just keep appending."""
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            campaign = await _make_campaign_with_filter(session, tenant.id)
            business = await _discover(
                session,
                tenant_id=tenant.id,
                campaign_id=campaign.id,
                native_id="stale-1",
                name="Golden Cafe Corner",
                website=None,
            )
            await session.commit()

            lead, _score, first_opportunities, _r = await scoring.score_lead(session, business.id)
            await session.commit()
            assert any(o.opportunity_type == "no_website" for o in first_opportunities)

            business.website = "https://www.goldencafecorner.example.com"
            await session.flush()
            await session.commit()

            _lead2, _score2, second_opportunities, _r2 = await scoring.score_lead(
                session, business.id
            )
            await session.commit()

            assert not any(o.opportunity_type == "no_website" for o in second_opportunities)
            all_opportunities = await leads_repo.list_opportunities_for_lead(session, lead.id)
            assert not any(o.opportunity_type == "no_website" for o in all_opportunities)
    finally:
        await engine.dispose()


async def test_recommendation_confidence_is_averaged_across_supporting_opportunities():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            campaign = await _make_campaign_with_filter(session, tenant.id)
            business = await _discover(
                session,
                tenant_id=tenant.id,
                campaign_id=campaign.id,
                native_id="rc-1",
                name="Golden Cafe Corner",
                website="https://www.goldencafecorner.example.com",
            )
            enrichment = await enrichment_repo.create_enrichment(
                session, tenant_id=tenant.id, business_id=business.id
            )
            enrichment.status = "completed"
            enrichment.pages_crawled = 2
            now = datetime.now(UTC)
            await enrichment_repo.record_evidence(
                session,
                tenant_id=tenant.id,
                business_id=business.id,
                enrichment_id=enrichment.id,
                detector_type="missing_contact_form",
                source_url="https://www.goldencafecorner.example.com/",
                structured_result={},
                confidence=0.7,
                collected_at=now,
            )
            await session.commit()

            _lead, _score, opportunities, recommendations = await scoring.score_lead(
                session, business.id
            )
            await session.commit()

            # website_development is reachable from both missing_contact_form
            # AND (potentially) other opportunities this business triggers -
            # its confidence must be the average of whichever opportunities
            # actually contributed to it, not a hardcoded constant.
            website_dev = next(
                r for r in recommendations if r["recommendation_type"] == "website_development"
            )
            contributing = [
                o for o in opportunities if str(o.id) in website_dev["supporting_opportunity_ids"]
            ]
            assert contributing
            expected_confidence = round(
                sum(float(o.confidence) for o in contributing) / len(contributing), 2
            )
            assert website_dev["confidence"] == expected_confidence
    finally:
        await engine.dispose()


async def test_score_businesses_for_campaign_scores_every_canonical_business():
    """`scoring.score_businesses_for_campaign` (Milestone 19) - the bulk
    "score all businesses from this campaign" action - closing the known
    limitation that scoring was manual/per-business only."""
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            campaign = await _make_campaign_with_filter(session, tenant.id)
            businesses = [
                await _discover(
                    session,
                    tenant_id=tenant.id,
                    campaign_id=campaign.id,
                    native_id=f"bulk-{i}",
                    name=f"Bulk Score Business {i}",
                )
                for i in range(3)
            ]
            await session.commit()

            results = await scoring.score_businesses_for_campaign(session, campaign.id)
            await session.commit()

            assert len(results) == 3
            scored_business_ids = {lead.business_id for lead, _score, _o, _r in results}
            assert scored_business_ids == {b.id for b in businesses}
            for lead, score, _opportunities, _recommendations in results:
                assert lead.status == "new"
                assert score["algorithm_version"] == SCORING_ALGORITHM_VERSION

            # Every business now has exactly one Lead, findable independently.
            for business in businesses:
                lead = await leads_repo.get_lead_for_business(session, business.id)
                assert lead is not None
    finally:
        await engine.dispose()


async def test_score_businesses_for_campaign_excludes_merged_away_businesses():
    """A business that lost a Milestone 5 dedup merge (`merged_into_id`
    set) must not be scored a second time under its own id - only the
    canonical winner should appear, matching
    `businesses_repo.list_businesses_for_campaign`'s own "canonical only"
    contract (already relied on by `GET /campaigns/{id}/businesses`)."""
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            campaign = await _make_campaign_with_filter(session, tenant.id)
            winner = await _discover(
                session,
                tenant_id=tenant.id,
                campaign_id=campaign.id,
                native_id="merge-winner",
                name="Merge Winner Cafe",
            )
            loser = await _discover(
                session,
                tenant_id=tenant.id,
                campaign_id=campaign.id,
                native_id="merge-loser",
                name="Merge Loser Cafe",
            )
            await session.commit()

            await dedup.merge_businesses(
                session,
                winner_id=winner.id,
                loser_id=loser.id,
                match_type="domain",
                confidence=0.95,
            )
            await session.commit()

            results = await scoring.score_businesses_for_campaign(session, campaign.id)
            await session.commit()

            assert len(results) == 1
            (lead, _score, _o, _r) = results[0]
            assert lead.business_id == winner.id
    finally:
        await engine.dispose()
