from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aura_core.memory import MemoryStore


def make_store(tmp_path) -> MemoryStore:
    return MemoryStore(f"sqlite:///{tmp_path}/mem.db")


def test_record_and_query_episodic_event(tmp_path):
    store = make_store(tmp_path)
    before = datetime.now(timezone.utc) - timedelta(seconds=1)

    store.record_event(event_type="test.event", summary="something happened", source="unit-test")

    events = store.events_since(before)
    assert len(events) == 1
    assert events[0].summary == "something happened"
    assert events[0].source == "unit-test"


def test_semantic_fact_low_confidence_is_superseded_cleanly(tmp_path):
    store = make_store(tmp_path)

    first, warning = store.assert_fact(
        subject="Gridkeep", predicate="pricing_tier", object="Basic",
        source="unit-test", confidence=0.3,
    )
    assert warning is None

    second, warning = store.assert_fact(
        subject="Gridkeep", predicate="pricing_tier", object="Pro",
        source="unit-test", confidence=0.9,
    )
    assert warning is None  # low-confidence prior fact supersedes cleanly, no conflict raised

    facts = store.facts_about("Gridkeep")
    assert len(facts) == 1
    assert facts[0].object == "Pro"


def test_semantic_fact_high_confidence_conflict_is_flagged_not_overwritten(tmp_path):
    store = make_store(tmp_path)

    store.assert_fact(
        subject="Gridkeep", predicate="pricing_tier", object="Basic",
        source="unit-test", confidence=0.95,
    )

    _new_fact, warning = store.assert_fact(
        subject="Gridkeep", predicate="pricing_tier", object="Pro",
        source="unit-test", confidence=0.9,
    )

    assert warning is not None
    assert warning.existing_object == "Basic"
    assert warning.new_object == "Pro"

    # Both facts should still be independently retrievable — no silent overwrite.
    facts = store.facts_about("Gridkeep")
    assert {f.object for f in facts} == {"Basic", "Pro"}


def test_decision_memory_records_reasoning(tmp_path):
    store = make_store(tmp_path)
    store.record_decision(
        goal="reach-100k-mrr", statement="Prioritize outbound over paid ads",
        reasoning="Current CAC via paid ads exceeds LTV at present conversion rate",
        source="unit-test",
    )
    decisions = store.decisions_for_goal("reach-100k-mrr")
    assert len(decisions) == 1
    assert "outbound" in decisions[0].statement


def test_commitment_lifecycle(tmp_path):
    store = make_store(tmp_path)
    commitment = store.add_commitment(description="Follow up with Ahmed", source="unit-test")

    open_ones = store.open_commitments()
    assert len(open_ones) == 1
    assert open_ones[0].id == commitment.id

    store.fulfill_commitment(commitment.id)
    assert store.open_commitments() == []
