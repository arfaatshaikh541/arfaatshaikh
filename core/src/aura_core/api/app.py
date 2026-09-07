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
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..config import Settings
from ..executive import GoalNotReadyError, MandateNotReadyError
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


class CreateMandateRequest(BaseModel):
    title: str
    mission: str
    objectives: list[str] = []
    kpis: list[dict] = []
    constraints: list[str] = []
    priority: int = 3
    observation_interval_seconds: int = 3600


class AskMemoryRequest(BaseModel):
    question: str


class WakeWordCheckRequest(BaseModel):
    audio_base64: str  # base64-encoded 16-bit PCM mono samples


class TranscribeRequest(BaseModel):
    audio_base64: str
    sample_rate: int = 16000


class SpeakRequest(BaseModel):
    text: str
    speed: float = 1.0


VOICE_SESSION_STATES = ("Idle", "ListeningForWake", "Awake", "Processing", "Speaking")


class VoiceStateRequest(BaseModel):
    state: str


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

    async def require_device_token(x_aura_device_token: str | None = Header(default=None)) -> None:
        # Every state-changing endpoint (every POST in this app) is
        # gated once an owner has actually enrolled (section 9's device
        # trust) -- before enrollment there is no owner identity to check
        # a caller against, so every endpoint stays exactly as open as it
        # always was, matching every pre-existing test that never calls
        # `aura enroll` first. Read-only GET endpoints are never gated:
        # they expose no capability an unauthenticated local caller could
        # cause harm with.
        if runtime.enrollment.is_enrolled():
            if x_aura_device_token is None or runtime.enrollment.verify_token(x_aura_device_token) is None:
                raise HTTPException(status_code=401, detail="valid X-Aura-Device-Token header required")

    gated = [Depends(require_device_token)]

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/status")
    async def status() -> dict:
        return registry.snapshot()

    @app.get("/connectors")
    async def list_connectors() -> list[dict]:
        # A health check can do genuinely blocking work (BrowserConnector
        # launches a real browser via Playwright's *sync* API, which
        # raises outright if called on a thread already running an asyncio
        # event loop -- as this endpoint's own thread is). Running it in
        # FastAPI's thread pool avoids that, the same way FastAPI already
        # handles a plain `def` path operation.
        await run_in_threadpool(runtime.connectors.refresh_all)
        return [
            {
                "name": m.name, "auth_method": m.auth_method,
                "required_credentials": m.required_credentials,
                "capabilities": m.capabilities, "notes": m.notes,
                "status": registry.snapshot().get(f"connector.{m.name}"),
            }
            for m in runtime.connectors.manifests()
        ]

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

    @app.post("/approvals/{approval_id}/decide", dependencies=gated)
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

    @app.post("/kill-switch/engage", dependencies=gated)
    async def engage_kill_switch() -> dict:
        runtime.policy.engage_kill_switch()
        return {"kill_switch_engaged": True}

    @app.post("/kill-switch/disengage", dependencies=gated)
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

    @app.post("/guardian/freeze", dependencies=gated)
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

    @app.post("/tasks", dependencies=gated)
    async def enqueue_task(request: EnqueueTaskRequest) -> dict:
        task = runtime.tasks.enqueue(
            request.task_type, request.payload,
            depends_on=request.depends_on, max_attempts=request.max_attempts,
        )
        return {"id": task.id, "status": task.status}

    @app.post("/goals", dependencies=gated)
    async def create_goal(request: CreateGoalRequest) -> dict:
        goal = runtime.goals.create(
            request.statement, priority=request.priority,
            success_metric=request.success_metric, budget=request.budget,
            stop_conditions=request.stop_conditions,
            review_interval_seconds=request.review_interval_seconds,
        )
        return {"id": goal.id, "status": goal.status}

    @app.post("/goals/{goal_id}/activate", dependencies=gated)
    async def activate_goal(goal_id: str) -> dict:
        try:
            goal = runtime.goals.activate(goal_id)
        except GoalNotReadyError as exc:
            return {"error": str(exc)}
        return {"id": goal.id, "status": goal.status}

    @app.post("/goals/{goal_id}/mandate/{mandate_id}", dependencies=gated)
    async def set_goal_mandate(goal_id: str, mandate_id: str) -> dict:
        try:
            runtime.goals.set_mandate(goal_id, mandate_id)
        except GoalNotReadyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"goal_id": goal_id, "mandate_id": mandate_id}

    @app.get("/goals")
    async def list_goals() -> list[dict]:
        return [
            {
                "id": g.id, "statement": g.statement, "status": g.status,
                "progress": g.progress, "priority": g.priority,
            }
            for g in runtime.goals.list_active()
        ]

    @app.post("/goals/review", dependencies=gated)
    async def review_goals() -> list[dict]:
        outcomes = await runtime.executive.run_review_cycle()
        return [
            {"goal_id": o.goal_id, "task_id": o.task_id, "error": o.error}
            for o in outcomes
        ]

    @app.post("/mandates", dependencies=gated)
    async def create_mandate(request: CreateMandateRequest) -> dict:
        mandate = runtime.mandates.create(
            request.title, request.mission, priority=request.priority,
            objectives=request.objectives, kpis=request.kpis, constraints=request.constraints,
            observation_interval_seconds=request.observation_interval_seconds,
        )
        return {"id": mandate.id, "status": mandate.status}

    @app.post("/mandates/{mandate_id}/activate", dependencies=gated)
    async def activate_mandate(mandate_id: str) -> dict:
        try:
            mandate = runtime.mandates.activate(mandate_id)
        except MandateNotReadyError as exc:
            return {"error": str(exc)}
        return {"id": mandate.id, "status": mandate.status}

    @app.get("/mandates")
    async def list_mandates() -> list[dict]:
        return [
            {"id": m.id, "title": m.title, "status": m.status, "priority": m.priority}
            for m in runtime.mandates.list_active()
        ]

    @app.get("/mandates/{mandate_id}/report")
    async def mandate_report(mandate_id: str) -> dict:
        try:
            report = runtime.mandates.report(mandate_id, runtime.goals, runtime.memory)
        except MandateNotReadyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {
            "mandate_id": report.mandate_id, "title": report.title, "status": report.status,
            "generated_at": report.generated_at.isoformat(), "counts": report.counts,
            "workstreams": [
                {
                    "goal_id": w.goal_id, "statement": w.statement, "status": w.status,
                    "bucket": w.bucket, "progress": w.progress, "latest_decision": w.latest_decision,
                }
                for w in report.workstreams
            ],
            "next_actions": report.next_actions, "blockers": report.blockers,
        }

    @app.post("/loop/run-once", dependencies=gated)
    async def loop_run_once() -> list[dict]:
        outcomes = await runtime.operating_loop.run_cycle_once()
        return [
            {"task_id": o.task_id, "task_type": o.task_type, "outcome": o.outcome, "detail": o.detail}
            for o in outcomes
        ]

    @app.get("/memory/search")
    async def memory_search(q: str, limit: int = 10) -> list[dict]:
        results = runtime.memory.search(q, limit=limit, world_model=runtime.world_model)
        return [
            {
                "kind": r.kind, "id": r.id, "text": r.text, "score": r.score,
                "created_at": r.created_at.isoformat(), "entity_ids": r.entity_ids,
            }
            for r in results
        ]

    @app.post("/memory/ask", dependencies=gated)
    async def memory_ask(request: AskMemoryRequest) -> dict:
        from ..memory import answer_question

        result = await answer_question(
            request.question, runtime.memory, runtime.model_router, world_model=runtime.world_model,
        )
        return {
            "question": result.question, "answer": result.answer,
            "error": result.error, "context_used": result.context_used,
        }

    @app.post("/chat", dependencies=gated)
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

    @app.post("/voice/wake-word/check", dependencies=gated)
    async def wake_word_check(request: WakeWordCheckRequest) -> dict:
        try:
            audio = np.frombuffer(base64.b64decode(request.audio_base64), dtype=np.int16)
            score = wake_word_detector.score(audio)
        except Exception as exc:  # noqa: BLE001 -- report honestly, don't crash the request
            raise HTTPException(status_code=503, detail=f"wake-word detector unavailable: {exc}") from exc
        return {"score": score, "detected": score >= 0.5}

    @app.post("/voice/stt/transcribe", dependencies=gated)
    async def stt_transcribe(request: TranscribeRequest) -> dict:
        try:
            audio = np.frombuffer(base64.b64decode(request.audio_base64), dtype=np.int16)
            text = speech_to_text.transcribe(audio, sample_rate=request.sample_rate)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=f"speech-to-text unavailable: {exc}") from exc
        return {"text": text}

    @app.post("/voice/tts/speak", dependencies=gated)
    async def tts_speak(request: SpeakRequest) -> Response:
        try:
            wav_bytes = text_to_speech.synthesize_to_wav_bytes(request.text, speed=request.speed)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=f"text-to-speech unavailable: {exc}") from exc
        return Response(content=wav_bytes, media_type="audio/wav")

    @app.get("/voice/state")
    async def get_voice_state() -> dict:
        # Real cross-process visibility, not a log line only the owner's
        # terminal can see (section 8's "privacy-visible status"): the
        # voice host process pushes its VoiceSessionController state here
        # on every transition, and any client on this machine -- a future
        # tray icon, `aura status`, this endpoint directly -- can read the
        # current state without any direct reference to that process.
        record = registry.get("voice.session_state")
        if record is None or record.status != CapabilityStatus.LIVE:
            return {"state": "UNKNOWN", "detail": "no voice host has reported a state yet"}
        return {"state": record.detail, "reported_at": record.checked_at.isoformat()}

    @app.post("/voice/state", dependencies=gated)
    async def set_voice_state(request: VoiceStateRequest) -> dict:
        if request.state not in VOICE_SESSION_STATES:
            raise HTTPException(status_code=422, detail=f"unknown voice state '{request.state}'")
        registry.set("voice.session_state", CapabilityStatus.LIVE, request.state)
        return {"state": request.state}

    return app
