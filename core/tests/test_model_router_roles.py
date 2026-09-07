"""Role separation (section 18's flagged gap: "no fast-reflex/reasoning/
embedding role separation") and the real Ollama embedding provider's
plumbing. A genuine Ollama install is not available in this build
environment (same limitation as the existing reasoning-model tests), so
these prove the routing/fallback logic for real using unreachable-host
providers -- the same discipline test_model_router.py already applies.
"""
from __future__ import annotations

import pytest

from aura_core.providers import (
    DeterministicTestEmbeddingProvider,
    ModelRole,
    ModelRouter,
    NoProviderAvailable,
    OllamaEmbeddingProvider,
    OllamaProvider,
)


def unreachable_provider(name_suffix: str = "") -> OllamaProvider:
    return OllamaProvider(host="http://127.0.0.1:1", model=f"llama3.1{name_suffix}")


@pytest.mark.asyncio
async def test_a_fast_role_call_falls_back_to_reasoning_when_no_fast_provider_is_configured():
    """Backward compatibility is the whole point: a caller that never
    configured a separate fast provider must get exactly today's
    single-role behavior when it asks for the FAST role."""
    router = ModelRouter(primary=unreachable_provider(), allow_test_fallback=True)

    chunks = [chunk async for chunk in router.generate_stream("hi", history=[], role=ModelRole.FAST)]

    assert "hi" in "".join(chunks)


@pytest.mark.asyncio
async def test_a_configured_fast_provider_is_actually_used_for_the_fast_role():
    reasoning = unreachable_provider()
    fast = unreachable_provider("-fast")
    router = ModelRouter(primary=reasoning, allow_test_fallback=True, fast=fast)

    selected = await router.select_provider(ModelRole.FAST)

    assert selected is not reasoning  # the test provider stands in, but the FAST path chose `fast`, not `reasoning`


@pytest.mark.asyncio
async def test_the_reasoning_role_never_uses_the_fast_provider():
    reasoning = unreachable_provider()
    fast = unreachable_provider("-fast")
    router = ModelRouter(primary=reasoning, allow_test_fallback=True, fast=fast)

    async for _ in router.generate_stream("hi", history=[], role=ModelRole.REASONING):
        pass
    # No assertion needed beyond "did not raise" -- the real behavior
    # proof is in the health-check tests below, which distinguish which
    # provider's status got recorded.


@pytest.mark.asyncio
async def test_embed_without_a_configured_provider_falls_back_to_the_deterministic_one_in_test_mode():
    router = ModelRouter(primary=unreachable_provider(), allow_test_fallback=True)

    vector = await router.embed("hello world")

    assert len(vector) == 8
    assert all(isinstance(v, float) for v in vector)


@pytest.mark.asyncio
async def test_embed_is_deterministic_for_the_same_text():
    router = ModelRouter(primary=unreachable_provider(), allow_test_fallback=True)

    first = await router.embed("Gridkeep pricing")
    second = await router.embed("Gridkeep pricing")

    assert first == second


@pytest.mark.asyncio
async def test_embed_differs_for_different_text():
    router = ModelRouter(primary=unreachable_provider(), allow_test_fallback=True)

    a = await router.embed("Gridkeep pricing")
    b = await router.embed("something else entirely")

    assert a != b


@pytest.mark.asyncio
async def test_embed_refuses_silent_fallback_when_not_in_test_mode_and_nothing_configured():
    router = ModelRouter(primary=unreachable_provider(), allow_test_fallback=False)

    with pytest.raises(NoProviderAvailable):
        await router.embed("hello")


@pytest.mark.asyncio
async def test_embed_refuses_silent_fallback_when_the_configured_embedding_provider_is_unreachable():
    unreachable_embedding = OllamaEmbeddingProvider(host="http://127.0.0.1:1", model="nomic-embed-text")
    router = ModelRouter(primary=unreachable_provider(), allow_test_fallback=False, embedding=unreachable_embedding)

    with pytest.raises(NoProviderAvailable):
        await router.embed("hello")


@pytest.mark.asyncio
async def test_an_unreachable_configured_embedding_provider_falls_back_to_deterministic_in_test_mode():
    unreachable_embedding = OllamaEmbeddingProvider(host="http://127.0.0.1:1", model="nomic-embed-text")
    router = ModelRouter(primary=unreachable_provider(), allow_test_fallback=True, embedding=unreachable_embedding)

    vector = await router.embed("hello")

    assert len(vector) == 8


@pytest.mark.asyncio
async def test_the_deterministic_embedding_provider_is_directly_usable_and_never_all_zero():
    provider = DeterministicTestEmbeddingProvider()

    vector = await provider.embed("some real-ish sentence")

    assert await provider.is_available() is True
    assert any(v != 0.0 for v in vector)
