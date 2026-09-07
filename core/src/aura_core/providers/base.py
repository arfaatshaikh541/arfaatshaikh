"""Model provider protocol.

A provider streams response chunks for a prompt. This is the only interface
the rest of the system depends on, so swapping/adding providers (a coding
model, a vision model, a second local model) never touches calling code —
per docs/architecture/07-model-routing.md.
"""
from __future__ import annotations

import enum
from collections.abc import AsyncIterator
from typing import Protocol


class ModelRole(str, enum.Enum):
    """The capability-class split docs/architecture/07-model-routing.md
    describes, narrowed to the three this build actually routes between
    (the full seven-class table -- coding/vision/frontier-reasoning/etc
    -- needs providers this codebase has no credentials for). REASONING
    is the default and the only role that existed before this: every
    caller that doesn't pass a role keeps its exact previous behavior."""

    REASONING = "reasoning"  # the general-purpose local model -- the only role that existed before
    FAST = "fast"  # high-volume, low-complexity: classification, routing, simple extraction
    EMBEDDING = "embedding"  # semantic memory retrieval -- vectors, not text, so a separate protocol


class ModelProvider(Protocol):
    name: str

    async def is_available(self) -> bool:
        """Real health check — must actually contact the provider, never
        assume availability from configuration alone."""
        ...

    def generate_stream(self, prompt: str, history: list[dict[str, str]]) -> AsyncIterator[str]:
        """Yield response text incrementally as it is produced."""
        ...


class EmbeddingProvider(Protocol):
    name: str

    async def is_available(self) -> bool:
        """Real health check — must actually contact the provider, never
        assume availability from configuration alone."""
        ...

    async def embed(self, text: str) -> list[float]:
        """Return a real embedding vector for `text`."""
        ...
