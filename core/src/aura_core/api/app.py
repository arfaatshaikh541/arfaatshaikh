"""FastAPI app: real SSE streaming chat (routed through the Action Broker
for the deterministic lane), status, health, and the owner-facing
approval/kill-switch/audit surfaces.

Streaming is genuine: chunks are flushed as they become available, not
assembled first and revealed character-by-character.
"""
from __future__ import annotations

import asyncio
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
from ..executive import GoalNotReadyError, MandateNotReadyError, parse_status_query
from ..governance.action_broker import OutcomeStatus
from ..governance.risk_engine import ActionRequest
from ..identity import BackendRateLimitedError, InvalidBackendCredentialError, NotEnrolledError
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


class RunDirectiveRequest(BaseModel):
    directive: str


class ComposeSkillStepRequest(BaseModel):
    capability_name: str
    params_template: dict = {}
    on_failure: str = "abort"


class ComposeSkillRequest(BaseModel):
    name: str
    description: str
    domain: str
    steps: list[ComposeSkillStepRequest]


class RunSkillRequest(BaseModel):
    context: dict = {}


class PlanRequest(BaseModel):
    objective: str


class BackendAuthenticateRequest(BaseModel):
    pin: str


class SetBackendPinRequest(BaseModel):
    pin: str


class RecordOpportunityRequest(BaseModel):
    kind: str = "opportunity"
    category: str
    summary: str
    evidence: str = ""
    confidence: float = 0.5
    estimated_impact: str = "unknown"
    effort: str = "unknown"
    recommended_next_action: str = ""
    source: str = "owner"


class AskMemoryRequest(BaseModel):
    question: str


class EmbedRequest(BaseModel):
    text: str


class ClassifyEmailRequest(BaseModel):
    subject: str
    body: str


class WakeWordCheckRequest(BaseModel):
    audio_base64: str  # base64-encoded 16-bit PCM mono samples


class TranscribeRequest(BaseModel):
    audio_base64: str
    sample_rate: int = 16000


class SpeakRequest(BaseModel):
    text: str
    speed: float = 1.0


VOICE_SESSION_STATES = ("Idle", "ListeningForWake", "Awake", "Processing", "Speaking")
VOICE_PRIVACY_MODES = ("Normal", "WakeWordOnly", "FullMicOff")


class VoiceStateRequest(BaseModel):
    state: str


class VoicePrivacyRequest(BaseModel):
    mode: str


def _sse(event: str, data: str) -> bytes:
    payload = json.dumps({"event": event, "data": data})
    return f"data: {payload}\n\n".encode()


async def voice_state_events(poll_interval: float = 0.1) -> AsyncIterator[bytes]:
    """Event-driven push for the native shell's Voice Mode view (section
    6: "reflect real runtime events, never a polling timer with a fixed
    refresh interval"). The registry itself (status.py's StatusRegistry)
    is a plain in-memory dict with no subscribe/notify of its own, so
    this generator is the one place that watches it and turns "a value
    changed" into a genuine server push -- the client still just reads a
    stream and never issues a repeated GET. The internal poll_interval is
    an implementation detail of this generator, not something any client
    is asked to do.

    A module-level function (not a closure inside the /voice/state/stream
    route) on purpose: it never terminates on its own by design, which
    the in-process TestClient used by this test suite cannot stream
    incrementally -- TestClient runs an ASGI call to full completion
    before returning anything, so a route that only ever exposed this
    logic as an inline generator would be untestable without an
    unbounded hang. Being a standalone function lets tests drive it
    directly with asyncio.wait_for + aclose() instead, while the real
    /voice/state/stream endpoint below wraps it completely unchanged.
    """
    last_sent: str | None = None
    while True:
        record = registry.get("voice.session_state")
        state = record.detail if record is not None and record.status == CapabilityStatus.LIVE else "UNKNOWN"
        if state != last_sent:
            yield _sse("state", state)
            last_sent = state
        await asyncio.sleep(poll_interval)


