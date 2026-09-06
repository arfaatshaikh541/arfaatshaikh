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


class FreezeRequest(BaseModel):
    reason: str


class EnqueueTaskRequest(BaseModel):
    task_type: str
    payload: dict = {}
    depends_on: list[str] = []
    max_attempts: int = 3


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

    @app.get("/guardian/events")
    async def guardian_events() -> list[dict]:
        return [
            {
                "id": e.id, "detected_at": e.detected_at.isoformat(),
                "rule_name": e.rule_name, "detail": e.detail, "action_taken": e.action_taken,
            }
            for e in runtime.guardian.recent_events()
        ]

    @app.post("/guardian/freeze")
    async def guardian_freeze(request: FreezeRequest) -> dict:
        event = runtime.guardian.freeze(request.reason)
        return {"id": event.id, "action_taken": event.action_taken}

    @app.get("/tasks")
    async def list_tasks(status: str | None = None) -> list[dict]:
        records = runtime.tasks.list_by_status(status) if status else [
            t for s in ("QUEUED", "RUNNING", "WAITING", "BLOCKED", "NEEDS_APPROVAL", "RETRYING")
            for t in runtime.tasks.list_by_status(s)
        ]
        return [
            {
                "id": t.id, "task_type": t.task_type, "status": t.status,
                "attempts": t.attempts, "max_attempts": t.max_attempts,
                "created_at": t.created_at.isoformat(),
            }
            for t in records
        ]

    @app.post("/tasks")
    async def enqueue_task(request: EnqueueTaskRequest) -> dict:
        task = runtime.tasks.enqueue(
            request.task_type, request.payload,
            depends_on=request.depends_on, max_attempts=request.max_attempts,
        )
        return {"id": task.id, "status": task.status}

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
