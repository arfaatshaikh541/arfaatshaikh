"""Model router.

Selects a provider per docs/architecture/07-model-routing.md's capability-
class idea, narrowed to the three roles this build actually separates:
REASONING (the general-purpose local model -- the only role that existed
before this file gained role separation), FAST (high-volume, low-
complexity calls that don't need a full reasoning pass), and EMBEDDING
(semantic memory retrieval -- vectors, not text). The full seven-class
table in the architecture doc (coding/vision/frontier-reasoning/speech)
needs providers this codebase has no credentials for and is not built.

Every role is optional except REASONING: a caller that doesn't configure
`fast` or `embedding` gets REASONING's provider for FAST calls (today's
un-split behavior, unchanged) and NoProviderAvailable for EMBEDDING calls
(there is no reasonable "make up an embedding" fallback). Health-checks
the real provider before ever using it, and only ever falls back to the
test-only providers when explicitly running in test mode — never silently
in a context where the output could be mistaken for a genuine model
response.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from ..status import CapabilityStatus, registry
from .base import EmbeddingProvider, ModelProvider, ModelRole
from .test_provider import DeterministicTestEmbeddingProvider, DeterministicTestProvider


class NoProviderAvailable(RuntimeError):
    pass


class ModelRouter:
    def __init__(
        self, primary: ModelProvider, allow_test_fallback: bool,
        fast: ModelProvider | None = None, embedding: EmbeddingProvider | None = None,
    ) -> None:
        self._primary = primary
        self._fast = fast
        self._embedding = embedding
        self._allow_test_fallback = allow_test_fallback
        self._test_provider = DeterministicTestProvider()
        self._test_embedding_provider = DeterministicTestEmbeddingProvider()

    async def select_provider(self, role: ModelRole = ModelRole.REASONING) -> ModelProvider:
        candidate = self._fast if role == ModelRole.FAST and self._fast is not None else self._primary
        status_key = "model.ollama" if candidate is self._primary else f"model.ollama.{role.value}"

        if await candidate.is_available():
            registry.set(status_key, CapabilityStatus.LIVE, f"{candidate.name} responded to health check")
            return candidate

        registry.set(
            status_key, CapabilityStatus.NOT_CONNECTED,
            f"{candidate.name} did not respond; is it running and reachable?",
        )

        if self._allow_test_fallback:
            return self._test_provider

        raise NoProviderAvailable(
            "No model provider is reachable. Start Ollama (see core/RUNBOOK.md) "
            "or set AURA_ENV=test to use the deterministic test provider."
        )

    async def generate_stream(
        self, prompt: str, history: list[dict[str, str]], role: ModelRole = ModelRole.REASONING,
    ) -> AsyncIterator[str]:
        provider = await self.select_provider(role)
        async for chunk in provider.generate_stream(prompt, history):
            yield chunk

    async def embed(self, text: str) -> list[float]:
        if self._embedding is None:
            if self._allow_test_fallback:
                registry.set("model.ollama.embedding", CapabilityStatus.NOT_CONNECTED, "no embedding provider configured")
                return await self._test_embedding_provider.embed(text)
            raise NoProviderAvailable(
                "No embedding provider configured. Set AURA_OLLAMA_EMBEDDING_MODEL "
                "(see core/RUNBOOK.md) or set AURA_ENV=test to use the deterministic test provider."
            )

        if await self._embedding.is_available():
            registry.set("model.ollama.embedding", CapabilityStatus.LIVE, f"{self._embedding.name} responded to health check")
            return await self._embedding.embed(text)

        registry.set(
            "model.ollama.embedding", CapabilityStatus.NOT_CONNECTED,
            f"{self._embedding.name} did not respond; is it running and reachable?",
        )
        if self._allow_test_fallback:
            return await self._test_embedding_provider.embed(text)
        raise NoProviderAvailable(
            "No embedding provider is reachable. Start Ollama with an embedding "
            "model pulled (see core/RUNBOOK.md) or set AURA_ENV=test."
        )
