"""Real Ollama provider.

This talks to a real local Ollama server over HTTP using its documented
streaming chat API (NDJSON-over-HTTP, one JSON object per line). It has not
been exercised against a live Ollama instance in this build environment —
there is no GPU/Ollama installation here to verify against — so its status
is READY_TO_CONNECT, not LIVE, until you run it against your own Ollama
install and it passes a real health check (see core/RUNBOOK.md). The code
itself is real, not a stub: point AURA_OLLAMA_HOST at a running Ollama and
it will make genuine HTTP calls.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx


class OllamaProvider:
    name = "ollama"

    def __init__(self, host: str, model: str, timeout_seconds: float = 120.0) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self._host}/api/tags")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def generate_stream(self, prompt: str, history: list[dict[str, str]]) -> AsyncIterator[str]:
        messages = [*history, {"role": "user", "content": prompt}]
        payload = {"model": self._model, "messages": messages, "stream": True}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream("POST", f"{self._host}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if chunk.get("done"):
                        break


class OllamaEmbeddingProvider:
    """Real Ollama embeddings via its documented /api/embeddings endpoint
    (e.g. the `nomic-embed-text` model). Same "code is real, status is
    honest until health-checked against a live install" posture as
    OllamaProvider above -- there is no GPU/Ollama install in this build
    environment to verify against."""

    name = "ollama-embedding"

    def __init__(self, host: str, model: str, timeout_seconds: float = 30.0) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self._host}/api/tags")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def embed(self, text: str) -> list[float]:
        payload = {"model": self._model, "prompt": text}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._host}/api/embeddings", json=payload)
            response.raise_for_status()
            return response.json()["embedding"]
