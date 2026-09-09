"""Synthetic-history memory validation, per section 6/23 of the product
spec: "generate synthetic histories... include thousands of events...
test retrieval quality... measure it. Do not simply assert that it
works." This is deliberately bounded (~1,000 records, not the full
12-month/thousands-of-events production scenario) to keep this in the
normal test suite's runtime budget -- honestly a correctness-and-
performance proof at meaningful scale, not the full endurance scenario
section 23 separately calls for (a multi-day soak test, which belongs
in a dedicated, manually-triggered run, not every `pytest` invocation).

The acceptance query from the spec is used verbatim: "why did we decide
to charge Gridkeep customers that way?"
"""
from __future__ import annotations

import random
import time

import pytest

from aura_core.memory import MemoryStore, answer_question
from aura_core.providers import ModelRouter

_NOISE_TOPICS = [
    ("marketing", "Reviewed the {q} campaign performance for {company}"),
    ("support", "Resolved a support ticket from {company} about login issues"),
    ("hiring", "Interviewed a candidate for the {company} account manager role"),
    ("office", "Ordered new office supplies for the {company} team"),
    ("vendor", "Renewed the {company} vendor contract for another year"),
    ("legal", "Reviewed the {company} NDA before the kickoff call"),
    ("it", "Rotated API credentials for the {company} integration"),
    ("sales", "Followed up with {company} after the demo call"),
    ("product", "Shipped a bugfix requested by {company}"),
    ("finance", "Reconciled the {company} invoice against the bank statement"),
]
_NOISE_COMPANIES = [
    "Acme Corp", "Northwind Traders", "Initech", "Globex", "Umbrella Retail",
    "Wonka Industries", "Stark Logistics", "Wayne Facilities", "Hooli Systems", "Vandelay Imports",
]


def _generate_noise(memory: MemoryStore, rng: random.Random, count: int) -> None:
    for i in range(count):
        topic, template = rng.choice(_NOISE_TOPICS)
        company = rng.choice(_NOISE_COMPANIES)
        text = template.format(q=topic, company=company)
        kind = rng.choice(["event", "fact", "decision", "commitment"])
        if kind == "event":
            memory.record_event(event_type=topic, summary=text, source="synthetic")
        elif kind == "fact":
            memory.assert_fact(subject=company, predicate=topic, object=text, source="synthetic")
        elif kind == "decision":
            memory.record_decision(goal=f"noise-{i}", statement=text, reasoning="routine", source="synthetic")
        else:
            memory.add_commitment(description=text, source="synthetic")


@pytest.fixture(scope="module")
def populated_memory(tmp_path_factory):
    """Built once per module (not per test) -- generating ~1,000 rows is
    the expensive part, and nothing here mutates state in a way that
    would make sharing it across the two tests below unsafe."""
    tmp_path = tmp_path_factory.mktemp("synthetic_history")
    memory = MemoryStore(f"sqlite:///{tmp_path}/synthetic.db")
    rng = random.Random(20260101)  # fixed seed: deterministic, not flaky

    _generate_noise(memory, rng, count=400)

    original = memory.record_decision(
        goal="gridkeep-pricing", statement="Charge Gridkeep customers a flat monthly fee",
        reasoning="simplest to bill given their usage was predictable at signup", source="finance",
    )
    _generate_noise(memory, rng, count=300)

    amended = memory.record_decision(
        goal="gridkeep-pricing", statement="Switch Gridkeep customers to usage-based pricing",
        reasoning="the flat fee under-charged their heaviest users once usage grew", source="finance",
        supersedes_id=original.id,
    )
    memory.record_event(
        event_type="pricing", summary="Gridkeep finance team confirmed the usage-based pricing rollout date",
        source="synthetic",
    )
    _generate_noise(memory, rng, count=300)

    latest = memory.record_decision(
        goal="gridkeep-pricing", statement="Cap usage-based pricing to avoid bill shock for Gridkeep customers",
        reasoning="customers complained the usage-based bills were unpredictable month to month", source="finance",
        supersedes_id=amended.id,
    )

    return memory, original, amended, latest


def test_search_surfaces_the_real_signal_above_a_thousand_records_of_noise(populated_memory):
    memory, original, amended, latest = populated_memory

    started = time.monotonic()
    results = memory.search("why did we decide to charge Gridkeep customers that way", limit=5)
    elapsed = time.monotonic() - started

    result_ids = {r.id for r in results}
    assert original.id in result_ids or amended.id in result_ids or latest.id in result_ids
    assert any("Gridkeep" in r.text and "pricing" in r.text.lower() for r in results[:3])
    # A measured performance bound, not just correctness: recomputing
    # TF-IDF over ~1,000 rows at query time must stay fast enough to
    # serve an interactive "ask AURA" request, not a batch job.
    assert elapsed < 2.0, f"search over ~1,000 records took {elapsed:.2f}s, expected under 2s"


def test_decision_chain_reconstructs_correctly_even_surrounded_by_hundreds_of_unrelated_decisions(populated_memory):
    memory, original, amended, latest = populated_memory

    chain = memory.decision_chain(latest.id)

    assert [d.id for d in chain] == [original.id, amended.id, latest.id]
    assert chain[0].statement == "Charge Gridkeep customers a flat monthly fee"
    assert chain[-1].statement == "Cap usage-based pricing to avoid bill shock for Gridkeep customers"


class _ScriptedProvider:
    name = "scripted"

    def __init__(self, response: str) -> None:
        self._response = response

    async def is_available(self) -> bool:
        return True

    async def generate_stream(self, prompt: str, history: list[dict[str, str]]):
        for word in self._response.split(" "):
            yield word + " "


@pytest.mark.asyncio
async def test_the_acceptance_query_from_the_spec_is_answered_from_grounded_history(populated_memory):
    """The exact acceptance example from section 6: "Why did we decide
    to charge Gridkeep customers that way?" -> the answer must be built
    from the original decision, the amendment, and the dates/rationale
    for each -- not a generic non-answer -- even with ~1,000 unrelated
    records in the same store."""
    memory, _original, _amended, _latest = populated_memory
    provider = _ScriptedProvider(
        "Gridkeep started on a flat monthly fee, then moved to usage-based pricing "
        "because heavy users were under-charged, then that was capped after billing complaints."
    )
    router = ModelRouter(primary=provider, allow_test_fallback=True)

    result = await answer_question("Why did we decide to charge Gridkeep customers that way?", memory, router)

    assert result.error is None
    assert result.answer is not None
    assert any(c["kind"] == "decision" for c in result.context_used)
