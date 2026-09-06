"""Deterministic, explicitly test-only provider.

This is NOT a model. It exists only to prove the streaming plumbing
(provider -> router -> API SSE -> CLI terminal output) genuinely delivers
incremental chunks over time, rather than faking streaming by revealing a
pre-computed string character by character with no real generation behind
it. Its output must never be presented to an owner as a real AI response —
enforced by config.Settings.allow_test_provider, which the router refuses
outside AURA_ENV=test.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator


class DeterministicTestProvider:
    name = "test-echo"

    async def is_available(self) -> bool:
        return True

    async def generate_stream(self, prompt: str, history: list[dict[str, str]]) -> AsyncIterator[str]:
        response = f"[test-provider echo] you said: {prompt}"
        for word in response.split(" "):
            await asyncio.sleep(0)  # yield control to the event loop between chunks, proving real incrementality
            yield word + " "
