"""Browser engine + application runner against LOCAL test fixture pages.

This verifies our own code paths (real Chromium, real DOM, real file upload,
real state transitions and evidence). It is NOT validation of any real
platform; see docs/ACCEPTANCE.md for live validation.
"""
import http.server
import os
import threading
from pathlib import Path

import pytest

from autopilot.models import Application, ApplicationEvidence, FactStatus
from autopilot.profile.service import set_fact, store_cv

FIX = Path(__file__).parent / "fixtures" / "forms"
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


class _Handler(http.server.SimpleHTTPRequestHandler):
    log = []

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(FIX), **kw)

    def guess_type(self, path):
        return "text/html" if "recaptcha" in str(path) else super().guess_type(path)

    def do_GET(self):
        _Handler.log.append(self.path)
        if self.path.startswith("/submit-log"):
            self.send_response(204)
            self.end_headers()
            return
        return super().do_GET()

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="module")
def runner():
    if os.path.exists(CHROME):
        os.environ["JOBAP_BROWSER_EXECUTABLE"] = CHROME
    from autopilot.config import reset_config_cache

    reset_config_cache()
    from autopilot.browser.engine import BrowserManager
    from autopilot.workers.apply import ApplicationRunner

    bm = BrowserManager()
    yield ApplicationRunner(bm, "test-worker")
    bm.close()


def _setup(s, profile, url, mode="LIVE"):
    from autopilot.connectors.base import NormalizedJob
    from autopilot.jobs.pipeline import ingest
    from autopilot.state import transition
    from autopilot.models import ApplicationStatus as S

    for cat, key, val in [("identity", "full_name", "Test Candidate"), ("contact", "email", "t@example.invalid"),
                          ("contact", "phone", "+000000000"),
                          ("work_authorization", "authorized:united arab emirates", "yes"),
                          ("work_authorization", "requires_sponsorship:united arab emirates", "no"),
                          ("experience", "total_professional_years", "0")]:
        set_fact(s, profile, cat, key, val)
    cv = store_cv(s, profile, "Test_CV.txt", b"Test Candidate\nfixture cv\n")
    job, _ = ingest(s, None, NormalizedJob(platform="greenhouse", board="fixture", external_id=url, url=url,
                                           apply_url=url, apply_method="greenhouse_hosted_form", title="Fixture Role",
                                           company="Fixture Co", location="Dubai, United Arab Emirates"), [])
    app = Application(job_id=job.id, mode=mode, status="EVALUATED", cv_version_id=cv.id)
    s.add(app)
    s.flush()
    transition(s, app, S.QUEUED)
    s.commit()
    return app.id


def _reload(s, app_id):
    s.expire_all()
    return s.get(Application, app_id)


def test_live_submission_with_evidence(s, profile, server, runner):
    _Handler.log.clear()
    app_id = _setup(s, profile, f"{server}/apply_form.html")
    res = runner.run(app_id)
    app = _reload(s, app_id)
    assert res.status == "SUBMITTED", app.status_reason
    assert app.status == "SUBMITTED" and app.external_application_id == "FIXTURE-0001"
    kinds = {e.kind for e in app.evidence}
    assert {"CONFIRMATION_TEXT", "CONFIRMATION_URL", "APPLICATION_ID", "SCREENSHOT", "PRE_SUBMIT_SCREENSHOT"} <= kinds
    assert all(e.event_id for e in app.evidence)
    sub = [p for p in _Handler.log if p.startswith("/submit-log")]
    assert len(sub) == 1 and "fn=Test" in sub[0] and "auth=Yes" in sub[0] and "yrs=Less+than+1+year" in sub[0]
    assert "file=Test_CV.txt" in sub[0]
    qs = {q.label: q for q in app.questions}
    spons = next(q for l, q in qs.items() if "sponsorship" in l)
    assert spons.answer.answer_text == "No" and spons.answer.provenance["fact_ids"]
    extra = next(q for l, q in qs.items() if l.startswith("Anything else"))
    assert extra.answer.status == "UNKNOWN" and not extra.answer.filled  # optional narrative left blank
    statuses = [e.to_status for e in app.events if e.to_status]
    assert statuses == ["QUEUED", "STARTED", "FORM_COMPLETED", "SUBMITTING", "SUBMITTED"]
    from autopilot.evidence import read_evidence_png

    shot = next(e for e in app.evidence if e.kind == "SCREENSHOT")
    assert read_evidence_png(shot)[:4] == b"\x89PNG"
    # a second run is refused: never submits twice
    assert runner.run(app_id).status == "NOT_CLAIMED"


def test_dry_run_never_submits(s, profile, server, runner):
    _Handler.log.clear()
    app_id = _setup(s, profile, f"{server}/apply_form.html", mode="DRY_RUN")
    assert runner.run(app_id).status == "DRY_RUN_COMPLETE"
    assert not [p for p in _Handler.log if p.startswith("/submit-log") or "confirmation" in p]
    app = _reload(s, app_id)
    assert app.submitted_at is None
    assert not {e.kind for e in app.evidence} & {"CONFIRMATION_TEXT", "CONFIRMATION_URL", "APPLICATION_ID"}


def test_captcha_is_recorded_not_bypassed(s, profile, server, runner):
    app_id = _setup(s, profile, f"{server}/captcha_form.html")
    assert runner.run(app_id).status == "VERIFICATION_REQUIRED"
    assert "VERIFICATION REQUIRED" in _reload(s, app_id).status_reason


def test_unknown_mandatory_answer_goes_to_review(s, profile, server, runner):
    app_id = _setup(s, profile, f"{server}/unknown_form.html")
    assert runner.run(app_id).status == "NEEDS_REVIEW"
    app = _reload(s, app_id)
    assert "SIEM" in app.status_reason
    assert app.submitted_at is None


def test_no_confirmation_means_unknown(s, profile, server, runner, monkeypatch):
    import autopilot.workers.apply as ap

    real = ap.wait_for_outcome
    monkeypatch.setattr(ap, "wait_for_outcome", lambda p, u, c: real(p, u, c, timeout_s=4))
    app_id = _setup(s, profile, f"{server}/silent_form.html")
    res = runner.run(app_id)
    assert res.status == "UNKNOWN", _reload(s, app_id).status_reason
    app = _reload(s, app_id)
    assert not [e for e in app.evidence if e.kind in ("CONFIRMATION_TEXT", "APPLICATION_ID")]


def test_http_404_fails_cleanly(s, profile, server, runner):
    app_id = _setup(s, profile, f"{server}/does-not-exist.html")
    assert runner.run(app_id).status == "FAILED"
