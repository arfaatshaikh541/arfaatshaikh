"""Tests for `app.modules.businesses.dedup` - the deduplication matching
and merge engine (Milestone 5, see docs/adr/0013).

Uses the same raw-session-against-a-real-database pattern as
`test_campaign_engine.py` (a migrator-role engine that bypasses RLS for
setup, `set_tenant_context` for anything that must go through the real
RLS-protected path) - dedup logic is exercised directly against real
Postgres, not mocked, including the false-positive/false-negative
scenarios the architecture explicitly calls for ("test false-positive and
false-negative scenarios").
"""

import uuid
from datetime import UTC, datetime

import pytest
from app.core.db import set_tenant_context
from app.core.exceptions import ConflictError
from app.modules.businesses import dedup
from app.modules.businesses import repositories as businesses_repo
from app.modules.businesses.normalize import normalize_address, normalize_name, normalize_phone
from app.modules.enrichment import repositories as enrichment_repo
from app.modules.tenancy import repositories as tenancy_repo
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.helpers import migrator_asyncpg_url

pytestmark = pytest.mark.asyncio


def _session_factory():
    engine = create_async_engine(migrator_asyncpg_url())
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


async def _make_tenant(session):
    return await tenancy_repo.create_tenant(
        session, name="Dedup Test Co", slug=f"dedup-{uuid.uuid4().hex[:10]}"
    )


async def _discover(session, *, tenant_id, native_id, **fields):
    record = {
        "source": "mock",
        "source_native_id": native_id,
        "source_url": f"https://mock-source.example.com/place/{native_id}",
        "collected_at": datetime.now(UTC).isoformat(),
        "name": fields.pop("name", "Golden Cafe Corner"),
        **fields,
    }
    return await businesses_repo.upsert_business_from_discovery(
        session, tenant_id=tenant_id, campaign_id=None, record=record
    )


# ---------------------------------------------------------------------------
# Normalization (pure functions, no DB)
# ---------------------------------------------------------------------------


async def test_normalize_name_strips_punctuation_and_case():
    assert normalize_name("Joe's Pizza!") == normalize_name("JOES PIZZA")


async def test_normalize_phone_strips_formatting():
    assert normalize_phone("+1 (206) 555-0100") == normalize_phone("1-206-555-0100")


async def test_normalize_phone_different_area_codes_are_not_equal():
    # A "last N digits" comparison would wrongly equate these - normalize
    # is deliberately just digit-stripping, nothing lossier.
    assert normalize_phone("+1-206-555-0100") != normalize_phone("+1-425-555-0100")


async def test_normalize_address_strips_punctuation_and_case():
    assert normalize_address("123 Main St.") == normalize_address("123 MAIN ST")


# ---------------------------------------------------------------------------
# Matching tiers - true positives (each should auto-merge)
# ---------------------------------------------------------------------------


async def test_identifier_match_auto_merges():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)

            first = await _discover(
                session, tenant_id=tenant.id, native_id="place-1", name="Golden Cafe"
            )
            # A second discovery event for the exact same google_place_id,
            # arriving with a different name/native_id (e.g. re-surfaced
            # under a slightly different query) - the identifier tier
            # should still catch it as the same real business.
            first.google_place_id = "gp-shared-1"
            await session.flush()

            second = await _discover(
                session, tenant_id=tenant.id, native_id="place-2", name="Golden Cafe Corner"
            )
            second.google_place_id = "gp-shared-1"
            await session.flush()

            await dedup.process_new_business_for_duplicates(session, second)
            await session.commit()

            refreshed_first = await businesses_repo.get_business_or_raise(session, first.id)
            refreshed_second = await businesses_repo.get_business_or_raise(session, second.id)
            # Exactly one of the two is now the loser.
            merged = {refreshed_first.merged_into_id, refreshed_second.merged_into_id}
            assert len(merged) == 2
            assert None in merged  # the winner has no merged_into_id
    finally:
        await engine.dispose()


async def test_domain_match_auto_merges():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)

            await _discover(
                session,
                tenant_id=tenant.id,
                native_id="d-1",
                name="Blue Diner",
                website="https://www.bluediner.example.com",
            )
            second = await _discover(
                session,
                tenant_id=tenant.id,
                native_id="d-2",
                name="Blue Diner Restaurant",
                website="https://bluediner.example.com/home",
            )

            await dedup.process_new_business_for_duplicates(session, second)
            await session.commit()

            history = await businesses_repo.list_merge_history_for_business(session, second.id)
            assert len(history) == 1
            assert history[0].match_type == "domain"
    finally:
        await engine.dispose()


