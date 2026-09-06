"""Model router.

Selects a provider per docs/architecture/07-model-routing.md's capability-
class idea, simplified to one class ("local reasoning model") for this
build. Health-checks the real provider before ever using it, and only ever
falls back to the test-only provider when explicitly running in test mode
— never silently in a context where the output could be mistaken for a
genuine model response.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from ..status import CapabilityStatus, registry
from .base import ModelProvider
from .test_provider import DeterministicTestProvider


class NoProviderAvailable(RuntimeError):
    pass


class ModelRouter:
    def __init__(self, primary: ModelProvider, allow_test_fallback: bool) -> None:
        self._primary = primary
        self._allow_test_fallback = allow_test_fallback
        self._test_provider = DeterministicTestProvider()

    async def select_provider(self) -> ModelProvider:
        if await self._primary.is_available():
            registry.set("model.ollama", CapabilityStatus.LIVE, f"{self._primary.name} responded to health check")
            return self._primary

        registry.set(
            "model.ollama",
            CapabilityStatus.NOT_CONNECTED,
            f"{self._primary.name} did not respond; is it running and reachable?",
        )

        if self._allow_test_fallback:
            return self._test_provider

        raise NoProviderAvailable(
            "No model provider is reachable. Start Ollama (see core/RUNBOOK.md) "
            "or set AURA_ENV=test to use the deterministic test provider."
        )

    async def generate_stream(self, prompt: str, history: list[dict[str, str]]) -> AsyncIterator[str]:
        provider = await self.select_provider()
        async for chunk in provider.generate_stream(prompt, history):
            yield chunk
