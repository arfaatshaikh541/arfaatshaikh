"""classify_message_intent closes the "classify" half of section 12's
email gap. A scripted provider stands in for the model (the same
RecordingProvider shape test_memory_qa.py already uses) -- these tests
assert both on what the model actually returns and, for the malformed
cases, that a bad response is reported honestly as "unclassified"
rather than silently mapped to the nearest-looking category.
"""
from __future__ import annotations

import pytest

from aura_core.email_intent import INTENT_CATEGORIES, classify_message_intent
from aura_core.providers import ModelRouter


class ScriptedProvider:
    name = "scripted"

    def __init__(self, response: str) -> None:
        self.response = response
        self.last_prompt: str | None = None

    async def is_available(self) -> bool:
        return True

    async def generate_stream(self, prompt: str, history: list[dict[str, str]]):
        self.last_prompt = prompt
        for word in self.response.split(" "):
            yield word + " "


@pytest.mark.asyncio
async def test_a_clean_category_response_is_returned_as_is():
    provider = ScriptedProvider("complaint")
    router = ModelRouter(primary=provider, allow_test_fallback=False)

    result = await classify_message_intent("Broken widget", "This doesn't work at all.", router)

    assert result == "complaint"


@pytest.mark.asyncio
async def test_the_real_subject_and_body_are_placed_in_the_prompt():
    provider = ScriptedProvider("inquiry")
    router = ModelRouter(primary=provider, allow_test_fallback=False)

    await classify_message_intent("Pricing question", "How much does Gridkeep cost?", router)

    assert "Pricing question" in provider.last_prompt
    assert "How much does Gridkeep cost?" in provider.last_prompt


@pytest.mark.asyncio
async def test_a_response_with_extra_words_still_extracts_the_category():
    provider = ScriptedProvider("spam this is definitely junk mail")
    router = ModelRouter(primary=provider, allow_test_fallback=False)

    result = await classify_message_intent("You won!!!", "Click here now", router)

    assert result == "spam"


@pytest.mark.asyncio
async def test_a_response_outside_the_fixed_category_list_is_reported_unclassified_not_guessed():
    provider = ScriptedProvider("this email seems urgent and important")
    router = ModelRouter(primary=provider, allow_test_fallback=False)

    result = await classify_message_intent("Subject", "Body", router)

    assert result == "unclassified"


@pytest.mark.asyncio
async def test_an_empty_model_response_is_unclassified_not_a_crash():
    provider = ScriptedProvider("")
    router = ModelRouter(primary=provider, allow_test_fallback=False)

    result = await classify_message_intent("Subject", "Body", router)

    assert result == "unclassified"


@pytest.mark.asyncio
async def test_every_real_category_round_trips():
    for category in INTENT_CATEGORIES:
        provider = ScriptedProvider(category)
        router = ModelRouter(primary=provider, allow_test_fallback=False)
        assert await classify_message_intent("s", "b", router) == category