async def test_phone_match_auto_merges():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)

            await _discover(
                session,
                tenant_id=tenant.id,
                native_id="p-1",
                name="Silver Studio",
                phone="+1-206-555-0100",
            )
            second = await _discover(
                session,
                tenant_id=tenant.id,
                native_id="p-2",
                name="Silver Studio Cafe",
                phone="+1 (206) 555-0100",
            )

            await dedup.process_new_business_for_duplicates(session, second)
            await session.commit()

            history = await businesses_repo.list_merge_history_for_business(session, second.id)
            assert len(history) == 1
            assert history[0].match_type == "phone"
    finally:
        await engine.dispose()


async def test_name_address_exact_match_auto_merges():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)

            await _discover(
                session,
                tenant_id=tenant.id,
                native_id="na-1",
                name="Royal Hub",
                city="Dubai",
                address="12 Marina Street",
            )
            second = await _discover(
                session,
                tenant_id=tenant.id,
                native_id="na-2",
                name="Royal Hub",
                city="Dubai",
                address="12 Marina Street.",
            )

            await dedup.process_new_business_for_duplicates(session, second)
            await session.commit()

            history = await businesses_repo.list_merge_history_for_business(session, second.id)
            assert len(history) == 1
            assert history[0].match_type == "name_address"
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Conservative fuzzy matching - never auto-merges (false-positive guard)
# ---------------------------------------------------------------------------


async def test_fuzzy_name_match_creates_a_candidate_not_a_merge():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)

            await _discover(
                session,
                tenant_id=tenant.id,
                native_id="f-1",
                name="Northern Works Café",
                city="Dubai",
            )
            second = await _discover(
                session,
                tenant_id=tenant.id,
                native_id="f-2",
                name="Northern Works Cafe",
                city="Dubai",
            )

            await dedup.process_new_business_for_duplicates(session, second)
            await session.commit()

            history = await businesses_repo.list_merge_history_for_business(session, second.id)
            assert history == []  # never silently merged

            candidates = await businesses_repo.list_duplicate_candidates(
                session, tenant_id=tenant.id, status="pending"
            )
            assert len(candidates) == 1
            assert candidates[0].match_type == "fuzzy_name"
            assert candidates[0].confidence < dedup.AUTO_MERGE_CONFIDENCE_THRESHOLD
    finally:
        await engine.dispose()


async def test_dissimilar_names_in_the_same_city_produce_no_match():
    """False-negative guard: two genuinely different businesses in the
    same city must not be flagged as duplicates at all."""
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)

            await _discover(
                session,
                tenant_id=tenant.id,
                native_id="x-1",
                name="Golden Cafe Corner",
                city="Dubai",
            )
            second = await _discover(
                session,
                tenant_id=tenant.id,
                native_id="x-2",
                name="Royal Auto Repair",
                city="Dubai",
            )

            await dedup.process_new_business_for_duplicates(session, second)
            await session.commit()

            history = await businesses_repo.list_merge_history_for_business(session, second.id)
            assert history == []
            candidates = await businesses_repo.list_duplicate_candidates_for_business(
                session, second.id
            )
            assert candidates == []
    finally:
        await engine.dispose()


async def test_matching_names_in_different_cities_produce_no_match():
    """False-negative-avoidance's mirror image: matching *is* conservative
    about city, but that means a same-name business in a different city
    correctly does NOT match - the fuzzy/name+address tiers are scoped to
    same-city candidates by design."""
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)

            await _discover(
                session,
                tenant_id=tenant.id,
                native_id="c-1",
                name="Coastal Place",
                city="Dubai",
                address="1 Beach Road",
            )
            second = await _discover(
                session,
                tenant_id=tenant.id,
                native_id="c-2",
                name="Coastal Place",
                city="Abu Dhabi",
                address="1 Beach Road",
            )

            await dedup.process_new_business_for_duplicates(session, second)
            await session.commit()

            history = await businesses_repo.list_merge_history_for_business(session, second.id)
            assert history == []
    finally:
        await engine.dispose()


async def test_duplicate_match_never_crosses_tenants():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant_a = await _make_tenant(session)
            tenant_b = await _make_tenant(session)

            await set_tenant_context(session, tenant_a.id)
            await _discover(
                session,
                tenant_id=tenant_a.id,
                native_id="t-1",
                name="Grand Lounge",
                website="https://www.grandlounge.example.com",
            )
            await session.commit()

            await set_tenant_context(session, tenant_b.id)
            second = await _discover(
                session,
                tenant_id=tenant_b.id,
                native_id="t-2",
                name="Grand Lounge",
                website="https://www.grandlounge.example.com",
            )
            await dedup.process_new_business_for_duplicates(session, second)
            await session.commit()

            history = await businesses_repo.list_merge_history_for_business(session, second.id)
            assert history == []
            refreshed = await businesses_repo.get_business_or_raise(session, second.id)
            assert refreshed.merged_into_id is None
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Merge mechanics: field combination, record reassignment, undo
# ---------------------------------------------------------------------------


