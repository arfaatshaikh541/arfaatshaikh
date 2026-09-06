"""FastAPI app: real SSE streaming chat (routed through the Action Broker
for the deterministic lane), status, health, and the owner-facing
approval/kill-switch/audit surfaces.

Streaming is genuine: chunks are flushed as they become available, not
assembled first and revealed character-by-character.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import Settings
from ..providers import NoProviderAvailable
from ..runtime import Runtime, build_runtime
from ..status import CapabilityStatus, registry


class ChatRequest(BaseModel):
    message: str


class ApprovalDecisionRequest(BaseModel):
    approved: bool
    decided_by: str = "owner"


def _sse(event: str, data: str) -> bytes:
    payload = json.dumps({"event": event, "data": data})
    return f"data: {payload}\n\n".encode()


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime: Runtime = build_runtime(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        registry.set("api.server", CapabilityStatus.LIVE, "uvicorn server running")
        yield
        registry.set("api.server", CapabilityStatus.UNAVAILABLE, "server stopped")

    app = FastAPI(title="AURA Core", version="0.2.0", lifespan=lifespan)
    app.state.runtime = runtime

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
            for c in runtime.memory.open_commitments()
        ]

    @app.get("/approvals")
    async def list_approvals() -> list[dict]:
        return [
            {
                "id": a.id, "action_type": a.action_type, "risk_tier": a.risk_tier,
                "reason": a.reason, "status": a.status, "created_at": a.created_at.isoformat(),
            }
            for a in runtime.approvals.pending()
        ]

    @app.post("/approvals/{approval_id}/decide")
    async def decide_approval(approval_id: str, decision: ApprovalDecisionRequest) -> dict:
        outcome = runtime.broker.resume_after_approval(
            approval_id, approved=decision.approved, decided_by=decision.decided_by,
        )
        return {"status": outcome.status.value, "message": outcome.message}

    @app.get("/audit")
    async def audit_entries() -> list[dict]:
        return [
            {
                "seq": e.seq, "timestamp": e.timestamp_iso, "actor": e.actor,
                "action_type": e.action_type, "risk_tier": e.risk_tier, "decision": e.decision,
                "approval_id": e.approval_id, "result_status": e.result_status,
                "result_message": e.result_message,
            }
            for e in runtime.audit.all_entries()
        ]

    @app.get("/audit/verify")
    async def audit_verify() -> dict:
        verification = runtime.audit.verify_chain()
        return {
            "valid": verification.valid,
            "broken_at_seq": verification.broken_at_seq,
            "entries_checked": verification.entries_checked,
        }

    @app.post("/kill-switch/engage")
    async def engage_kill_switch() -> dict:
        runtime.policy.engage_kill_switch()
        return {"kill_switch_engaged": True}

    @app.post("/kill-switch/disengage")
    async def disengage_kill_switch() -> dict:
        runtime.policy.disengage_kill_switch()
        return {"kill_switch_engaged": False}

    @app.post("/chat")
    async def chat(request: ChatRequest) -> StreamingResponse:
        async def stream() -> AsyncIterator[bytes]:
            action_request = runtime.triggers.resolve(request.message)
            if action_request is not None:
                outcome = runtime.broker.submit(action_request)
                yield _sse("lane", "deterministic")
                yield _sse("chunk", outcome.message)
                yield _sse("done", outcome.status.value)
                return

            yield _sse("lane", "model")
            try:
                async for chunk in runtime.model_router.generate_stream(request.message, history=[]):
                    yield _sse("chunk", chunk)
                yield _sse("done", "ok")
            except NoProviderAvailable as exc:
                yield _sse("error", str(exc))
                yield _sse("done", "unavailable")

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app