def _format_mandate_report(report) -> str:
    """Plain-text rendering of a real MandateReport for chat/voice
    output -- every line traces back to real workstream/decision state
    (see MandateEngine.report()), never a fabricated summary."""
    lines = [f"{report.title} [{report.status}]"]
    lines.append(f"Counts: {report.counts}" if report.counts else "No workstreams yet.")
    for workstream in report.workstreams:
        lines.append(f"  [{workstream.bucket}] {workstream.statement} (progress={workstream.progress:.0%})")
        if workstream.latest_decision:
            lines.append(f"      last decision: {workstream.latest_decision}")
    if report.blockers:
        lines.append("Blockers:")
        lines.extend(f"  - {b}" for b in report.blockers)
    if report.next_actions:
        lines.append("Next actions:")
        lines.extend(f"  - {a}" for a in report.next_actions)
    return "\n".join(lines)


def _execute_plan_steps(broker, steps, requested_by: str) -> tuple[str, bool]:
    """Runs a UniversalPlanner-resolved plan's steps through the real
    Action Broker, one at a time, stopping (without cascading past it)
    the moment one needs owner approval -- "I've prepared X... shall I?"
    per section 19, never silently executing further steps behind that
    gate. Returns (voice-friendly message, True if execution paused for
    approval)."""
    lines: list[str] = []
    for step in steps:
        outcome = broker.submit(ActionRequest(action_type=step.capability_name, params=step.params, requested_by=requested_by))
        if outcome.status == OutcomeStatus.PENDING_APPROVAL:
            lines.append(f"I've prepared to {step.capability_name.replace('_', ' ').replace('.', ' ')}. {outcome.message} Shall I proceed?")
            return "\n".join(lines), True
        if outcome.status == OutcomeStatus.EXECUTED:
            lines.append(outcome.message)
        else:
            lines.append(f"I couldn't complete that: {outcome.message}")
            return "\n".join(lines), False
    return "\n".join(lines), False


