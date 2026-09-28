"""Real application execution against the employer's hosted application form.

State discipline:
  QUEUED -> STARTED (row-locked, one worker only)
  STARTED -> FORM_COMPLETED after every required field is filled from grounded answers
  FORM_COMPLETED -> SUBMITTING is COMMITTED before the submit click
  SUBMITTING -> SUBMITTED only with stored confirmation evidence, else UNKNOWN / FAILED /
  VERIFICATION_REQUIRED. An application that reached SUBMITTING is never retried automatically.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass

from playwright.sync_api import Error as PWError, Page, TimeoutError as PWTimeout
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.providers import ProviderHandle
from ..audit import record_error
from ..browser.detect import CONFIRM_TEXT_RE, detect_challenge, wait_for_outcome
from ..browser.engine import BrowserManager
from ..browser.forms import DetectedField, FillError, combobox_options, extract_fields, fill_field, find_submit
from ..config import get_config
from ..db import session_scope
from ..evidence import add_evidence
from ..models import (
    Application, ApplicationAnswer, ApplicationQuestion, ApplicationStatus as S, CandidateProfile, CVVersion, Job,
)
from ..profile.service import knowledge, read_cv, rules as load_rules
from ..questions.engine import Answer, AnswerEngine, JobContext
from ..questions.grounding import make_narrative_fn
from ..security.redact import redact
from ..settings_store import AutomationSettings, load
from ..state import log_event, transition

log = logging.getLogger(__name__)


class TransientApplyError(Exception):
    pass


@dataclass
class RunResult:
    status: str
    reason: str | None = None


def _claim(s: Session, app_id: int, worker_id: str, session_id: str) -> Application | None:
    app = s.scalar(select(Application).where(Application.id == app_id).with_for_update(skip_locked=True))
    if app is None or app.status != S.QUEUED.value:
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


def _reveal_form(page: Page) -> None:
    btn = page.locator("a:visible, button:visible").filter(
        has_text=re.compile(r"^\s*(apply( for this (job|position|role))?( now)?|apply to this job)\s*$", re.I))
    if btn.count():
        btn.first.click()
        page.wait_for_timeout(2500)


class ApplicationRunner:
    def __init__(self, browsers: BrowserManager, worker_id: str):
        self.browsers = browsers
        self.worker_id = worker_id
        self._submitting = False

    def run(self, app_id: int) -> RunResult:
        with self.browsers.context() as (ctx, sid):
            with session_scope() as s:
                app = _claim(s, app_id, self.worker_id, sid)
                if app is None:
                    return RunResult("NOT_CLAIMED", "Application not in QUEUED state or locked by another worker")
                auto = load(s, AutomationSettings)
                max_retries = auto.max_retries
            page = ctx.new_page()
            reached_submitting = False
            tmpdir = None
            try:
                tmpdir = tempfile.mkdtemp(prefix="cv-", dir=self._tmp_root())
                return self._run(app_id, page, tmpdir, lambda: setattr(self, "_submitting", True))
            except Exception as e:
                reached_submitting = getattr(self, "_submitting", False)
                return self._handle_exception(app_id, e, reached_submitting, max_retries, page)
            finally:
                self._submitting = False
                if tmpdir:
                    shutil.rmtree(tmpdir, ignore_errors=True)

    @staticmethod
    def _tmp_root() -> str:
        d = get_config().data_dir / "tmp"
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        return str(d)

    # ------------------------------------------------------------------ main flow

    def _run(self, app_id: int, page: Page, tmpdir: str, mark_submitting) -> RunResult:
        wid = self.worker_id
        with session_scope() as s:
            app = s.get(Application, app_id)
            job = s.get(Job, app.job_id)
            cv = s.get(CVVersion, app.cv_version_id) if app.cv_version_id else None
            if cv is None:
                transition(s, app, S.NEEDS_REVIEW, worker_id=wid, reason="No CV version attached to application")
                return RunResult(S.NEEDS_REVIEW.value, "No CV")
            cv_path = os.path.join(tmpdir, re.sub(r"[^\w.-]", "_", cv.filename))
            with open(cv_path, "wb") as fh:
                fh.write(read_cv(cv))
            os.chmod(cv_path, 0o600)
            apply_url, mode = job.apply_url, app.mode

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

        # 2. challenges before anything is typed
        if (res := self._check_challenge(app_id, page)) is not None:
            return res

        # 3. detect form
        fields = extract_fields(page)
        if len([f for f in fields if f.field.field_type != "file"]) < 2:
            _reveal_form(page)
            fields = extract_fields(page)
        if not fields:
            raise TransientApplyError("No application form detected on page (unexpected layout)")

        # 4. CV upload first (some ATSs autofill from it), then re-detect
        with session_scope() as s:
            app = s.get(Application, app_id)
            engine = self._engine(s, app)
        uploaded = False
        for df in fields:
            if df.field.field_type == "file" and engine.answer(df.field).intent == "cv_upload":
                fill_field(page, df, None, cv_path)
                uploaded = True
        if uploaded:
            page.wait_for_timeout(3500)
            with session_scope() as s:
                log_event(s, s.get(Application, app_id), "cv_uploaded", worker_id=wid, url=page.url,
                          detail={"cv_version_id": cv.id, "sha256": cv.sha256})
            fields = extract_fields(page)
        for df in fields:
            if df.field.field_type == "combobox" and not df.field.options:
                df.field.options = combobox_options(page, df)

        # 5. answer every question and persist provenance
        answers: list[tuple[DetectedField, Answer, int]] = []
        with session_scope() as s:
            app = s.get(Application, app_id)
            engine = self._engine(s, app)
            for q in list(app.questions):
                s.delete(q)  # a retry re-reads the live form
            s.flush()
            for df in fields:
                a = engine.answer(df.field)
                q = ApplicationQuestion(application_id=app.id, label=df.field.label, field_name=df.field.name,
                                        field_type=df.field.field_type, required=df.field.required,
                                        options=df.field.options[:100], intent=a.intent)
                s.add(q)
                s.flush()
                s.add(ApplicationAnswer(
                    question_id=q.id,
                    answer_text=None if a.value is None else ("[CV FILE v%d]" % cv.version if a.intent == "cv_upload" else str(a.value)),
                    status=a.status, confidence=a.confidence, provenance=a.provenance(df.field.label),
                    fabricated_information_detected=a.fabricated_information_detected))
                answers.append((df, a, q.id))
            blocking = [(df, a) for df, a, _ in answers if df.field.required and not a.usable
                        and not (a.intent == "cv_upload" and uploaded)]
            if blocking:
                rules = load_rules(s.get(CandidateProfile, s.get(CVVersion, cv.id).profile_id))
                target = S.NEEDS_REVIEW if rules.on_unknown_mandatory_answer == "REVIEW" else S.SKIPPED
                why = "; ".join(f"'{df.field.label[:80]}': {a.basis}" for df, a in blocking[:8])
                transition(s, app, target, worker_id=wid, url=page.url,
                           reason=f"{len(blocking)} mandatory question(s) without verified answer: {why}")
                return RunResult(target.value, why)

        # 6. fill
        fill_problems = []
        for df, a, qid in answers:
            if not a.usable or df.field.field_type == "file":
                continue
            try:
                fill_field(page, df, a.value)
                filled = True
            except (FillError, PWError, ValueError) as e:
                filled = False
                fill_problems.append((df, str(e)))
            with session_scope() as s:
                ans = s.scalar(select(ApplicationAnswer).where(ApplicationAnswer.question_id == qid))
                ans.filled = filled
        with session_scope() as s:
            app = s.get(Application, app_id)
            required_failed = [(df, e) for df, e in fill_problems if df.field.required]
            if required_failed:
                transition(s, app, S.NEEDS_REVIEW, worker_id=wid, url=page.url,
                           reason="Could not fill required field(s): " + "; ".join(
                               f"'{df.field.label[:60]}': {redact(e)[:120]}" for df, e in required_failed))
                return RunResult(S.NEEDS_REVIEW.value, "fill failed")
            ev = transition(s, app, S.FORM_COMPLETED, worker_id=wid, url=page.url,
                            detail={"fields": len(answers), "optional_unfilled": len(fill_problems)})
            if png := _screenshot(page):
                add_evidence(s, app, ev, "PRE_SUBMIT_SCREENSHOT", png=png, url=page.url)
            if mode == "DRY_RUN":
                transition(s, app, S.DRY_RUN_COMPLETE, worker_id=wid, url=page.url,
                           reason="DRY RUN: form completed, submit NOT clicked")
                return RunResult(S.DRY_RUN_COMPLETE.value)

        # 7. submit (LIVE only)
        if (res := self._check_challenge(app_id, page)) is not None:
            return res
        submit = find_submit(page)
        if submit is None:
            with session_scope() as s:
                transition(s, s.get(Application, app_id), S.FAILED, worker_id=wid, url=page.url,
                           reason="Submit button not found; not submitted")
            return RunResult(S.FAILED.value, "no submit button")
        pre_url = page.url
        try:
            pre_confirm = bool(CONFIRM_TEXT_RE.search(page.inner_text("body", timeout=5000)))
        except PWError:
            pre_confirm = False
        with session_scope() as s:
            transition(s, s.get(Application, app_id), S.SUBMITTING, worker_id=wid, url=pre_url)
        mark_submitting()
        t0 = time.monotonic()
        submit.click()
        outcome = wait_for_outcome(page, pre_url, pre_confirm)
        dur = int((time.monotonic() - t0) * 1000)
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
                add_evidence(s, app, ev, "CHALLENGE_SCREENSHOT" if outcome.kind == "challenge" else "ERROR_SCREENSHOT",
                             png=png, url=outcome.url)
            if outcome.kind == "challenge":
                transition(s, app, S.VERIFICATION_REQUIRED, worker_id=wid, url=outcome.url,
                           reason=f"VERIFICATION REQUIRED after submit click ({outcome.detail}); not bypassed")
                return RunResult(S.VERIFICATION_REQUIRED.value)
            if outcome.kind == "validation_errors":
                transition(s, app, S.FAILED, worker_id=wid, url=outcome.url,
                           reason=f"Form rejected by site: {redact(outcome.detail or '')[:500]}")
                return RunResult(S.FAILED.value)
            transition(s, app, S.UNKNOWN, worker_id=wid, url=outcome.url,
                       reason="Submit clicked but no confirmation detected; investigate before retrying")
            return RunResult(S.UNKNOWN.value)

    def _engine(self, s: Session, app: Application) -> AnswerEngine:
        cv = s.get(CVVersion, app.cv_version_id)
        profile = s.get(CandidateProfile, cv.profile_id)
        job = s.get(Job, app.job_id)
        kb = knowledge(s, profile)
        provider = ProviderHandle(s, profile.user_id)
        narrative = make_narrative_fn(provider) if provider.configured else None
        return AnswerEngine(kb, load_rules(profile),
                            JobContext(job.company, job.title, job.location, job.description_text), narrative)

    def _check_challenge(self, app_id: int, page: Page) -> RunResult | None:
        ch = detect_challenge(page)
        if ch is None:
            return None
        with session_scope() as s:
            app = s.get(Application, app_id)
            ev = transition(s, app, S.VERIFICATION_REQUIRED, worker_id=self.worker_id, url=page.url,
                            reason=f"VERIFICATION REQUIRED ({ch.kind}): {ch.detail}. Not bypassed.")
            if png := _screenshot(page):
                add_evidence(s, app, ev, "CHALLENGE_SCREENSHOT", png=png, url=page.url)
        return RunResult(S.VERIFICATION_REQUIRED.value, ch.detail)

    def _handle_exception(self, app_id: int, e: Exception, reached_submitting: bool, max_retries: int,
                          page: Page) -> RunResult:
        log.exception("application run failed", extra={"application_id": app_id, "event": "apply_error"})
        transient = isinstance(e, (TransientApplyError, PWTimeout)) or (
            isinstance(e, PWError) and re.search(r"net::|Target .*closed|Browser .*closed|crash", str(e), re.I))
        with session_scope() as s:
            app = s.get(Application, app_id)
            record_error(s, "apply", e, worker_id=self.worker_id, platform=app.job.platform, job_id=app.job_id,
                         application_id=app.id)
            app.last_error = redact(f"{type(e).__name__}: {e}")[:2000]
            st = S(app.status)
            if reached_submitting or st == S.SUBMITTING:
                transition(s, app, S.UNKNOWN, worker_id=self.worker_id,
                           reason="Error after submit was initiated; submission status uncertain. Not retried.")
                return RunResult(S.UNKNOWN.value, str(e))
            if st in {S.STARTED, S.FORM_COMPLETED}:
                if transient and app.retry_count < max_retries:
                    app.retry_count += 1
                    transition(s, app, S.QUEUED, worker_id=self.worker_id,
                               reason=f"Transient error before submit (retry {app.retry_count}/{max_retries})")
                    return RunResult("RETRY", str(e))
                transition(s, app, S.FAILED, worker_id=self.worker_id, reason=app.last_error)
                return RunResult(S.FAILED.value, str(e))
        if isinstance(e, PWError) and re.search(r"closed|crash", str(e), re.I):
            self.browsers.restart()
        return RunResult("ERROR", str(e))
