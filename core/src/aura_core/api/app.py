"""FastAPI app: real SSE streaming chat, status, and health endpoints.

Streaming is genuine: each chunk yielded by the model provider (or the
single deterministic-action message) is flushed to the client as it
becomes available, not assembled first and revealed character-by-character.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..actions import build_default_registry
from ..config import Settings, load_settings
from ..memory import MemoryStore
from ..providers import ModelRouter, NoProviderAvailable, OllamaProvider
from ..status import CapabilityStatus, registry


class ChatRequest(BaseModel):
    message: str


def _sse(event: str, data: str) -> bytes:
    payload = json.dumps({"event": event, "data": data})
    return f"data: {payload}\n\n".encode()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    memory = MemoryStore(settings.database_url)
    registry.set("memory.store", CapabilityStatus.LIVE, f"connected to {settings.database_url}")

    actions = build_default_registry(memory)

    ollama = OllamaProvider(host=settings.ollama_host, model=settings.ollama_model)
    router = ModelRouter(primary=ollama, allow_test_fallback=settings.allow_test_provider)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        registry.set("api.server", CapabilityStatus.LIVE, "uvicorn server running")
        yield
        registry.set("api.server", CapabilityStatus.UNAVAILABLE, "server stopped")

    app = FastAPI(title="AURA Core", version="0.1.0", lifespan=lifespan)
    app.state.memory = memory
    app.state.actions = actions
    app.state.router = router

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/status")
    async def status() -> dict:
        return registry.snapshot()

    @app.get("/commitments")
    async def commitments() -> list[dict]:
        return [
            {"id": c.id, "description": c.description, "due_at": c.due_at.isoformat() if c.due_at else None}
            for c in memory.open_commitments()
        ]

    @app.post("/chat")
    async def chat(request: ChatRequest) -> StreamingResponse:
        async def stream() -> AsyncIterator[bytes]:
            action_result = actions.dispatch(request.message)
            if action_result is not None:
                yield _sse("lane", "deterministic")
                yield _sse("chunk", action_result.message)
                yield _sse("done", action_result.status.value)
                return

            yield _sse("lane", "model")
            try:
                async for chunk in router.generate_stream(request.message, history=[]):
                    yield _sse("chunk", chunk)
                yield _sse("done", "ok")
            except NoProviderAvailable as exc:
                yield _sse("error", str(exc))
                yield _sse("done", "unavailable")

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app
