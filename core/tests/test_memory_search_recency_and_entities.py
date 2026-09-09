"""Recency weighting and entity cross-referencing on top of
MemoryStore.search()'s existing TF-IDF ranking -- the two remaining
"what's left" items this document's own audit named after the PHASE 5
pass closed search/decision-chain/Q&A."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aura_core.memory import MemoryStore, WorldModelStore


def make_store(tmp_path) -> MemoryStore:
    return MemoryStore(f"sqlite:///{tmp_path}/search_recency.db")


def _backdate(memory: MemoryStore, event_id: str, when: datetime) -> None:
    """Test-only helper: reaches into the row to simulate a record from
    long ago, since record_event() always stamps `created_at` as now."""
    with memory._Session() as session:
        from aura_core.memory.models import EpisodicEvent
        row = session.get(EpisodicEvent, event_id)
        row.created_at = when
        session.commit()


def test_among_equally_relevant_results_the_more_recent_one_ranks_first(tmp_path):
    memory = make_store(tmp_path)
    old = memory.record_event(event_type="pricing", summary="Gridkeep pricing reviewed", source="s")
    recent = memory.record_event(event_type="pricing", summary="Gridkeep pricing reviewed", source="s")
    _backdate(memory, old.id, datetime.now(timezone.utc) - timedelta(days=400))

    results = memory.search("Gridkeep pricing reviewed", recency_half_life_days=90)

    assert results[0].id == recent.id
    assert results[0].score > results[1].score


def test_a_much_stronger_old_match_still_beats_a_weak_recent_one(tmp_path):
    """Recency is a tie-breaker, not a veto over relevance -- a record
    that barely matches the query must not leapfrog one that matches it
    thoroughly just for being newer."""
    memory = make_store(tmp_path)
    strong_old = memory.record_event(
        event_type="pricing", summary="Gridkeep customers moved to tiered monthly pricing plans", source="s",
    )
    weak_recent = memory.record_event(event_type="other", summary="Gridkeep mentioned once in passing", source="s")
    _backdate(memory, strong_old.id, datetime.now(timezone.utc) - timedelta(days=1000))

    results = memory.search("Gridkeep tiered monthly pricing plans", recency_half_life_days=30)

    assert results[0].id == strong_old.id


def test_a_half_life_of_zero_disables_recency_weighting_entirely(tmp_path):
    memory = make_store(tmp_path)
    old = memory.record_event(event_type="pricing", summary="Gridkeep pricing reviewed", source="s")
    recent = memory.record_event(event_type="pricing", summary="Gridkeep pricing reviewed", source="s")
    _backdate(memory, old.id, datetime.now(timezone.utc) - timedelta(days=1000))

    results = memory.search("Gridkeep pricing reviewed", recency_half_life_days=0)

    assert results[0].score == results[1].score


def test_search_without_a_world_model_returns_no_entity_ids(tmp_path):
    memory = make_store(tmp_path)
    memory.record_event(event_type="e", summary="Acme onboarding kicked off", source="s")

    results = memory.search("Acme onboarding")

    assert results[0].entity_ids == []


def test_search_with_a_world_model_tags_results_mentioning_a_known_entity(tmp_path):
    memory = make_store(tmp_path)
    world_model = WorldModelStore(f"sqlite:///{tmp_path}/search_recency.db")
    acme = world_model.upsert_entity(entity_type="account", name="Acme", source="s")
    memory.record_event(event_type="e", summary="Acme onboarding kicked off this week", source="s")
    memory.record_event(event_type="e", summary="Unrelated office event", source="s")

    results = memory.search("Acme onboarding", world_model=world_model)

    assert results[0].entity_ids == [acme.id]


def test_entity_cross_referencing_does_not_affect_ranking_order(tmp_path):
    """Cross-referencing is metadata attached to a result, not a scoring
    signal -- passing world_model must not change which results rank
    above which."""
    memory = make_store(tmp_path)
    world_model = WorldModelStore(f"sqlite:///{tmp_path}/search_recency.db")
    world_model.upsert_entity(entity_type="account", name="Acme", source="s")
    memory.record_event(event_type="e", summary="Acme pricing discussion", source="s")
    memory.record_event(event_type="e", summary="Acme pricing discussion continued in depth", source="s")

    without = [r.id for r in memory.search("Acme pricing discussion")]
    with_wm = [r.id for r in memory.search("Acme pricing discussion", world_model=world_model)]

    assert without == with_wm
