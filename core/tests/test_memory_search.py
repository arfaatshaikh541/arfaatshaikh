"""Free-text search and decision-chain reconstruction -- the retrieval
primitives docs/FINAL_COMPLETION_AUDIT.md flagged as missing (exact-match
only, no way to answer a question that names no goal id or exact
subject). No mocking: real SQLite-backed MemoryStore, real TF-IDF scoring
over real inserted rows."""
from __future__ import annotations

from aura_core.memory import MemoryStore


def make_store(tmp_path) -> MemoryStore:
    return MemoryStore(f"sqlite:///{tmp_path}/search.db")


def test_search_ranks_relevant_events_above_unrelated_ones(tmp_path):
    memory = make_store(tmp_path)
    memory.record_event(event_type="pricing", summary="Gridkeep customers moved to tiered monthly pricing", source="s")
    memory.record_event(event_type="weather", summary="It rained heavily in the office car park today", source="s")
    memory.record_event(event_type="pricing", summary="Gridkeep pricing tiers reviewed again after complaints", source="s")

    results = memory.search("Gridkeep pricing")

    assert len(results) >= 2
    assert all("Gridkeep" in r.text for r in results[:2])
    assert results[0].score >= results[-1].score  # ranked, not just filtered


def test_search_covers_events_facts_decisions_and_commitments_together(tmp_path):
    memory = make_store(tmp_path)
    memory.record_event(event_type="e", summary="Acme onboarding kicked off", source="s")
    memory.assert_fact(subject="Acme", predicate="plan", object="enterprise", source="s")
    memory.record_decision(goal="g1", statement="Offer Acme a discount", reasoning="new logo", source="s")
    memory.add_commitment(description="Follow up with Acme in two weeks", source="s")

    results = memory.search("Acme")
    kinds = {r.kind for r in results}

    assert kinds == {"event", "fact", "decision", "commitment"}


def test_search_with_no_matching_terms_returns_nothing_not_everything(tmp_path):
    memory = make_store(tmp_path)
    memory.record_event(event_type="e", summary="Completely unrelated office event", source="s")

    assert memory.search("supersonic jellyfish astronomy") == []


def test_search_on_an_empty_store_does_not_crash(tmp_path):
    memory = make_store(tmp_path)
    assert memory.search("anything") == []


def test_decision_chain_reconstructs_original_and_every_amendment_in_order(tmp_path):
    memory = make_store(tmp_path)
    original = memory.record_decision(
        goal="pricing", statement="Charge Gridkeep customers a flat monthly fee",
        reasoning="simplest to bill", source="s",
    )
    amendment = memory.record_decision(
        goal="pricing", statement="Switch Gridkeep customers to usage-based pricing",
        reasoning="flat fee under-charged heavy users", source="s", supersedes_id=original.id,
    )
    latest = memory.record_decision(
        goal="pricing", statement="Cap usage-based pricing to avoid bill shock",
        reasoning="customer complaints about unpredictable bills", source="s", supersedes_id=amendment.id,
    )

    chain_from_original = memory.decision_chain(original.id)
    chain_from_latest = memory.decision_chain(latest.id)

    assert [d.id for d in chain_from_original] == [original.id, amendment.id, latest.id]
    assert [d.id for d in chain_from_latest] == [original.id, amendment.id, latest.id]


def test_decision_chain_of_a_never_superseded_decision_is_just_itself(tmp_path):
    memory = make_store(tmp_path)
    decision = memory.record_decision(goal="g", statement="s", reasoning="r", source="src")

    assert [d.id for d in memory.decision_chain(decision.id)] == [decision.id]


def test_decision_chain_of_an_unknown_id_is_empty(tmp_path):
    memory = make_store(tmp_path)
    assert memory.decision_chain("does-not-exist") == []
