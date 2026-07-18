"""Tests for the Lead Workspace (Milestone 6): the paginated/sorted/
filtered lead list, status changes + history, assignment + history,
notes, tags, bulk actions, saved views, and the Milestone 5 `dedup.
merge_businesses` extension that carries a `Lead` along with its
`Business` on merge.

Same raw-session-against-real-Postgres pattern as
`test_deduplication.py`/`test_lead_scoring.py`.
"""

import uuid
from datetime import UTC, datetime

import pytest
from app.core.db import set_tenant_context
from app.core.exceptions import ConflictError, PermissionDeniedError, ValidationAppError
from app.modules.businesses import dedup
from app.modules.businesses import repositories as businesses_repo
from app.modules.identity.models import User
from app.modules.leads import repositories as leads_repo
from app.modules.leads import scoring
from app.modules.leads import services as leads_services
from app.modules.leads.repositories import LeadListFilters
from app.modules.tenancy import repositories as tenancy_repo
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.helpers import migrator_asyncpg_url

pytestmark = pytest.mark.asyncio


def _session_factory():
    engine = create_async_engine(migrator_asyncpg_url())
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


async def _make_tenant(session):
    return await tenancy_repo.create_tenant(
        session, name="Workspace Test Co", slug=f"lw-{uuid.uuid4().hex[:10]}"
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


async def _make_user(session, *, email: str) -> User:
    user = User(email=email, password_hash="x", full_name="Test User", email_verified=True)
    session.add(user)
    await session.flush()
    return user


async def _make_lead(session, *, tenant_id, native_id, **fields):
    business = await _discover(session, tenant_id=tenant_id, native_id=native_id, **fields)
    lead, _score, _o, _r = await scoring.score_lead(session, business.id)
    return lead, business


# ---------------------------------------------------------------------------
# List: pagination, sorting, filtering
# ---------------------------------------------------------------------------


async def test_list_leads_paginates():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            for i in range(5):
                await _make_lead(
                    session, tenant_id=tenant.id, native_id=f"pg-{i}", name=f"Business {i}"
                )
            await session.commit()

            page1, total = await leads_repo.list_leads(
                session, tenant_id=tenant.id, filters=LeadListFilters(), page=1, page_size=2
            )
            page2, _total2 = await leads_repo.list_leads(
                session, tenant_id=tenant.id, filters=LeadListFilters(), page=2, page_size=2
            )
            assert total == 5
            assert len(page1) == 2
            assert len(page2) == 2
            assert {r.lead.id for r in page1}.isdisjoint({r.lead.id for r in page2})
    finally:
        await engine.dispose()


async def test_list_leads_sorts_by_name():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            await _make_lead(session, tenant_id=tenant.id, native_id="s-1", name="Zebra Diner")
            await _make_lead(session, tenant_id=tenant.id, native_id="s-2", name="Alpha Diner")
            await session.commit()

            rows, _total = await leads_repo.list_leads(
                session,
                tenant_id=tenant.id,
                filters=LeadListFilters(),
                sort_by="name",
                sort_dir="asc",
            )
            assert [r.business.name for r in rows] == ["Alpha Diner", "Zebra Diner"]
    finally:
        await engine.dispose()


async def test_list_leads_filters_by_status():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead_a, _ = await _make_lead(session, tenant_id=tenant.id, native_id="f-1", name="A")
            await _make_lead(session, tenant_id=tenant.id, native_id="f-2", name="B")
            await session.commit()

            await leads_services.change_status(
                session, lead_id=lead_a.id, to_status="qualified", actor_user_id=None
            )
            await session.commit()

            rows, total = await leads_repo.list_leads(
                session, tenant_id=tenant.id, filters=LeadListFilters(statuses=["qualified"])
            )
            assert total == 1
            assert rows[0].lead.id == lead_a.id
    finally:
        await engine.dispose()


async def test_list_leads_filters_by_tag_and_score_range():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead_a, _ = await _make_lead(session, tenant_id=tenant.id, native_id="t-1", name="A")
            lead_b, _ = await _make_lead(session, tenant_id=tenant.id, native_id="t-2", name="B")
            await session.commit()
            await leads_services.add_tag(session, lead_id=lead_a.id, tag="hot", actor_user_id=None)
            await session.commit()

            rows, total = await leads_repo.list_leads(
                session, tenant_id=tenant.id, filters=LeadListFilters(tag="hot")
            )
            assert total == 1
            assert rows[0].lead.id == lead_a.id

            # min_score=0 should include everyone (every lead scores >= 0);
            # an absurdly high min_score should exclude everyone.
            _rows_all, total_all = await leads_repo.list_leads(
                session, tenant_id=tenant.id, filters=LeadListFilters(min_score=0.0)
            )
            assert total_all == 2
            _rows_none, total_none = await leads_repo.list_leads(
                session, tenant_id=tenant.id, filters=LeadListFilters(min_score=999.0)
            )
            assert total_none == 0
            _ = lead_b
    finally:
        await engine.dispose()


async def test_list_leads_excludes_leads_whose_business_was_merged_away():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            winner_lead, winner_business = await _make_lead(
                session, tenant_id=tenant.id, native_id="m-1", name="Merge Target"
            )
            _loser_lead, loser_business = await _make_lead(
                session, tenant_id=tenant.id, native_id="m-2", name="Merge Source"
            )
            await session.commit()

            await dedup.merge_businesses(
                session,
                winner_id=winner_business.id,
                loser_id=loser_business.id,
                match_type="fuzzy_name",
                confidence=0.7,
            )
            await session.commit()

            rows, total = await leads_repo.list_leads(
                session, tenant_id=tenant.id, filters=LeadListFilters()
            )
            # Both leads existed before the merge; only the winner's
            # canonical business remains listed.
            assert total == 1
            assert rows[0].lead.id == winner_lead.id
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Status changes
# ---------------------------------------------------------------------------


async def test_change_status_records_history():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead, _business = await _make_lead(session, tenant_id=tenant.id, native_id="cs-1")
            await session.commit()

            await leads_services.change_status(
                session, lead_id=lead.id, to_status="reviewed", actor_user_id=None
            )
            await session.commit()

            refreshed = await leads_repo.get_lead_or_raise(session, lead.id)
            assert refreshed.status == "reviewed"
            history = await leads_repo.list_status_history(session, lead.id)
            assert len(history) == 1
            assert history[0].from_status == "new"
            assert history[0].to_status == "reviewed"
    finally:
        await engine.dispose()


async def test_change_status_to_same_status_is_a_noop():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead, _business = await _make_lead(session, tenant_id=tenant.id, native_id="cs-2")
            await session.commit()

            await leads_services.change_status(
                session, lead_id=lead.id, to_status="new", actor_user_id=None
            )
            await session.commit()
            history = await leads_repo.list_status_history(session, lead.id)
            assert history == []
    finally:
        await engine.dispose()


async def test_change_status_rejects_invalid_value():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead, _business = await _make_lead(session, tenant_id=tenant.id, native_id="cs-3")
            await session.commit()

            with pytest.raises(ValidationAppError):
                await leads_services.change_status(
                    session, lead_id=lead.id, to_status="not_a_real_status", actor_user_id=None
                )
    finally:
        await engine.dispose()


async def test_status_can_move_non_linearly_with_no_transition_graph():
    """No state machine (docs/adr/0014) - a lead can go straight from
    "new" to "do_not_contact", or back from "contacted" to "reviewed"."""
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead, _business = await _make_lead(session, tenant_id=tenant.id, native_id="cs-4")
            await session.commit()

            await leads_services.change_status(
                session, lead_id=lead.id, to_status="contacted", actor_user_id=None
            )
            await leads_services.change_status(
                session, lead_id=lead.id, to_status="reviewed", actor_user_id=None
            )
            await session.commit()
            refreshed = await leads_repo.get_lead_or_raise(session, lead.id)
            assert refreshed.status == "reviewed"
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------


async def test_assign_and_unassign_records_history():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead, _business = await _make_lead(session, tenant_id=tenant.id, native_id="as-1")
            await session.commit()
            fake_user = await _make_user(session, email="assignee@example.com")
            await session.commit()
            fake_user_id = fake_user.id

            await leads_services.assign_lead(
                session, lead_id=lead.id, assigned_to_user_id=fake_user_id, actor_user_id=None
            )
            await session.commit()
            refreshed = await leads_repo.get_lead_or_raise(session, lead.id)
            assert refreshed.assigned_to_user_id == fake_user_id
            history = await leads_repo.list_assignment_history(session, lead.id)
            assert len(history) == 1
            assert history[0].unassigned_at is None

            await leads_services.unassign_lead(session, lead_id=lead.id, actor_user_id=None)
            await session.commit()
            refreshed = await leads_repo.get_lead_or_raise(session, lead.id)
            assert refreshed.assigned_to_user_id is None
            history = await leads_repo.list_assignment_history(session, lead.id)
            assert history[0].unassigned_at is not None
    finally:
        await engine.dispose()


async def test_reassigning_to_a_different_user_closes_the_open_assignment():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead, _business = await _make_lead(session, tenant_id=tenant.id, native_id="as-2")
            await session.commit()
            user_a_obj = await _make_user(session, email="usera@example.com")
            user_b_obj = await _make_user(session, email="userb@example.com")
            await session.commit()
            user_a, user_b = user_a_obj.id, user_b_obj.id

            await leads_services.assign_lead(
                session, lead_id=lead.id, assigned_to_user_id=user_a, actor_user_id=None
            )
            await leads_services.assign_lead(
                session, lead_id=lead.id, assigned_to_user_id=user_b, actor_user_id=None
            )
            await session.commit()

            refreshed = await leads_repo.get_lead_or_raise(session, lead.id)
            assert refreshed.assigned_to_user_id == user_b
            history = await leads_repo.list_assignment_history(session, lead.id)
            assert len(history) == 2
            open_entries = [h for h in history if h.unassigned_at is None]
            assert len(open_entries) == 1
            assert open_entries[0].assigned_to_user_id == user_b
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Notes and tags
# ---------------------------------------------------------------------------


async def test_add_note_and_list():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead, _business = await _make_lead(session, tenant_id=tenant.id, native_id="n-1")
            await session.commit()

            await leads_services.add_note(
                session, lead_id=lead.id, author_user_id=None, body="Called, left voicemail."
            )
            await session.commit()
            notes = await leads_repo.list_notes(session, lead.id)
            assert len(notes) == 1
            assert notes[0].body == "Called, left voicemail."
    finally:
        await engine.dispose()


async def test_add_note_rejects_empty_body():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead, _business = await _make_lead(session, tenant_id=tenant.id, native_id="n-2")
            await session.commit()

            with pytest.raises(ValidationAppError):
                await leads_services.add_note(
                    session, lead_id=lead.id, author_user_id=None, body="   "
                )
    finally:
        await engine.dispose()


async def test_add_tag_is_idempotent_and_normalizes_case():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead, _business = await _make_lead(session, tenant_id=tenant.id, native_id="tg-1")
            await session.commit()

            await leads_services.add_tag(
                session, lead_id=lead.id, tag="Hot Lead", actor_user_id=None
            )
            await leads_services.add_tag(
                session, lead_id=lead.id, tag="hot lead", actor_user_id=None
            )
            await session.commit()
            tags = await leads_repo.list_tags(session, lead.id)
            assert tags == ["hot lead"]
    finally:
        await engine.dispose()


async def test_remove_tag():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead, _business = await _make_lead(session, tenant_id=tenant.id, native_id="tg-2")
            await session.commit()
            await leads_services.add_tag(session, lead_id=lead.id, tag="warm", actor_user_id=None)
            await session.commit()

            removed = await leads_repo.remove_tag(session, lead_id=lead.id, tag="warm")
            await session.commit()
            assert removed is True
            assert await leads_repo.list_tags(session, lead.id) == []
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Bulk actions
# ---------------------------------------------------------------------------


async def test_bulk_change_status_applies_to_every_lead():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead_a, _ = await _make_lead(session, tenant_id=tenant.id, native_id="bs-1")
            lead_b, _ = await _make_lead(session, tenant_id=tenant.id, native_id="bs-2")
            await session.commit()

            await leads_services.bulk_change_status(
                session, lead_ids=[lead_a.id, lead_b.id], to_status="qualified", actor_user_id=None
            )
            await session.commit()

            for lid in (lead_a.id, lead_b.id):
                refreshed = await leads_repo.get_lead_or_raise(session, lid)
                assert refreshed.status == "qualified"
    finally:
        await engine.dispose()


async def test_bulk_assign_applies_to_every_lead():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead_a, _ = await _make_lead(session, tenant_id=tenant.id, native_id="ba-1")
            lead_b, _ = await _make_lead(session, tenant_id=tenant.id, native_id="ba-2")
            await session.commit()
            user_obj = await _make_user(session, email="bulkassignee@example.com")
            await session.commit()
            user_id = user_obj.id

            await leads_services.bulk_assign(
                session,
                lead_ids=[lead_a.id, lead_b.id],
                assigned_to_user_id=user_id,
                actor_user_id=None,
            )
            await session.commit()

            for lid in (lead_a.id, lead_b.id):
                refreshed = await leads_repo.get_lead_or_raise(session, lid)
                assert refreshed.assigned_to_user_id == user_id
    finally:
        await engine.dispose()


async def test_bulk_add_tag_applies_to_every_lead():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead_a, _ = await _make_lead(session, tenant_id=tenant.id, native_id="bt-1")
            lead_b, _ = await _make_lead(session, tenant_id=tenant.id, native_id="bt-2")
            await session.commit()

            await leads_services.bulk_add_tag(
                session, lead_ids=[lead_a.id, lead_b.id], tag="campaign-q3", actor_user_id=None
            )
            await session.commit()

            for lid in (lead_a.id, lead_b.id):
                assert await leads_repo.list_tags(session, lid) == ["campaign-q3"]
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Saved views
# ---------------------------------------------------------------------------


async def test_saved_view_create_list_and_owner_delete():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            owner_obj = await _make_user(session, email="viewowner@example.com")
            await session.commit()
            owner_id = owner_obj.id

            view = await leads_repo.create_saved_view(
                session,
                tenant_id=tenant.id,
                name="Hot leads this week",
                created_by_user_id=owner_id,
                filters={"tag": "hot"},
            )
            await session.commit()

            views = await leads_repo.list_saved_views(session, tenant.id)
            assert len(views) == 1
            assert views[0].name == "Hot leads this week"

            await leads_services.delete_saved_view(
                session, view_id=view.id, actor_user_id=owner_id, actor_can_edit=False
            )
            await session.commit()
            assert await leads_repo.list_saved_views(session, tenant.id) == []
    finally:
        await engine.dispose()


async def test_saved_view_delete_denied_for_non_owner_without_edit_permission():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            owner_obj = await _make_user(session, email="viewowner2@example.com")
            other_obj = await _make_user(session, email="otheruser@example.com")
            await session.commit()
            owner_id, other_id = owner_obj.id, other_obj.id

            view = await leads_repo.create_saved_view(
                session,
                tenant_id=tenant.id,
                name="Owner's view",
                created_by_user_id=owner_id,
                filters={},
            )
            await session.commit()

            with pytest.raises(PermissionDeniedError):
                await leads_services.delete_saved_view(
                    session, view_id=view.id, actor_user_id=other_id, actor_can_edit=False
                )
    finally:
        await engine.dispose()


async def test_saved_view_delete_allowed_for_non_owner_with_edit_permission():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            owner_obj = await _make_user(session, email="viewowner3@example.com")
            editor_obj = await _make_user(session, email="editoruser@example.com")
            await session.commit()
            owner_id, editor_id = owner_obj.id, editor_obj.id

            view = await leads_repo.create_saved_view(
                session,
                tenant_id=tenant.id,
                name="Owner's view",
                created_by_user_id=owner_id,
                filters={},
            )
            await session.commit()

            await leads_services.delete_saved_view(
                session, view_id=view.id, actor_user_id=editor_id, actor_can_edit=True
            )
            await session.commit()
            assert await leads_repo.list_saved_views(session, tenant.id) == []
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Merge carries the Lead along (Milestone 6 extension to dedup.merge_businesses)
# ---------------------------------------------------------------------------


async def test_merge_moves_loser_lead_onto_winner_when_winner_has_none():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            winner_business = await _discover(
                session, tenant_id=tenant.id, native_id="ml-1", name="Winner Business"
            )
            _loser_lead, loser_business = await _make_lead(
                session, tenant_id=tenant.id, native_id="ml-2", name="Loser Business"
            )
            await session.commit()
            assert await leads_repo.get_lead_for_business(session, winner_business.id) is None

            merge_history = await dedup.merge_businesses(
                session,
                winner_id=winner_business.id,
                loser_id=loser_business.id,
                match_type="fuzzy_name",
                confidence=0.7,
            )
            await session.commit()

            assert merge_history.moved_records["lead"] is not None
            winner_lead = await leads_repo.get_lead_for_business(session, winner_business.id)
            assert winner_lead is not None
            assert await leads_repo.get_lead_for_business(session, loser_business.id) is None
    finally:
        await engine.dispose()


async def test_merge_leaves_loser_lead_untouched_when_winner_already_has_one():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            winner_lead, winner_business = await _make_lead(
                session, tenant_id=tenant.id, native_id="ml-3", name="Winner Business"
            )
            loser_lead, loser_business = await _make_lead(
                session, tenant_id=tenant.id, native_id="ml-4", name="Loser Business"
            )
            await session.commit()

            merge_history = await dedup.merge_businesses(
                session,
                winner_id=winner_business.id,
                loser_id=loser_business.id,
                match_type="fuzzy_name",
                confidence=0.7,
            )
            await session.commit()

            assert merge_history.moved_records["lead"] is None
            # The winner's own Lead is untouched.
            refreshed_winner_lead = await leads_repo.get_lead_or_raise(session, winner_lead.id)
            assert refreshed_winner_lead.business_id == winner_business.id
            # The loser's Lead still exists, still points at the (now
            # merged-away) loser business - nothing was deleted.
            refreshed_loser_lead = await leads_repo.get_lead_or_raise(session, loser_lead.id)
            assert refreshed_loser_lead.business_id == loser_business.id
    finally:
        await engine.dispose()


async def test_undo_merge_reverses_the_lead_move():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            winner_business = await _discover(
                session, tenant_id=tenant.id, native_id="ml-5", name="Winner Business"
            )
            loser_lead, loser_business = await _make_lead(
                session, tenant_id=tenant.id, native_id="ml-6", name="Loser Business"
            )
            await session.commit()

            merge_history = await dedup.merge_businesses(
                session,
                winner_id=winner_business.id,
                loser_id=loser_business.id,
                match_type="fuzzy_name",
                confidence=0.7,
            )
            await session.commit()
            assert await leads_repo.get_lead_for_business(session, winner_business.id) is not None

            await dedup.undo_merge(session, merge_history_id=merge_history.id)
            await session.commit()

            assert await leads_repo.get_lead_for_business(session, winner_business.id) is None
            restored = await leads_repo.get_lead_or_raise(session, loser_lead.id)
            assert restored.business_id == loser_business.id
    finally:
        await engine.dispose()


async def test_double_undo_raises_conflict():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            winner_business = await _discover(
                session, tenant_id=tenant.id, native_id="ml-7", name="W"
            )
            _lead, loser_business = await _make_lead(
                session, tenant_id=tenant.id, native_id="ml-8", name="L"
            )
            await session.commit()

            merge_history = await dedup.merge_businesses(
                session,
                winner_id=winner_business.id,
                loser_id=loser_business.id,
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
