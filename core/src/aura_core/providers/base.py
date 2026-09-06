"""Model provider protocol.

A provider streams response chunks for a prompt. This is the only interface
the rest of the system depends on, so swapping/adding providers (a coding
model, a vision model, a second local model) never touches calling code —
per docs/architecture/07-model-routing.md.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol


class ModelProvider(Protocol):
    name: str

    async def is_available(self) -> bool:
        """Real health check — must actually contact the provider, never
        assume availability from configuration alone."""
        ...

    def generate_stream(self, prompt: str, history: list[dict[str, str]]) -> AsyncIterator[str]:
        """Yield response text incrementally as it is produced."""
        ...
