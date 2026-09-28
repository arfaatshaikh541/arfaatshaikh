"""Real application execution against the employer's hosted application form.

State discipline:
  QUEUED -> STARTED (row-locked, one worker only)
  STARTED -> FORM_COMPLETED after every required field on every step is filled from grounded answers
  FORM_COMPLETED -> SUBMITTING is COMMITTED (with submit_clicked_at) before the submit click
  SUBMITTING -> SUBMITTED only with stored confirmation evidence, else UNKNOWN / FAILED
  Any step -> VERIFICATION_REQUIRED when a challenge appears; the browser is held for a human and the
  workflow resumes at the interrupted step only after the challenge is verified cleared, otherwise
  VERIFICATION_TIMEOUT. An application whose submit was clicked is never re-queued automatically.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

from playwright.sync_api import BrowserContext, Error as PWError, Page, TimeoutError as PWTimeout
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import lifecycle
from ..ai.providers import ProviderHandle
from ..audit import record_error
from ..browser.agent import BrowserAgent, TargetError, field_has_value
from ..browser.detect import CONFIRM_TEXT_RE, detect_challenge, visible_errors, wait_for_outcome
from ..browser.engine import BrowserManager
from ..browser.forms import DetectedField, FillError, combobox_options, extract_fields, fill_field
from ..config import get_config
from ..db import session_scope
from ..evidence import add_evidence
from ..models import (
    Application, ApplicationAnswer, ApplicationQuestion, ApplicationStatus as S, CandidateProfile, CVVersion, Job,
    VerificationRequest, utcnow,
)
from ..profile.service import knowledge, read_cv, rules as load_rules
from ..questions.engine import Answer, AnswerEngine, JobContext
from ..questions.grounding import make_narrative_fn
from ..security.destinations import DestinationRefused, check_destination, live_submissions_allowed
from ..security.redact import redact
from ..settings_store import AutomationSettings, load
from ..state import log_event, transition
from ..verification import gateway
from ..verification.session_server import SessionServer

log = logging.getLogger(__name__)
MAX_STEPS = 8
_STAGE = {S.STARTED: "pre_fill", S.FORM_COMPLETED: "pre_submit", S.SUBMITTING: "post_submit"}


class TransientApplyError(Exception):
    pass


class ApplicationTimeout(Exception):
    pass


@dataclass
class RunResult:
    status: str
    reason: str | None = None


def _claim(s: Session, app_id: int, worker_id: str, session_id: str) -> Application | None:
    app = s.scalar(select(Application).where(Application.id == app_id).with_for_update(skip_locked=True))
    if app is None or app.status != S.QUEUED.value:
        return None
    if app.submit_clicked_at is not None:  # belt and braces: the state machine already forbids this
        return None
    app.worker_id = worker_id
    app.browser_session_id = session_id
    transition(s, app, S.STARTED, worker_id=worker_id, event="worker_started")
    return app


def _screenshot(page: Page) -> bytes | None:
    try:
        return page.screenshot(full_page=True, timeout=15000)
    except Exception:
        return None


def _norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


class _Held(Exception):
    """Verification ended without completion; carries the final result."""

    def __init__(self, result: RunResult):
        self.result = result


class ApplicationRunner:
    def __init__(self, browsers: BrowserManager, worker_id: str, session_server: SessionServer | None = None,
                 keepalive: Callable[[], None] | None = None):
        self.browsers = browsers
        self.worker_id = worker_id
        self.session_server = session_server
        self.keepalive = keepalive
        self._submitting = False
        self._crashed = False
        self._deadline = 0.0

    def run(self, app_id: int) -> RunResult:
        with self.browsers.context() as (ctx, sid):
            with session_scope() as s:
                app = _claim(s, app_id, self.worker_id, sid)
                if app is None:
                    return RunResult("NOT_CLAIMED", "Application not in QUEUED state or locked by another worker")
                auto = load(s, AutomationSettings)
            self._auto, self._ctx, self._sid = auto, ctx, sid
            self._started = time.monotonic()
            self._deadline = self._started + auto.application_timeout_minutes * 60
            self._crashed = False
            page = ctx.new_page()
            page.on("crash", lambda *_: setattr(self, "_crashed", True))
            tmpdir = None
            try:
                tmpdir = tempfile.mkdtemp(prefix="cv-", dir=self._tmp_root())
                return self._run(app_id, page, tmpdir)
            except _Held as h:
                return h.result
            except Exception as e:
                return self._handle_exception(app_id, e, self._submitting, auto.max_retries)
            finally:
                self._submitting = False
                if tmpdir:
                    shutil.rmtree(tmpdir, ignore_errors=True)

    @staticmethod
    def _tmp_root() -> str:
        d = get_config().data_dir / "tmp"
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        return str(d)

    # ------------------------------------------------------------------ guards

    def _tick(self) -> None:
        lifecycle.touch()
        if self._crashed:
            raise TransientApplyError("Browser page crashed")
        if time.monotonic() > self._deadline:
            raise ApplicationTimeout(f"Application exceeded {self._auto.application_timeout_minutes} min")

    def _page(self) -> Page:
        live = [p for p in self._ctx.pages if not p.is_closed()]
        return live[-1] if live else self._ctx.new_page()

    # ------------------------------------------------------------------ main flow

    def _run(self, app_id: int, page: Page, tmpdir: str) -> RunResult:
        wid = self.worker_id
        with session_scope() as s:
            app = s.get(Application, app_id)
            job = s.get(Job, app.job_id)
            cv = s.get(CVVersion, app.cv_version_id) if app.cv_version_id else None
            if cv is None:
                transition(s, app, S.NEEDS_REVIEW, worker_id=wid, reason="No CV version attached to application")
                return RunResult(S.NEEDS_REVIEW.value, "No CV")
            if app.mode == "LIVE" and not live_submissions_allowed():
                transition(s, app, S.NEEDS_REVIEW, worker_id=wid,
                           reason="LIVE application refused: JOBAP_ENVIRONMENT=development does not allow LIVE mode")
                return RunResult(S.NEEDS_REVIEW.value, "environment")
            try:
                check_destination(job.apply_url or "")
            except DestinationRefused as e:
                transition(s, app, S.FAILED, worker_id=wid, reason=f"Destination refused: {e}")
                return RunResult(S.FAILED.value, str(e))
            safe = re.sub(r"[^\w.-]", "_", os.path.basename(cv.filename)).lstrip(".") or "cv"
            cv_path = os.path.join(tmpdir, safe)
            if os.path.dirname(os.path.abspath(cv_path)) != os.path.abspath(tmpdir):
                raise ValueError("unsafe CV filename")
            with open(cv_path, "wb") as fh:
                fh.write(read_cv(cv))
            os.chmod(cv_path, 0o600)
            apply_url, mode = job.apply_url, app.mode
            job_title, company, apply_host = job.title, job.company, urlsplit(job.apply_url).hostname
            events: list[tuple[str, dict]] = []

        # 1. navigate
        t0 = time.monotonic()
        resp = page.goto(apply_url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PWTimeout:
            pass
        status_code = resp.status if resp else None
        with session_scope() as s:
            app = s.get(Application, app_id)
            log_event(s, app, "navigate", worker_id=wid, url=page.url, duration_ms=int((time.monotonic() - t0) * 1000),
                      detail={"http_status": status_code})
            if status_code and status_code >= 500:
                raise TransientApplyError(f"HTTP {status_code} loading application page")
            if status_code and status_code >= 400:
                transition(s, app, S.FAILED, worker_id=wid, url=page.url,
                           reason=f"Application page returned HTTP {status_code} (posting closed or moved)")
                return RunResult(S.FAILED.value, f"HTTP {status_code}")

        agent = BrowserAgent(page, on_action=lambda a, d: events.append((a, d)))
        # 2. challenge before anything is typed
        self._checkpoint(app_id, S.STARTED)
        page = self._page()

        # 3. detect form (open it if the page only shows an Apply button)
        fields = extract_fields(page)
        if len([f for f in fields if f.field.field_type != "file"]) < 2:
            agent.page = page
            page = agent.open_application(self._ctx)
            self._checkpoint(app_id, S.STARTED)
            page = self._page()
            fields = extract_fields(page)
        if not fields:
            raise TransientApplyError("No application form detected on page (unexpected layout)")

        with session_scope() as s:
            app = s.get(Application, app_id)
            for q in list(app.questions):
                s.delete(q)  # a retry re-reads the live form
            engine = self._engine(s, app)
            rules = load_rules(s.get(CandidateProfile, cv.profile_id))

        uploaded = False
        answered_all: list[tuple[DetectedField, Answer]] = []
        step = 0
        while True:
            step += 1
            self._tick()
            agent.page = page
            # 4. CV upload first on this step (some ATSs autofill from it), then re-detect
            did_upload = False
            for df in fields:
                if df.field.field_type == "file" and engine.answer(df.field).intent == "cv_upload":
                    fill_field(page, df, None, cv_path)
                    did_upload = uploaded = True
            if did_upload:
                page.wait_for_timeout(3500)
                with session_scope() as s:
                    log_event(s, s.get(Application, app_id), "cv_uploaded", worker_id=wid, url=page.url,
                              detail={"cv_version_id": cv.id, "sha256": cv.sha256, "step": step})
                fields = extract_fields(page)
            for df in fields:
                if df.field.field_type == "combobox" and not df.field.options:
                    df.field.options = combobox_options(page, df)

            # 5. answer and persist provenance
            answers: list[tuple[DetectedField, Answer, int]] = []
            with session_scope() as s:
                app = s.get(Application, app_id)
                for df in fields:
                    a = engine.answer(df.field)
                    q = ApplicationQuestion(application_id=app.id, label=df.field.label, field_name=df.field.name,
                                            field_type=df.field.field_type, required=df.field.required,
                                            options=df.field.options[:100], intent=a.intent)
                    s.add(q)
                    s.flush()
                    s.add(ApplicationAnswer(
                        question_id=q.id,
                        answer_text=None if a.value is None else (
                            "[CV FILE v%d]" % cv.version if a.intent == "cv_upload" else str(a.value)),
                        status=a.status, confidence=a.confidence, provenance=a.provenance(df.field.label),
                        fabricated_information_detected=a.fabricated_information_detected))
                    answers.append((df, a, q.id))
                blocking = [(df, a) for df, a, _ in answers if df.field.required and not a.usable
                            and not (a.intent == "cv_upload" and uploaded)]
                if blocking:
                    target = S.NEEDS_REVIEW if rules.on_unknown_mandatory_answer == "REVIEW" else S.SKIPPED
                    why = "; ".join(f"'{df.field.label[:80]}': {a.basis}" for df, a in blocking[:8])
                    transition(s, app, target, worker_id=wid, url=page.url,
                               reason=f"{len(blocking)} mandatory question(s) without verified answer: {why}")
                    return RunResult(target.value, why)

            # 6. fill this step
            fill_problems = []
            for df, a, qid in answers:
                self._tick()
                if not a.usable or df.field.field_type == "file":
                    continue
                try:
                    if df.field.field_type not in ("radio", "checkbox", "checkbox_group"):
                        df.locator(page).scroll_into_view_if_needed(timeout=5000)
                    fill_field(page, df, a.value)
                    filled = True
                except (FillError, PWError, ValueError) as e:
                    filled = False
                    fill_problems.append((df, str(e)))
                with session_scope() as s:
                    ans = s.scalar(select(ApplicationAnswer).where(ApplicationAnswer.question_id == qid))
                    ans.filled = filled
            required_failed = [(df, e) for df, e in fill_problems if df.field.required]
            if required_failed:
                with session_scope() as s:
                    transition(s, s.get(Application, app_id), S.NEEDS_REVIEW, worker_id=wid, url=page.url,
                               reason="Could not fill required field(s): " + "; ".join(
                                   f"'{df.field.label[:60]}': {redact(e)[:120]}" for df, e in required_failed))
                return RunResult(S.NEEDS_REVIEW.value, "fill failed")
            answered_all += [(df, a) for df, a, _ in answers]

            final, nxt = agent.step_buttons()
            if final is None and nxt is not None:
                if mode == "DRY_RUN":
                    # Advancing a multi-step form can save a draft application on the employer's system.
                    break
                if step >= MAX_STEPS:
                    raise TransientApplyError("Too many form steps")
                errs = visible_errors(page)
                if errs:
                    with session_scope() as s:
                        transition(s, s.get(Application, app_id), S.NEEDS_REVIEW, worker_id=wid, url=page.url,
                                   reason=f"Validation errors before step {step + 1}: {'; '.join(errs)[:300]}")
                    return RunResult(S.NEEDS_REVIEW.value, "step validation")
                agent.click(nxt, f"Next (step {step})")
                page.wait_for_timeout(2500)
                with session_scope() as s:
                    log_event(s, s.get(Application, app_id), "form_step", worker_id=wid, url=page.url,
                              detail={"step": step + 1})
                self._checkpoint(app_id, S.STARTED)
                page = self._page()
                fields = extract_fields(page)
                continue
            break

        with session_scope() as s:
            app = s.get(Application, app_id)
            ev = transition(s, app, S.FORM_COMPLETED, worker_id=wid, url=page.url,
                            detail={"fields": len(answered_all), "steps": step,
                                    "actions": [a for a, _ in events][-50:]})
            if png := _screenshot(page):
                add_evidence(s, app, ev, "PRE_SUBMIT_SCREENSHOT", png=png, url=page.url)
            if mode == "DRY_RUN":
                transition(s, app, S.DRY_RUN_COMPLETE, worker_id=wid, url=page.url,
                           reason="DRY RUN: form completed, submit NOT clicked" + (
                               " (multi-step form: stopped before advancing)" if step == 1 and agent.step_buttons()[1] else ""))
                return RunResult(S.DRY_RUN_COMPLETE.value)

        # 7. submit (LIVE only) - challenge check, then the 10-point pre-submit verification
        self._checkpoint(app_id, S.FORM_COMPLETED)
        page = self._page()
        agent.page = page
        final, nxt = agent.step_buttons()
        checks = self._preflight(app_id, page, agent, final, nxt, job_title, company, apply_host, uploaded,
                                 answered_all)
        failed = {k: v for k, v in checks.items() if v is not True}
        with session_scope() as s:
            app = s.get(Application, app_id)
            log_event(s, app, "preflight", worker_id=wid, url=page.url, detail={"checks": checks})
            if failed:
                transition(s, app, S.NEEDS_REVIEW, worker_id=wid, url=page.url,
                           reason="Pre-submit verification failed: " + "; ".join(f"{k}: {v}" for k, v in failed.items()))
                return RunResult(S.NEEDS_REVIEW.value, "preflight")
        pre_url = page.url
        try:
            pre_confirm = bool(CONFIRM_TEXT_RE.search(page.inner_text("body", timeout=5000)))
        except PWError:
            pre_confirm = False
        final = agent.verify(final, "Final submit button")
        with session_scope() as s:
            transition(s, s.get(Application, app_id), S.SUBMITTING, worker_id=wid, url=pre_url)
        self._submitting = True
        t0 = time.monotonic()
        final.click(timeout=10000)
        with session_scope() as s:
            log_event(s, s.get(Application, app_id), "submit_clicked", worker_id=wid, url=pre_url)
        outcome = wait_for_outcome(page, pre_url, pre_confirm)
        if outcome.kind == "challenge":
            # Challenge after the click: hold for the human, then only observe the outcome (never re-click).
            self._checkpoint(app_id, S.SUBMITTING, detected=outcome.detail)
            page = self._page()
            outcome = wait_for_outcome(page, pre_url, pre_confirm)
        return self._record_outcome(app_id, page, outcome, pre_url, int((time.monotonic() - t0) * 1000))

    def _record_outcome(self, app_id, page, outcome, pre_url, dur) -> RunResult:
        wid = self.worker_id
        png = _screenshot(page)
        with session_scope() as s:
            app = s.get(Application, app_id)
            if outcome.kind == "confirmed":
                ev = log_event(s, app, "submission_confirmed", worker_id=wid, url=outcome.url, duration_ms=dur,
                               detail={"signal": outcome.detail})
                add_evidence(s, app, ev, "CONFIRMATION_TEXT", value=outcome.text_excerpt, url=outcome.url)
                if outcome.url != pre_url:
                    add_evidence(s, app, ev, "CONFIRMATION_URL", value=outcome.url, url=outcome.url)
                if outcome.application_id:
                    add_evidence(s, app, ev, "APPLICATION_ID", value=outcome.application_id, url=outcome.url)
                    app.external_application_id = outcome.application_id
                if png:
                    add_evidence(s, app, ev, "SCREENSHOT", png=png, url=outcome.url)
                transition(s, app, S.SUBMITTED, worker_id=wid, url=outcome.url, reason=outcome.detail)
                return RunResult(S.SUBMITTED.value)
            ev = log_event(s, app, f"submit_outcome:{outcome.kind}", worker_id=wid, url=outcome.url,
                           duration_ms=dur, detail={"detail": outcome.detail})
            if png:
                add_evidence(s, app, ev, "ERROR_SCREENSHOT", png=png, url=outcome.url)
            if outcome.kind == "validation_errors":
                transition(s, app, S.FAILED, worker_id=wid, url=outcome.url,
                           reason=f"Form rejected by site after submit: {redact(outcome.detail or '')[:500]}")
                return RunResult(S.FAILED.value)
            transition(s, app, S.UNKNOWN, worker_id=wid, url=outcome.url,
                       reason="Submit clicked but no confirmation detected; reconcile before any retry")
            return RunResult(S.UNKNOWN.value)

    # ------------------------------------------------------------------ pre-submit verification

    def _preflight(self, app_id, page, agent, final, nxt, job_title, company, apply_host, uploaded,
                   answered) -> dict:
        c: dict = {}
        with session_scope() as s:
            app = s.get(Application, app_id)
            c["1_intended_application"] = True if app.status == S.FORM_COMPLETED.value else f"status {app.status}"
            other = s.scalar(select(Application.id).where(Application.job_id == app.job_id, Application.id != app.id,
                                                          Application.status.in_(["SUBMITTED", "VERIFIED", "SUBMITTING",
                                                                                  "UNKNOWN"])))
            c["10_not_already_submitted"] = True if app.submit_clicked_at is None and other is None else \
                "submit already clicked for this application or its job"
        try:
            body = _norm(page.inner_text("body", timeout=5000))
        except PWError:
            body = ""
        title_tokens = [t for t in _norm(job_title).split() if len(t) > 2] or _norm(job_title).split()
        c["3_job_title_on_page"] = True if title_tokens and all(t in body.split() for t in title_tokens) else \
            f"job title '{job_title}' not found on page"
        c["2_employer"] = True if (not company or _norm(company) in body or c["3_job_title_on_page"] is True) else \
            f"employer '{company}' not found on page"
        host = urlsplit(page.url).hostname
        try:
            check_destination(page.url)
            dest_ok = host == apply_host or (host or "").endswith("." + ".".join((apply_host or "").split(".")[-2:]))
            c["4_destination"] = True if dest_ok else f"page moved to {host} (expected {apply_host})"
        except DestinationRefused as e:
            c["4_destination"] = str(e)
        current = extract_fields(page)
        missing = [df.field.label[:60] for df in current
                   if df.field.required and df.field.field_type != "file" and not field_has_value(page, df.ids)]
        c["5_required_fields_filled"] = True if not missing else f"empty required: {missing[:5]}"
        files = [df for df in current if df.field.field_type == "file"]
        cv_now = any(field_has_value(page, df.ids) for df in files)
        # If the form accepts a CV it must be attached (possibly on an earlier step); a form with no CV field passes.
        c["6_cv_attached"] = True if (cv_now or uploaded or not files) else "the form has a CV field but no CV is attached"
        unanswered = [df.field.label[:60] for df, a in answered if df.field.required and not a.usable
                      and a.intent != "cv_upload"]
        c["7_required_answers_grounded"] = True if not unanswered else f"ungrounded: {unanswered[:5]}"
        errs = visible_errors(page)
        c["8_no_validation_errors"] = True if not errs else f"visible errors: {errs[:3]}"
        if final is None:
            c["9_final_submission_step"] = "no final submit button found"
        elif nxt is not None:
            c["9_final_submission_step"] = "a Next/Continue step is still present"
        else:
            try:
                agent.verify(final, "Final submit button")
                c["9_final_submission_step"] = True
            except TargetError as e:
                c["9_final_submission_step"] = str(e)
        return dict(sorted(c.items()))

    # ------------------------------------------------------------------ human verification checkpoint

    def _checkpoint(self, app_id: int, stage_status: S, detected: str | None = None) -> None:
        """Returns normally when there is no challenge or the human cleared it; raises _Held otherwise."""
        page = self._page()
        ch = detect_challenge(page)
        if ch is None and detected is None:
            return
        kind = ch.kind if ch else "captcha"
        detail = ch.detail if ch else detected
        wid = self.worker_id
        auto = self._auto
        with session_scope() as s:
            app = s.get(Application, app_id)
            job = app.job
            capacity = gateway.open_sessions(s) < auto.max_open_verification_sessions
            can_hold = auto.hold_for_verification and self.session_server is not None and capacity
            ev = transition(s, app, S.VERIFICATION_REQUIRED, worker_id=wid, url=page.url,
                            reason=f"VERIFICATION REQUIRED ({kind}): {detail}. Not bypassed." +
                                   ("" if can_hold else " Browser not held (" + (
                                       "disabled" if not auto.hold_for_verification else
                                       "no session server" if self.session_server is None else
                                       "max open verification sessions reached") + ")."))
            if png := _screenshot(page):
                add_evidence(s, app, ev, "CHALLENGE_SCREENSHOT", png=png, url=page.url)
        if not can_hold:  # raised only after the transaction above has committed
            raise _Held(RunResult(S.VERIFICATION_REQUIRED.value, detail))
        with session_scope() as s:
            app = s.get(Application, app_id)
            job = app.job
            from ..models import User

            owner = s.scalars(select(User).order_by(User.id)).first()
            elapsed = time.monotonic() - self._started
            remaining_session = auto.browser_session_timeout_minutes * 60 - elapsed
            wait_s = max(30, min(auto.verification_timeout_minutes * 60, remaining_session))
            vr = gateway.create_request(
                s, application_id=app.id, platform_key=job.platform, user_id=owner.id if owner else None,
                worker_id=wid, browser_session_id=self._sid, endpoint=self.session_server.endpoint, kind=kind,
                detail=detail, stage=_STAGE[stage_status], page_url=page.url,
                expires_at=utcnow() + dt.timedelta(seconds=wait_s),
                title="HUMAN VERIFICATION REQUIRED",
                body=f"Application: {job.title}\nEmployer: {job.company or 'UNKNOWN'}\nPlatform: {job.platform}\n"
                     f"Reason: {kind} ({detail})\nWorker: {wid}\nExpires in {int(wait_s // 60)} min.")
            vid = vr.id
            deadline = vr.expires_at
        from ..models import Notification

        with session_scope() as s:
            nids = [n for n in s.scalars(select(Notification.id).where(Notification.verification_id == vid))]
        gateway.deliver_now(nids)
        t_hold = time.monotonic()
        result = gateway.hold(self.session_server, vid, self._page, deadline,
                              is_cleared=lambda p: detect_challenge(p) is None, keepalive=self.keepalive)
        self._deadline += time.monotonic() - t_hold  # time waiting for the human does not count
        with session_scope() as s:
            vr = gateway.finish(s, vid, result)
            app = s.get(Application, app_id)
            if result.outcome == "COMPLETED":
                transition(s, app, stage_status, worker_id=wid, event="verification_completed",
                           url=self._page().url, reason=f"Verification completed; resuming ({vr.stage})")
                from ..notifications import notify

                notify(s, "verification_completed", "Verification completed",
                       f"{job.title} @ {job.company or 'UNKNOWN'}: application resumed.",
                       link_path=f"/applications/{app_id}", application_id=app_id, verification_id=vid)
                return
            clicked = app.submit_clicked_at is not None
            transition(s, app, S.VERIFICATION_TIMEOUT, worker_id=wid, event=f"verification_{result.outcome.lower()}",
                       reason=f"{result.detail}. Application paused" + (
                           "; submit had been clicked, so it must be reconciled before any retry" if clicked else ""))
            from ..notifications import notify

            notify(s, "verification_timeout", "Verification not completed",
                   f"{job.title} @ {job.company or 'UNKNOWN'}: {result.detail}. The application is paused.",
                   severity="warning", link_path=f"/applications/{app_id}", application_id=app_id,
                   verification_id=vid)
        raise _Held(RunResult(S.VERIFICATION_TIMEOUT.value, result.detail))

    # ------------------------------------------------------------------ helpers

    def _engine(self, s: Session, app: Application) -> AnswerEngine:
        cv = s.get(CVVersion, app.cv_version_id)
        profile = s.get(CandidateProfile, cv.profile_id)
        job = s.get(Job, app.job_id)
        kb = knowledge(s, profile)
        provider = ProviderHandle(s, profile.user_id)
        narrative = make_narrative_fn(provider) if provider.configured else None
        return AnswerEngine(kb, load_rules(profile),
                            JobContext(job.company, job.title, job.location, job.description_text), narrative)

    def _handle_exception(self, app_id: int, e: Exception, reached_submitting: bool, max_retries: int) -> RunResult:
        log.exception("application run failed", extra={"application_id": app_id, "event": "apply_error"})
        if self._crashed or (isinstance(e, PWError) and re.search(r"closed|crash", str(e), re.I)):
            self.browsers.restart()  # the next application gets a fresh Chromium
        transient = isinstance(e, (TransientApplyError, PWTimeout, ApplicationTimeout, TargetError)) or (
            isinstance(e, PWError) and re.search(r"net::|Target .*closed|Browser .*closed|crash", str(e), re.I))
        with session_scope() as s:
            app = s.get(Application, app_id)
            record_error(s, "apply", e, worker_id=self.worker_id, platform=app.job.platform, job_id=app.job_id,
                         application_id=app.id)
            app.last_error = redact(f"{type(e).__name__}: {e}")[:2000]
            st = S(app.status)
            if reached_submitting or st == S.SUBMITTING or app.submit_clicked_at is not None:
                if st in {S.SUBMITTING, S.VERIFICATION_REQUIRED}:
                    transition(s, app, S.UNKNOWN, worker_id=self.worker_id,
                               reason="Error after submit was initiated; submission status uncertain. Not retried.")
                return RunResult(S.UNKNOWN.value, str(e))
            if st == S.VERIFICATION_REQUIRED:
                transition(s, app, S.VERIFICATION_TIMEOUT, worker_id=self.worker_id,
                           reason=f"Session lost during verification: {app.last_error}")
                return RunResult(S.VERIFICATION_TIMEOUT.value, str(e))
            if st in {S.STARTED, S.FORM_COMPLETED}:
                if transient and app.retry_count < max_retries:
                    app.retry_count += 1
                    transition(s, app, S.QUEUED, worker_id=self.worker_id,
                               reason=f"Transient error before submit (retry {app.retry_count}/{max_retries}): "
                                      f"{type(e).__name__}")
                    return RunResult("RETRY", str(e))
                transition(s, app, S.FAILED, worker_id=self.worker_id, reason=app.last_error)
                return RunResult(S.FAILED.value, str(e))
        return RunResult("ERROR", str(e))
