"""FastAPI app: real SSE streaming chat (routed through the Action Broker
for the deterministic lane), status, health, and the owner-facing
approval/kill-switch/audit surfaces.

Streaming is genuine: chunks are flushed as they become available, not
assembled first and revealed character-by-character.
"""
from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import Settings
from ..executive import GoalNotReadyError
from ..providers import NoProviderAvailable
from ..runtime import Runtime, build_runtime
from ..status import CapabilityStatus, registry
from ..voice import OpenWakeWordDetector, SherpaPiperTextToSpeech, SherpaWhisperSpeechToText


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


class CreateGoalRequest(BaseModel):
    statement: str
    success_metric: str | None = None
    budget: dict | None = None
    stop_conditions: list[str] = []
    priority: int = 3
    review_interval_seconds: int = 86400


class WakeWordCheckRequest(BaseModel):
    audio_base64: str  # base64-encoded 16-bit PCM mono samples


class TranscribeRequest(BaseModel):
    audio_base64: str
    sample_rate: int = 16000


class SpeakRequest(BaseModel):
    text: str
    speed: float = 1.0


def _sse(event: str, data: str) -> bytes:
    payload = json.dumps({"event": event, "data": data})
    return f"data: {payload}\n\n".encode()


def _check_voice_provider(name: str, provider) -> None:
    if provider.is_available():
        registry.set(name, CapabilityStatus.LIVE, "model loaded and verified")
    else:
        registry.set(name, CapabilityStatus.UNAVAILABLE, "model files not found or failed to load -- see core/RUNBOOK.md")


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime: Runtime = build_runtime(settings)
    wake_word_detector = OpenWakeWordDetector()
    speech_to_text = SherpaWhisperSpeechToText()
    text_to_speech = SherpaPiperTextToSpeech()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        registry.set("api.server", CapabilityStatus.LIVE, "uvicorn server running")
        # Real checks: each constructs/loads its model on first call, so
        # this genuinely proves (or disproves) usability at startup,
        # rather than assuming LIVE from configuration alone.
        _check_voice_provider("voice.wake_word", wake_word_detector)
        _check_voice_provider("voice.stt", speech_to_text)
        _check_voice_provider("voice.tts", text_to_speech)
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

    @app.post("/goals")
    async def create_goal(request: CreateGoalRequest) -> dict:
        goal = runtime.goals.create(
            request.statement, priority=request.priority,
            success_metric=request.success_metric, budget=request.budget,
            stop_conditions=request.stop_conditions,
            review_interval_seconds=request.review_interval_seconds,
        )
        return {"id": goal.id, "status": goal.status}

    @app.post("/goals/{goal_id}/activate")
    async def activate_goal(goal_id: str) -> dict:
        try:
            goal = runtime.goals.activate(goal_id)
        except GoalNotReadyError as exc:
            return {"error": str(exc)}
        return {"id": goal.id, "status": goal.status}

    @app.get("/goals")
    async def list_goals() -> list[dict]:
        return [
            {
                "id": g.id, "statement": g.statement, "status": g.status,
                "progress": g.progress, "priority": g.priority,
            }
            for g in runtime.goals.list_active()
        ]

    @app.post("/goals/review")
    async def review_goals() -> list[dict]:
        outcomes = await runtime.executive.run_review_cycle()
        return [
            {"goal_id": o.goal_id, "task_id": o.task_id, "error": o.error}
            for o in outcomes
        ]

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

    @app.post("/voice/wake-word/check")
    async def wake_word_check(request: WakeWordCheckRequest) -> dict:
        try:
            audio = np.frombuffer(base64.b64decode(request.audio_base64), dtype=np.int16)
            score = wake_word_detector.score(audio)
        except Exception as exc:  # noqa: BLE001 -- report honestly, don't crash the request
            raise HTTPException(status_code=503, detail=f"wake-word detector unavailable: {exc}") from exc
        return {"score": score, "detected": score >= 0.5}

    @app.post("/voice/stt/transcribe")
    async def stt_transcribe(request: TranscribeRequest) -> dict:
        try:
            audio = np.frombuffer(base64.b64decode(request.audio_base64), dtype=np.int16)
            text = speech_to_text.transcribe(audio, sample_rate=request.sample_rate)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=f"speech-to-text unavailable: {exc}") from exc
        return {"text": text}

    @app.post("/voice/tts/speak")
    async def tts_speak(request: SpeakRequest) -> Response:
        try:
            wav_bytes = text_to_speech.synthesize_to_wav_bytes(request.text, speed=request.speed)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=f"text-to-speech unavailable: {exc}") from exc
        return Response(content=wav_bytes, media_type="audio/wav")

    return app