def _format_gaps_for_voice(gaps) -> str:
    """A capability gap, spoken naturally -- the voice-facing sibling of
    the structured OBJECTIVE/MISSING_CAPABILITY/... object the CLI and
    API's /plan endpoint return verbatim for a human reading a screen.
    Never silence about what's missing; never a raw field dump either."""
    parts = []
    for gap in gaps:
        sentence = f"I don't have a way to {gap.missing_capability} yet."
        if gap.required_provider:
            sentence += f" That would need {gap.required_provider} connected."
        elif gap.required_tool:
            sentence += f" That would need {gap.required_tool}."
        parts.append(sentence)
    return " ".join(parts)


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

    async def require_backend_elevation(x_aura_backend_elevation: str | None = Header(default=None)) -> None:
        # The additional boundary Backend Mode requires beyond ordinary
        # device-session trust -- see identity/elevation.py's module
        # docstring for why a trusted device session is not, on its own,
        # sufficient to reach anything under /backend. This check is
        # independent of require_device_token and is never satisfied by
        # it: a request with a valid device token but no (or an expired/
        # revoked) elevation token is still rejected here. This is what
        # makes "voice commands cannot bypass backend authentication" and
        # "frontend manipulation cannot expose privileged data" true --
        # the boundary lives here, at the API layer, not in any UI state.
        if runtime.backend_elevation.verify(x_aura_backend_elevation) is None:
            raise HTTPException(status_code=401, detail="valid X-Aura-Backend-Elevation header required")

    backend_gated = [Depends(require_device_token), Depends(require_backend_elevation)]

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

    @app.get("/capabilities")
    async def list_capabilities(domain: str | None = None) -> list[dict]:
        items = runtime.capabilities.list_by_domain(domain) if domain else runtime.capabilities.list_all()
        return [
            {
                "name": c.name, "description": c.description, "domain": c.domain,
                "tools": list(c.tools), "verification": c.verification,
                "available": runtime.capabilities.is_handler_registered(c.name),
            }
            for c in items
        ]

    @app.get("/skills")
    async def list_skills() -> list[dict]:
        return [
            {"id": s.id, "name": s.name, "domain": s.domain, "steps": len(s.steps()), "created_by": s.created_by}
            for s in runtime.skills.list_all()
        ]

    @app.post("/skills", dependencies=gated)
    async def compose_skill(request: ComposeSkillRequest) -> dict:
        from ..skills import SkillStep, UnknownCapabilityError

        steps = [SkillStep(capability_name=s.capability_name, params_template=s.params_template, on_failure=s.on_failure) for s in request.steps]
        try:
            skill = runtime.skill_builder.compose(request.name, request.description, request.domain, steps, created_by="owner")
        except (UnknownCapabilityError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"id": skill.id, "name": skill.name, "steps": len(steps)}

    @app.post("/skills/{skill_id}/run", dependencies=gated)
    async def run_skill(skill_id: str, request: RunSkillRequest) -> dict:
        skill = runtime.skills.get(skill_id)
        if skill is None:
            raise HTTPException(status_code=404, detail=f"no such skill '{skill_id}'")
        result = runtime.skill_engine.run(skill, context=request.context)
        return {
            "skill_id": result.skill_id, "status": result.status,
            "steps": [
                {"capability_name": s.capability_name, "status": s.outcome.status.value, "message": s.outcome.message}
                for s in result.step_results
            ],
        }

    @app.post("/plan", dependencies=gated)
    async def plan_objective(request: PlanRequest) -> dict:
        result = await runtime.planner.plan(request.objective)
        return {
            "objective": result.objective,
            "fully_resolved": result.fully_resolved,
            "steps": [{"capability_name": s.capability_name, "params": s.params, "reasoning": s.reasoning} for s in result.steps],
            "gaps": [g.to_dict() for g in result.gaps],
        }

    @app.get("/interface/config")
    async def interface_config() -> dict:
        """Ungated on purpose: the native shell needs this before the
        owner has authenticated at all, to know what hotkey to register
        and what mode to boot into. None of these values are secrets --
        they're the same "which key combination toggles Backend Mode"
        information a config file would hold, just centralized here per
        docs/VOICE_FIRST_SECURE_INTERFACE.md rather than duplicated into
        the shell's own settings."""
        return {
            "default_interface_mode": settings.default_interface_mode,
            "backend_toggle_hotkey": settings.backend_toggle_hotkey,
            "require_backend_reauth": settings.require_backend_reauth,
            "backend_elevation_ttl_seconds": settings.backend_elevation_ttl_seconds,
        }

    @app.get("/identity/whoami", dependencies=gated)
    async def whoami(x_aura_device_token: str | None = Header(default=None)) -> dict:
        """The one deliberate exception to "GET endpoints are never
        gated": this endpoint's entire purpose is to answer "is the
        caller currently a recognized owner device," so it is the real
        substitute for a production startup authentication screen that
        this build has (no Windows Hello / hardware-backed factor is
        wired up here) -- the native shell calls this once at launch,
        after CompleteBootstrap(), to decide AuthRequired vs going
        straight to VoiceMode. `gated` already turns a missing/invalid
        token into a 401 whenever an owner is enrolled, so reaching this
        line with `runtime.enrollment.is_enrolled()` true means the token
        was already verified once by require_device_token; verifying it
        again here (rather than trusting that) costs nothing and means
        this handler never has to assume what the dependency did."""
        if not runtime.enrollment.is_enrolled():
            return {"enrolled": False, "owner_name": None, "device_label": None}
        device = runtime.enrollment.verify_token(x_aura_device_token) if x_aura_device_token else None
        return {
            "enrolled": True,
            "owner_name": runtime.enrollment.owner_display_name(),
            "device_label": device.label if device is not None else None,
        }

    @app.post("/backend/pin", dependencies=gated)
    async def set_backend_pin(request: SetBackendPinRequest) -> dict:
        """Setting the PIN only ever requires the ordinary owner/device
        session -- not backend elevation itself, since that would be
        circular for a first-time setup. Changing security configuration
        this way is still only reachable by an already-trusted device,
        never by voice/remote content (see /chat and the planner, which
        have no path to this endpoint)."""
        try:
            runtime.enrollment.set_owner_pin(request.pin)
        except NotEnrolledError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {"pin_configured": True}

    @app.post("/backend/authenticate")
    async def backend_authenticate(
        request: BackendAuthenticateRequest, x_aura_device_token: str | None = Header(default=None),
    ) -> dict:
        """The real Backend Mode entry point: a valid device token AND
        the owner's PIN are both required, independent of whether the
        caller already has an ordinary authenticated session. See
        identity/elevation.py for why."""
        if x_aura_device_token is None:
            raise HTTPException(status_code=401, detail="X-Aura-Device-Token header required")
        try:
            token = runtime.backend_elevation.authenticate(x_aura_device_token, request.pin)
        except BackendRateLimitedError as exc:
            raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": str(int(exc.retry_after_seconds) + 1)})
        except InvalidBackendCredentialError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
        session = runtime.backend_elevation.verify(token)
        return {"elevation_token": token, "expires_in_seconds": session.seconds_remaining()}

    @app.post("/backend/deauthenticate")
    async def backend_deauthenticate(x_aura_backend_elevation: str | None = Header(default=None)) -> dict:
        """Always succeeds (idempotent) -- leaving Backend Mode never
        requires proving anything, only ordinary state cleanup, per the
        product brief's explicit rule that returning to Voice Mode is
        never itself an authentication event."""
        if x_aura_backend_elevation:
            runtime.backend_elevation.revoke(x_aura_backend_elevation)
        return {"revoked": True}

    @app.get("/backend/session")
    async def backend_session_status(x_aura_backend_elevation: str | None = Header(default=None)) -> dict:
        session = runtime.backend_elevation.verify(x_aura_backend_elevation)
        if session is None:
            raise HTTPException(status_code=401, detail="no active backend elevation")
        return {"active": True, "seconds_remaining": session.seconds_remaining()}

    @app.get("/backend/diagnostics", dependencies=backend_gated)
    async def backend_diagnostics() -> dict:
        """Real system state only -- see diagnostics/health.py. Nothing
        here is a fabricated activity log; every field is computed from
        the real audit chain and the real Security Guardian."""
        from ..diagnostics import collect_diagnostics

        report = collect_diagnostics(runtime.audit, runtime.guardian)
        return {
            "audit_chain_valid": report.audit_chain_valid,
            "audit_entries_checked": report.audit_entries_checked,
            "recent_guardian_events": report.recent_guardian_events,
            "capability_status": report.capability_status,
        }

    @app.get("/backend/audit", dependencies=backend_gated)
    async def backend_audit(after_seq: int = 0, limit: int = 100) -> list[dict]:
        entries = runtime.audit.entries_after(after_seq)[:limit]
        return [
            {
                "seq": e.seq, "timestamp": e.timestamp_iso, "actor": e.actor, "action_type": e.action_type,
                "risk_tier": e.risk_tier, "decision": e.decision, "result_status": e.result_status,
                "result_message": e.result_message,
            }
            for e in entries
        ]

    @app.get("/opportunities")
    async def list_opportunities(kind: str | None = None) -> list[dict]:
        return [
            {
                "id": o.id, "kind": o.kind, "category": o.category, "summary": o.summary,
                "evidence": o.evidence, "confidence": o.confidence, "estimated_impact": o.estimated_impact,
                "effort": o.effort, "recommended_next_action": o.recommended_next_action,
                "source": o.source, "status": o.status,
            }
            for o in runtime.opportunities.list_open(kind=kind)
        ]

    @app.post("/opportunities", dependencies=gated)
    async def record_opportunity(request: RecordOpportunityRequest) -> dict:
        from ..opportunities import OpportunityInput

        record = runtime.opportunities.record(OpportunityInput(**request.model_dump()))
        return {"id": record.id, "status": record.status}

    @app.post("/opportunities/{opportunity_id}/status", dependencies=gated)
    async def set_opportunity_status(opportunity_id: str, status: str) -> dict:
        try:
            runtime.opportunities.set_status(opportunity_id, status)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"id": opportunity_id, "status": status}

    @app.post("/mandates/run", dependencies=gated)
    async def run_mandate_directive(request: RunDirectiveRequest) -> dict:
        """"Run Gridkeep" without a generic goal-form, per section 10 --
        see MandateEngine.create_from_directive() for why KPIs/
        constraints are still required, honestly, before /activate."""
        from ..executive import UnrecognizedDirectiveError

        try:
            mandate = runtime.mandates.create_from_directive(request.directive)
        except UnrecognizedDirectiveError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"id": mandate.id, "status": mandate.status, "title": mandate.title, "mission": mandate.mission}

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

    @app.post("/model/embed", dependencies=gated)
    async def model_embed(request: EmbedRequest) -> dict:
        try:
            vector = await runtime.model_router.embed(request.text)
        except NoProviderAvailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"embedding": vector, "dimensions": len(vector)}

    @app.post("/email/classify", dependencies=gated)
    async def email_classify(request: ClassifyEmailRequest) -> dict:
        from ..email_intent import classify_message_intent

        category = await classify_message_intent(request.subject, request.body, runtime.model_router)
        return {"category": category}

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

            company = parse_status_query(request.message)
            if company is not None:
                # An executive-status question ("What's happening with
                # Gridkeep?") must be answered from real mandate/
                # workstream state, never generic chatbot advice
                # (section 22 of the product brief) -- resolved here,
                # deterministically, before ever reaching the model.
                yield _sse("lane", "mandate_status")
                mandate = runtime.mandates.find_by_company(company)
                if mandate is None:
                    yield _sse("chunk", f"No mandate found matching '{company}'.")
                    yield _sse("done", "not_found")
                    return
                report = runtime.mandates.report(mandate.id, runtime.goals, runtime.memory)
                yield _sse("chunk", _format_mandate_report(report))
                yield _sse("done", "ok")
                return

            # Voice/chat as a first-class channel into the same
            # general-purpose planner/execution architecture every other
            # interface uses (never a hardcoded voice-command list): try
            # to resolve the request into real, currently-available
            # capabilities before ever falling back to a purely
            # conversational model response. A request the planner
            # cannot resolve to anything concrete (including every
            # request in AURA_ENV=test, which has no real model to plan
            # with) falls through to the model exactly as before --
            # informational/conversational questions are not forced
            # through the planner just because they didn't match a
            # deterministic trigger.
            plan_result = await runtime.planner.plan(request.message)
            if plan_result.fully_resolved:
                yield _sse("lane", "planner")
                message, needs_approval = _execute_plan_steps(runtime.broker, plan_result.steps, "owner")
                yield _sse("chunk", message)
                yield _sse("done", "pending_approval" if needs_approval else "ok")
                return
            if plan_result.steps and plan_result.gaps:
                # A mixed plan (some of the request is doable, some
                # isn't) -- report both halves honestly rather than
                # silently doing only the resolvable part or discarding
                # the whole request.
                yield _sse("lane", "planner")
                message, needs_approval = _execute_plan_steps(runtime.broker, plan_result.steps, "owner")
                gap_message = _format_gaps_for_voice(plan_result.gaps)
                yield _sse("chunk", f"{message}\n{gap_message}")
                yield _sse("done", "pending_approval" if needs_approval else "partial")
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

    @app.get("/voice/state/stream")
    async def voice_state_stream() -> StreamingResponse:
        return StreamingResponse(voice_state_events(), media_type="text/event-stream")

    @app.get("/voice/privacy")
    async def get_voice_privacy() -> dict:
        # Ungated, same reasoning as GET /voice/state: reading the current
        # privacy mode exposes no capability an unauthenticated local
        # caller could cause harm with, and the WPF shell needs to read it
        # before the owner has authenticated at all (Voice Mode's mute
        # control must reflect real state immediately on launch).
        record = registry.get("voice.privacy_mode")
        mode = record.detail if record is not None and record.status == CapabilityStatus.LIVE else "Normal"
        return {"mode": mode}

    @app.post("/voice/privacy", dependencies=gated)
    async def set_voice_privacy(request: VoicePrivacyRequest) -> dict:
        # The real backend half of section 17's "FULL MIC OFF vs.
        # WAKE-WORD-ONLY" gating: this is the value AuraVoice.Windows.Host
        # polls and hands to WindowsVoicePipeline.PrivacyGate, which is
        # what actually opens/closes the real microphone hardware --
        # this endpoint itself only records the requested mode, exactly
        # like /voice/state records the reported session state.
        if request.mode not in VOICE_PRIVACY_MODES:
            raise HTTPException(status_code=422, detail=f"unknown voice privacy mode '{request.mode}'")
        registry.set("voice.privacy_mode", CapabilityStatus.LIVE, request.mode)
        return {"mode": request.mode}

    return app
