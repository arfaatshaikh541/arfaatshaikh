"""answer_question is the closed loop the audit's acceptance example
names directly: "why did we decide to charge Gridkeep customers that
way" answered from real retrieved records, never the model's unaided
guess. The model here is a scripted stand-in (the deterministic
test-mode provider only ever echoes its prompt, which is realistic for
proving streaming plumbing but useless for proving an answer was
actually grounded in the context passed to it) -- these tests assert on
what was *fed* to the model as much as what it returned, since a real
model swapped in later inherits the same contract.
"""
from __future__ import annotations

import pytest

from aura_core.memory import MemoryStore, answer_question
from aura_core.providers import ModelRouter


class RecordingProvider:
    """Captures the exact prompt it was given and returns a scripted
    answer, so tests can assert the real retrieved memory records (not
    just some memory) were actually placed in front of the model."""
    name = "recording"

    def __init__(self, response: str = "scripted answer") -> None:
        self.response = response
        self.last_prompt: str | None = None

    async def is_available(self) -> bool:
        return True

    async def generate_stream(self, prompt: str, history: list[dict[str, str]]):
        self.last_prompt = prompt
        for word in self.response.split(" "):
            yield word + " "


@pytest.mark.asyncio
async def test_answer_is_grounded_in_real_retrieved_decision_history(tmp_path):
    memory = MemoryStore(f"sqlite:///{tmp_path}/qa.db")
    original = memory.record_decision(
        goal="pricing", statement="Charge Gridkeep customers a flat monthly fee",
        reasoning="simplest to bill", source="s",
    )
    memory.record_decision(
        goal="pricing", statement="Switch Gridkeep customers to usage-based pricing",
        reasoning="flat fee under-charged heavy users", source="s", supersedes_id=original.id,
    )

    provider = RecordingProvider("Gridkeep started on a flat fee, then moved to usage-based pricing.")
    router = ModelRouter(primary=provider, allow_test_fallback=True)

    result = await answer_question("Why did we decide to charge Gridkeep customers that way?", memory, router)

    assert result.error is None
    assert result.answer == "Gridkeep started on a flat fee, then moved to usage-based pricing."
    assert len(result.context_used) >= 1
    assert any(c["kind"] == "decision" for c in result.context_used)
    # The model must have actually been shown the supersession history,
    # not just the single top-ranked row.
    assert "usage-based pricing" in provider.last_prompt
    assert "decision history" in provider.last_prompt


@pytest.mark.asyncio
async def test_no_relevant_memory_is_reported_honestly_not_sent_to_the_model(tmp_path):
    memory = MemoryStore(f"sqlite:///{tmp_path}/qa_empty.db")
    provider = RecordingProvider("I should never be called")
    router = ModelRouter(primary=provider, allow_test_fallback=True)

    result = await answer_question("What happened with Gridkeep pricing?", memory, router)

    assert result.error == "no relevant memory found for this question"
    assert result.answer is None
    assert provider.last_prompt is None  # never even called -- nothing to ground an answer in


@pytest.mark.asyncio
async def test_provider_unavailable_is_reported_as_an_error_not_a_crash(tmp_path):
    from aura_core.providers import OllamaProvider

    memory = MemoryStore(f"sqlite:///{tmp_path}/qa_unavailable.db")
    memory.record_event(event_type="e", summary="Gridkeep pricing was reviewed", source="s")
    unreachable = OllamaProvider(host="http://127.0.0.1:1", model="llama3.1")
    router = ModelRouter(primary=unreachable, allow_test_fallback=False)

    result = await answer_question("What happened with Gridkeep pricing?", memory, router)

    assert result.error is not None
    assert result.answer is None
    assert len(result.context_used) == 1  # retrieval itself still worked
