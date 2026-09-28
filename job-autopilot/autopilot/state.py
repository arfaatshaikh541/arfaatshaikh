"""Application state machine. All transitions go through :func:`transition`."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Application, ApplicationEvent, ApplicationEvidence, ApplicationStatus as S, utcnow


class IllegalTransition(Exception):
    pass


ALLOWED: dict[S, set[S]] = {
    S.DISCOVERED: {S.EVALUATED, S.SKIPPED},
    S.EVALUATED: {S.QUEUED, S.SKIPPED, S.NEEDS_REVIEW},
    S.NEEDS_REVIEW: {S.QUEUED, S.SKIPPED},
    S.QUEUED: {S.STARTED, S.SKIPPED},
    S.STARTED: {S.FORM_COMPLETED, S.VERIFICATION_REQUIRED, S.NEEDS_REVIEW, S.SKIPPED, S.FAILED, S.QUEUED},
    S.FORM_COMPLETED: {S.SUBMITTING, S.DRY_RUN_COMPLETE, S.VERIFICATION_REQUIRED, S.NEEDS_REVIEW, S.SKIPPED,
                       S.FAILED, S.QUEUED},
    # Once SUBMITTING, the only exits are evidence-backed or explicitly uncertain.
    S.SUBMITTING: {S.SUBMITTED, S.UNKNOWN, S.FAILED, S.VERIFICATION_REQUIRED},
    # (SUBMITTING -> VERIFICATION_REQUIRED: a challenge appeared after the submit click.)
    S.SUBMITTED: {S.VERIFIED},
    S.VERIFIED: set(),
    S.DRY_RUN_COMPLETE: set(),
    S.SKIPPED: {S.QUEUED},  # manual override only
    # Retrying is always a deliberate action (admin "retry" or scheduler for pre-submit failures).
    S.FAILED: {S.QUEUED},
    # Held for a human. Resume returns to the step that was interrupted, only after the agent has
    # verified that the challenge is cleared. A post-submit challenge resumes into SUBMITTING
    # (outcome detection) and never re-clicks submit.
    S.VERIFICATION_REQUIRED: {S.STARTED, S.FORM_COMPLETED, S.SUBMITTING, S.VERIFICATION_TIMEOUT, S.UNKNOWN,
                              S.FAILED, S.QUEUED},
    S.VERIFICATION_TIMEOUT: {S.QUEUED, S.UNKNOWN, S.FAILED},
    # UNKNOWN is resolved by a human: confirm submitted (with evidence) or mark failed.
    S.UNKNOWN: {S.SUBMITTED, S.FAILED},
}

TERMINAL_SUCCESS = {S.SUBMITTED, S.VERIFIED}
EVIDENCE_REQUIRED = {S.SUBMITTED, S.VERIFIED}


def transition(
    s: Session,
    app: Application,
    to: S,
    *,
    reconciled_not_submitted: bool = False,
    event: str | None = None,
    worker_id: str | None = None,
    reason: str | None = None,
    url: str | None = None,
    duration_ms: int | None = None,
    detail: dict[str, Any] | None = None,
) -> ApplicationEvent:
    """Validate and apply a state transition, recording an event in the same transaction."""
    frm = S(app.status)
    if to not in ALLOWED[frm]:
        raise IllegalTransition(f"{frm.value} -> {to.value} is not allowed")
    if to == S.QUEUED and app.submit_clicked_at is not None and not reconciled_not_submitted:
        raise IllegalTransition(
            "Submit was already clicked for this application; it can only be re-queued after a human "
            "reconciles it as NOT submitted (duplicate-submission protection)")
    if to in EVIDENCE_REQUIRED:
        s.flush()
        from .evidence import SUBMISSION_PROOF_KINDS

        has_evidence = s.scalar(
            select(ApplicationEvidence.id)
            .where(ApplicationEvidence.application_id == app.id, ApplicationEvidence.kind.in_(SUBMISSION_PROOF_KINDS))
            .limit(1)
        )
        if not has_evidence:
            raise IllegalTransition(f"{to.value} requires stored submission evidence")
    if app.mode == "DRY_RUN" and to in {S.SUBMITTING, S.SUBMITTED, S.VERIFIED}:
        raise IllegalTransition("DRY_RUN applications can never be submitted")
    now = utcnow()
    app.status = to.value
    app.updated_at = now
    if reason is not None:
        app.status_reason = reason
    if to == S.QUEUED:
        app.queued_at = now
    elif to == S.STARTED:
        app.started_at = now
    elif to == S.SUBMITTING and app.submit_clicked_at is None:
        # Committed together with SUBMITTING, i.e. BEFORE the click, so a crash can never lose it.
        app.submit_clicked_at = now
    elif to == S.SUBMITTED:
        app.submitted_at = app.submitted_at or now
    if to in {S.SUBMITTED, S.VERIFIED, S.DRY_RUN_COMPLETE, S.FAILED, S.UNKNOWN, S.SKIPPED, S.VERIFICATION_REQUIRED, S.VERIFICATION_TIMEOUT,
              S.NEEDS_REVIEW}:
        app.finished_at = now
    ev = ApplicationEvent(
        application_id=app.id,
        event=event or f"status:{to.value}",
        from_status=frm.value,
        to_status=to.value,
        worker_id=worker_id,
        url=url,
        duration_ms=duration_ms,
        detail={**(detail or {}), **({"reason": reason} if reason else {})},
    )
    s.add(ev)
    s.flush()
    return ev


def log_event(
    s: Session,
    app: Application,
    event: str,
    *,
    worker_id: str | None = None,
    url: str | None = None,
    duration_ms: int | None = None,
    detail: dict[str, Any] | None = None,
) -> ApplicationEvent:
    """Record a non-transition event (navigation, upload, field fill, ...)."""
    ev = ApplicationEvent(
        application_id=app.id, event=event, worker_id=worker_id, url=url, duration_ms=duration_ms, detail=detail or {}
    )
    s.add(ev)
    s.flush()
    return ev
