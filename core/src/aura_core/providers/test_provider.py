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
import hashlib
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


class DeterministicTestEmbeddingProvider:
    """NOT a real embedding model -- a fixed-length vector derived from a
    SHA-256 hash of the input text, deterministic (same text always
    yields the same vector) and normalized to unit length like a genuine
    embedding would be, purely so this proves the router/CLI/API plumbing
    around embeddings without ever presenting a fabricated vector as a
    real one. Same "explicitly test-only, gated by allow_test_provider"
    posture as DeterministicTestProvider above."""

    name = "test-embedding"
    _dimensions = 8

    async def is_available(self) -> bool:
        return True

    async def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        raw = [digest[i] / 255.0 for i in range(self._dimensions)]
        norm = sum(v * v for v in raw) ** 0.5
        return [v / norm for v in raw] if norm > 0 else raw