async def test_merge_combines_fields_by_confidence_and_preserves_source_records():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)

            winner = await _discover(
                session,
                tenant_id=tenant.id,
                native_id="m-1",
                name="Urban Collective",
                website="https://www.urbancollective.example.com",
                phone=None,
            )
            loser = await _discover(
                session,
                tenant_id=tenant.id,
                native_id="m-2",
                name="Urban Collective Studio",
                website="https://www.urbancollective.example.com",
                phone="+1-206-555-0199",
            )
            await session.flush()

            merge_history = await dedup.merge_businesses(
                session,
                winner_id=winner.id,
                loser_id=loser.id,
                match_type="domain",
                confidence=0.95,
            )
            await session.commit()

            refreshed_winner = await businesses_repo.get_business_or_raise(session, winner.id)
            refreshed_loser = await businesses_repo.get_business_or_raise(session, loser.id)

            # Winner had no phone at all - the loser's (only) phone value
            # fills the gap, since the winner had no competing provenance.
            assert refreshed_winner.phone == "+1-206-555-0199"
            assert refreshed_winner.field_provenance["phone"]["source"] == "mock"
            assert "phone" in merge_history.field_changes
            assert merge_history.field_changes["phone"]["winner_before_value"] is None

            # The loser row still exists (never deleted) and now points
            # at the winner.
            assert refreshed_loser.merged_into_id == winner.id
            source_records = await businesses_repo.get_source_record_by_native_id(
                session, tenant_id=tenant.id, source="mock", source_native_id="m-2"
            )
            assert source_records is not None
            # Reassigned onto the winner, not deleted.
            assert source_records.business_id == winner.id
    finally:
        await engine.dispose()


async def test_merge_reassigns_enrichment_and_evidence():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)

            winner = await _discover(
                session, tenant_id=tenant.id, native_id="e-1", name="Bright Place"
            )
            loser = await _discover(
                session,
                tenant_id=tenant.id,
                native_id="e-2",
                name="Bright Place Two",
                website="https://www.brightplace.example.com",
            )
            winner.canonical_domain = (
                None  # ensure this merge is driven manually, not by domain tier
            )
            await session.flush()

            enrichment = await enrichment_repo.create_enrichment(
                session, tenant_id=tenant.id, business_id=loser.id
            )
            evidence = await enrichment_repo.record_evidence(
                session,
                tenant_id=tenant.id,
                business_id=loser.id,
                enrichment_id=enrichment.id,
                detector_type="contact_email",
                source_url="https://www.brightplace.example.com/contact",
                structured_result={"email": "hello@brightplace.example.com"},
                confidence=0.95,
                collected_at=datetime.now(UTC),
            )
            await session.flush()

            merge_history = await dedup.merge_businesses(
                session,
                winner_id=winner.id,
                loser_id=loser.id,
                match_type="fuzzy_name",
                confidence=0.7,
            )
            await session.commit()

            assert str(enrichment.id) in merge_history.moved_records["enrichments"]
            assert str(evidence.id) in merge_history.moved_records["evidence"]

            refreshed_enrichment = await enrichment_repo.get_enrichment_or_raise(
                session, enrichment.id
            )
            refreshed_evidence_list = await enrichment_repo.list_evidence_for_business(
                session, winner.id
            )
            assert refreshed_enrichment.business_id == winner.id
            assert any(e.id == evidence.id for e in refreshed_evidence_list)
    finally:
        await engine.dispose()


async def test_undo_merge_reverses_field_changes_and_record_reassignment():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)

            winner = await _discover(
                session, tenant_id=tenant.id, native_id="u-1", name="Sunset Hub", phone=None
            )
            loser = await _discover(
                session,
                tenant_id=tenant.id,
                native_id="u-2",
                name="Sunset Hub Two",
                phone="+1-206-555-0177",
            )
            await session.flush()

            merge_history = await dedup.merge_businesses(
                session,
                winner_id=winner.id,
                loser_id=loser.id,
                match_type="fuzzy_name",
                confidence=0.7,
            )
            await session.commit()

            undone = await dedup.undo_merge(session, merge_history_id=merge_history.id)
            await session.commit()

            assert undone.undone_at is not None

            refreshed_winner = await businesses_repo.get_business_or_raise(session, winner.id)
            refreshed_loser = await businesses_repo.get_business_or_raise(session, loser.id)
            assert refreshed_winner.phone is None
            assert "phone" not in refreshed_winner.field_provenance
            assert refreshed_loser.merged_into_id is None

            source_record = await businesses_repo.get_source_record_by_native_id(
                session, tenant_id=tenant.id, source="mock", source_native_id="u-2"
            )
            assert source_record.business_id == loser.id
    finally:
        await engine.dispose()


