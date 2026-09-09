from __future__ import annotations

import pytest

from aura_core.providers import ModelRouter, NoProviderAvailable, OllamaProvider


@pytest.mark.asyncio
async def test_router_reports_ollama_unavailable_when_unreachable():
    # Real code path: an OllamaProvider pointed at a port nothing listens on
    # must genuinely fail its HTTP health check, not assume availability.
    unreachable = OllamaProvider(host="http://127.0.0.1:1", model="llama3.1")
    assert await unreachable.is_available() is False


@pytest.mark.asyncio
async def test_router_falls_back_to_test_provider_only_when_allowed():
    unreachable = OllamaProvider(host="http://127.0.0.1:1", model="llama3.1")
    router = ModelRouter(primary=unreachable, allow_test_fallback=True)

    chunks = [chunk async for chunk in router.generate_stream("hello", history=[])]

    assert len(chunks) > 1  # genuinely incremental, not one blob
    assert "hello" in "".join(chunks)


@pytest.mark.asyncio
async def test_router_refuses_silent_fallback_when_not_in_test_mode():
    unreachable = OllamaProvider(host="http://127.0.0.1:1", model="llama3.1")
    router = ModelRouter(primary=unreachable, allow_test_fallback=False)

    with pytest.raises(NoProviderAvailable):
        async for _ in router.generate_stream("hello", history=[]):
            pass
