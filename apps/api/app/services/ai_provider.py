"""Provider-agnostic AI layer.

    AIProvider
    +-- OllamaProvider      (local, self-hosted - the default)
    +-- LocalModelProvider  (alias of OllamaProvider: Ollama IS the local-model runtime here)
    +-- ExternalProvider    (off by default; requires an explicit opt-in)

This module exists so the platform NEVER depends on a paid AI API to
function, and never calls one silently. `get_ai_provider()` is the only
supported way to obtain a provider - it enforces the opt-in rule below, so
there is exactly one place in the codebase where "would this hit a paid
API?" needs to be answered.

Unavailability is a normal, expected outcome (no Ollama daemon installed,
model not pulled yet, etc.) and is always returned as a plain result, never
raised as an exception that could be mistaken for a real failure and never
covered up by fabricating a response.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.core.config import Settings


@dataclass(frozen=True)
class AIGenerationResult:
    available: bool
    provider: str
    text: str | None = None
    error: str | None = None


class AIProvider(ABC):
    name: str

    @abstractmethod
    async def is_available(self) -> bool: ...

    @abstractmethod
    async def generate(self, prompt: str) -> AIGenerationResult: ...


class OllamaProvider(AIProvider):
    """Talks to a self-hosted Ollama server. No API key, no external network call."""

    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def generate(self, prompt: str) -> AIGenerationResult:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/generate",
                    json={"model": self._model, "prompt": prompt, "stream": False},
                )
        except httpx.HTTPError as exc:
            reason = exc.__class__.__name__
            error = f"local_ai_unavailable: could not reach Ollama at {self._base_url} ({reason})"
            return AIGenerationResult(available=False, provider=self.name, error=error)
        if response.status_code != 200:
            return AIGenerationResult(
                available=False, provider=self.name,
                error=f"local_ai_error: Ollama returned HTTP {response.status_code}",
            )
        payload = response.json()
        text = payload.get("response")
        if not text:
            return AIGenerationResult(
                available=False, provider=self.name, error="local_ai_empty_response",
            )
        return AIGenerationResult(available=True, provider=self.name, text=text)


# Ollama IS the local-model runtime this platform targets; this alias exists
# only so callers/config that think in terms of "local model" have a name
# that matches, without a second implementation to keep in sync.
LocalModelProvider = OllamaProvider


class ExternalProvider(AIProvider):
    """Disabled by construction.

    Documents the extension point without wiring in a real paid API here.
    """

    name = "external"

    async def is_available(self) -> bool:
        return False

    async def generate(self, prompt: str) -> AIGenerationResult:
        return AIGenerationResult(
            available=False, provider=self.name,
            error="external_ai_disabled: external AI providers are not configured",
        )


def get_ai_provider(settings: Settings) -> AIProvider:
    if settings.ai_mode == "external":
        if not settings.external_ai_enabled:
            return ExternalProvider()
        # Reaching here requires BOTH ai_mode=external AND external_ai_enabled=true
        # to be set explicitly - this codebase ships no concrete paid-API
        # implementation, so this remains a documented extension point.
        return ExternalProvider()
    return OllamaProvider(
        settings.ollama_base_url, settings.ollama_model, settings.ollama_timeout_seconds,
    )