async def test_undo_merge_twice_raises_conflict():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)

            winner = await _discover(
                session, tenant_id=tenant.id, native_id="uu-1", name="Coastal Hub"
            )
            loser = await _discover(
                session, tenant_id=tenant.id, native_id="uu-2", name="Coastal Hub 2"
            )
            await session.flush()

            merge_history = await dedup.merge_businesses(
                session,
                winner_id=winner.id,
                loser_id=loser.id,
                match_type="fuzzy_name",
                confidence=0.7,
            )
            await session.commit()
            await dedup.undo_merge(session, merge_history_id=merge_history.id)
            await session.commit()

            with pytest.raises(ConflictError):
                await dedup.undo_merge(session, merge_history_id=merge_history.id)
    finally:
        await engine.dispose()


async def test_merging_an_already_merged_business_raises_conflict():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)

            a = await _discover(session, tenant_id=tenant.id, native_id="tri-1", name="Place A")
            b = await _discover(session, tenant_id=tenant.id, native_id="tri-2", name="Place B")
            c = await _discover(session, tenant_id=tenant.id, native_id="tri-3", name="Place C")
            await session.flush()

            await dedup.merge_businesses(
                session, winner_id=a.id, loser_id=b.id, match_type="fuzzy_name", confidence=0.7
            )
            await session.commit()

            with pytest.raises(ConflictError):
                # b is already merged away - cannot merge it again.
                await dedup.merge_businesses(
                    session, winner_id=c.id, loser_id=b.id, match_type="fuzzy_name", confidence=0.7
                )
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Candidate review workflow
# ---------------------------------------------------------------------------


async def test_confirm_candidate_performs_the_merge():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)

            await _discover(
                session,
                tenant_id=tenant.id,
                native_id="cc-1",
                name="Studio Works Place",
                city="Dubai",
            )
            second = await _discover(
                session,
                tenant_id=tenant.id,
                native_id="cc-2",
                name="Studio Works Plac",
                city="Dubai",
            )
            await dedup.process_new_business_for_duplicates(session, second)
            await session.commit()

            candidates = await businesses_repo.list_duplicate_candidates(
                session, tenant_id=tenant.id, status="pending"
            )
            assert len(candidates) == 1
            candidate_id = candidates[0].id

            await dedup.confirm_candidate(session, candidate_id=candidate_id)
            await session.commit()

            refreshed_candidate = await businesses_repo.get_duplicate_candidate_or_raise(
                session, candidate_id
            )
            assert refreshed_candidate.status == "confirmed"
            history = await businesses_repo.list_merge_history_for_business(session, second.id)
            assert len(history) == 1
    finally:
        await engine.dispose()


async def test_reject_candidate_leaves_businesses_distinct_and_is_not_re_proposed():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)

            first = await _discover(
                session,
                tenant_id=tenant.id,
                native_id="rj-1",
                name="Corner Collective",
                city="Dubai",
            )
            second = await _discover(
                session,
                tenant_id=tenant.id,
                native_id="rj-2",
                name="Corner Collectiv",
                city="Dubai",
            )
            await dedup.process_new_business_for_duplicates(session, second)
            await session.commit()

            candidates = await businesses_repo.list_duplicate_candidates(
                session, tenant_id=tenant.id, status="pending"
            )
            assert len(candidates) == 1
            candidate_id = candidates[0].id

            await dedup.reject_candidate(session, candidate_id=candidate_id)
            await session.commit()

            refreshed_first = await businesses_repo.get_business_or_raise(session, first.id)
            refreshed_second = await businesses_repo.get_business_or_raise(session, second.id)
            assert refreshed_first.merged_into_id is None
            assert refreshed_second.merged_into_id is None

            # Re-running the same match must not re-propose a rejected pair.
            await dedup.process_new_business_for_duplicates(session, second)
            await session.commit()
            all_candidates = await businesses_repo.list_duplicate_candidates(
                session, tenant_id=tenant.id, status=None
            )
            assert len(all_candidates) == 1
            assert all_candidates[0].status == "rejected"
    finally:
        await engine.dispose()


async def test_confirming_an_already_reviewed_candidate_raises_conflict():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)

            await _discover(
                session,
                tenant_id=tenant.id,
                native_id="ar-1",
                name="Lounge Corner Spot",
                city="Dubai",
            )
            second = await _discover(
                session,
                tenant_id=tenant.id,
                native_id="ar-2",
                name="Lounge Corner Spott",
                city="Dubai",
            )
            await dedup.process_new_business_for_duplicates(session, second)
            await session.commit()

            candidates = await businesses_repo.list_duplicate_candidates(
                session, tenant_id=tenant.id, status="pending"
            )
            candidate_id = candidates[0].id
            await dedup.reject_candidate(session, candidate_id=candidate_id)
            await session.commit()

            with pytest.raises(ConflictError):
                await dedup.confirm_candidate(session, candidate_id=candidate_id)
    finally:
        await engine.dispose()
