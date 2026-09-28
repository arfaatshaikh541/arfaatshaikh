"""Administrative dashboard and control API.

Every figure shown comes from the database or a live check. Empty tables show
0 / "none". Passwords, API keys and cookies are never rendered or returned.
"""
from __future__ import annotations

import datetime as dt
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import audit
from ..config import get_config
from ..db import check_db, init_db, session_factory
from ..evidence import add_evidence, read_evidence_png
from ..health import system_health
from ..jobs.matching import SUPPORTED_APPLY_METHODS
from ..logging_setup import setup_logging
from ..models import (
    Application, ApplicationEvidence, ApplicationStatus as S, AuditLog, CandidateFact, CVVersion, ErrorRecord,
    FactStatus, Job, JobSource, Platform, Report, Task, utcnow,
)
from ..profile import service as prof
from ..profile.cv_parser import CVParseError
from ..profile.schema import Preferences, Rules
from ..reports import compute, generate
from ..security.credentials import delete_credential, list_credentials, store_credential
from ..security.redact import redact
from ..settings_store import AISettings, AutomationSettings, load, save
from ..state import IllegalTransition, log_event, transition
from ..workers import queue
from .auth import COOKIE, authenticate, check_csrf, create_session, destroy_session, get_session

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
TEMPLATES.env.globals["quote"] = quote

@asynccontextmanager
async def lifespan(_app):
    setup_logging(get_config().log_level)
    init_db()
    yield


app = FastAPI(title="JOB AUTOPILOT", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

FACT_CATEGORIES = ["identity", "contact", "work_authorization", "availability", "compensation", "experience",
                   "employment", "education", "skill", "skill_years", "certification", "language", "project",
                   "narrative", "eeo"]


@app.middleware("http")
async def security_headers(request: Request, call_next):
    try:
        resp = await call_next(request)
    finally:
        # Safety net: a request that raised (403, 404, errors) never leaks its DB session / transaction.
        for ctx in getattr(request.state, "ctxs", []):
            ctx.close(commit=False)
    if request.url.path.startswith("/verify/") and request.method == "GET":
        # The remote-verification page is the only page that runs script: our own static file, and a
        # WebSocket back to this same host. No inline script, no third-party origins.
        host = request.headers.get("host", "")
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' blob: data:; style-src 'self'; script-src 'self'; "
            f"connect-src 'self' wss://{host} ws://{host}; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
    else:
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'none'; "
            "frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cache-Control"] = "no-store"
    if get_config().secure_cookies:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000"
    return resp


# ------------------------------------------------------------------ helpers


class Ctx:
    def __init__(self, request: Request):
        self.request = request
        self.closed = False
        self.s: Session = session_factory()()
        request.state.ctxs = getattr(request.state, "ctxs", []) + [self]
        found = get_session(self.s, request)
        self.user, self.ws = found if found else (None, None)

    def close(self, commit: bool = True) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            if commit:
                self.s.commit()
            else:
                self.s.rollback()
        finally:
            self.s.close()

    @property
    def ip(self) -> str | None:
        return self.request.client.host if self.request.client else None

    def audit(self, action: str, target: str | None = None, **detail: Any) -> None:
        audit(self.s, self.user.email if self.user else "anonymous", action, target, self.ip, **detail)


def _login_redirect() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


def render(c: Ctx, template: str, **kw: Any) -> HTMLResponse:
    auto = load(c.s, AutomationSettings)
    resp = TEMPLATES.TemplateResponse(c.request, template, {
        "user": c.user, "csrf": c.ws.csrf_token if c.ws else "", "auto": auto, "flash": c.request.query_params.get("msg"),
        **kw})
    c.close()
    return resp


def back(c: Ctx, url: str, msg: str | None = None) -> RedirectResponse:
    c.close()
    return RedirectResponse(url + (("&" if "?" in url else "?") + "msg=" + quote(msg) if msg else ""), status_code=303)


async def authed_post(request: Request) -> tuple[Ctx, Any]:
    c = Ctx(request)
    if c.user is None:
        c.close(False)
        raise HTTPException(status_code=401)
    form = await request.form()
    check_csrf(c.ws, form.get("csrf"))
    return c, form


def authed_get(request: Request) -> Ctx | None:
    c = Ctx(request)
    if c.user is None:
        c.close(False)
        return None
    return c


def _split(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").replace("\n", ",").split(",") if x.strip()]


# ------------------------------------------------------------------ auth


@app.get("/healthz")
def healthz():
    ok, msg = check_db()
    return JSONResponse({"database": msg}, status_code=200 if ok else 503)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    c = Ctx(request)
    return render(c, "login.html", error=request.query_params.get("error"))


@app.post("/login")
async def login(request: Request):
    form = await request.form()
    c = Ctx(request)
    from ..ratelimit import reserve_slot

    if reserve_slot(f"login:{c.ip}", 2.0) > 10:
        return back(c, "/login?error=" + quote("Too many attempts; wait a minute"))
    user, why = authenticate(c.s, str(form.get("email", "")), str(form.get("password", "")))
    if user is None:
        audit(c.s, str(form.get("email", ""))[:320], "login_failed", ip=c.ip)
        c.close()
        return RedirectResponse("/login?error=" + quote(why), status_code=303)
    token = create_session(c.s, user, request)
    audit(c.s, user.email, "login", ip=c.ip)
    c.close()
    resp = RedirectResponse("/", status_code=303)
    cfg = get_config()
    resp.set_cookie(COOKIE, token, httponly=True, secure=cfg.secure_cookies, samesite="strict",
                    max_age=cfg.session_hours * 3600)
    return resp


@app.post("/logout")
async def logout(request: Request):
    c, _ = await authed_post(request)
    destroy_session(c.s, request)
    c.audit("logout")
    c.close()
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE)
    return resp


# ------------------------------------------------------------------ overview & health


@app.get("/", response_class=HTMLResponse)
def overview(request: Request):
    if not (c := authed_get(request)):
        return _login_redirect()
    auto = load(c.s, AutomationSettings)
    today = dt.datetime.now(ZoneInfo(auto.timezone)).date()
    counts = compute(c.s, today, auto.timezone)
    totals = {
        "jobs": c.s.scalar(select(func.count(Job.id))) or 0,
        "live_submitted": c.s.scalar(select(func.count(Application.id)).where(
            Application.mode == "LIVE", Application.status.in_(["SUBMITTED", "VERIFIED"]))) or 0,
        "by_status": dict(c.s.execute(select(Application.status, func.count(Application.id))
                                      .where(Application.mode == auto.mode).group_by(Application.status)).all()),
    }
    p = prof.get_or_create_profile(c.s, c.user.id)
    setup = {
        "verified_facts": c.s.scalar(select(func.count(CandidateFact.id)).where(
            CandidateFact.profile_id == p.id, CandidateFact.status == "VERIFIED")) or 0,
        "unconfirmed_facts": c.s.scalar(select(func.count(CandidateFact.id)).where(
            CandidateFact.profile_id == p.id, CandidateFact.status == "EXTRACTED")) or 0,
        "active_cv": prof.active_cv(c.s, p),
        "target_roles": prof.preferences(p).target_roles,
        "sources": c.s.scalar(select(func.count(JobSource.id))) or 0,
    }
    return render(c, "overview.html", health=system_health(c.s), counts=counts, totals=totals, setup=setup)


@app.get("/health")
def health_json(request: Request):
    if not (c := authed_get(request)):
        raise HTTPException(401)
    h = system_health(c.s)
    c.close()
    return JSONResponse(json.loads(json.dumps(h, default=str)))


# ------------------------------------------------------------------ applications


@app.get("/applications", response_class=HTMLResponse)
def applications(request: Request, status: str | None = None, mode: str | None = None):
    if not (c := authed_get(request)):
        return _login_redirect()
    q = select(Application).join(Job).order_by(Application.id.desc()).limit(500)
    if status:
        q = q.where(Application.status == status)
    if mode:
        q = q.where(Application.mode == mode)
    return render(c, "applications.html", apps=c.s.scalars(q).all(), statuses=[x.value for x in S],
                  status=status, mode=mode)


@app.get("/applications/{app_id}", response_class=HTMLResponse)
def application_detail(request: Request, app_id: int):
    if not (c := authed_get(request)):
        return _login_redirect()
    a = c.s.get(Application, app_id)
    if a is None:
        c.close()
        raise HTTPException(404)
    cv = c.s.get(CVVersion, a.cv_version_id) if a.cv_version_id else None
    errors = c.s.scalars(select(ErrorRecord).where(ErrorRecord.application_id == a.id).order_by(ErrorRecord.id)).all()
    return render(c, "application.html", a=a, job=a.job, match=a.job.match, cv=cv, errors=errors)


@app.post("/applications/{app_id}/action")
async def application_action(request: Request, app_id: int):
    c, form = await authed_post(request)
    a = c.s.get(Application, app_id, with_for_update=True)
    if a is None:
        c.close(False)
        raise HTTPException(404)
    action = form.get("action")
    try:
        if action in ("retry", "approve"):
            if S(a.status) not in {S.FAILED, S.VERIFICATION_REQUIRED, S.VERIFICATION_TIMEOUT, S.NEEDS_REVIEW,
                                   S.SKIPPED}:
                raise IllegalTransition(f"Cannot retry from {a.status}")
            reconciled = a.submit_clicked_at is not None and any(
                e.event == "reconciled_not_submitted" and e.ts >= a.submit_clicked_at for e in a.events)
            if a.cv_version_id is None:
                cv = prof.active_cv(c.s, prof.get_or_create_profile(c.s, c.user.id))
                if cv is None:
                    raise IllegalTransition("Upload a CV first")
                a.cv_version_id = cv.id
            transition(c.s, a, S.QUEUED, event=f"admin_{action}", reason=f"{action} by {c.user.email}",
                       reconciled_not_submitted=reconciled)
        elif action == "skip":
            transition(c.s, a, S.SKIPPED, event="admin_skip", reason=f"Skipped by {c.user.email}")
        elif action == "resolve_submitted":
            note = str(form.get("evidence", "")).strip()
            if S(a.status) not in {S.UNKNOWN, S.VERIFICATION_TIMEOUT} or len(note) < 10:
                raise IllegalTransition("Provide the confirmation you received (min 10 chars) for an UNKNOWN "
                                        "or VERIFICATION_TIMEOUT application")
            if S(a.status) == S.VERIFICATION_TIMEOUT:
                transition(c.s, a, S.UNKNOWN, event="admin_resolve", reason="Reconciling after verification timeout")
            ev = log_event(c.s, a, "admin_confirmed_submission", detail={"by": c.user.email})
            add_evidence(c.s, a, ev, "MANUAL_CONFIRMATION", value=f"Confirmed by {c.user.email}: {note}")
            transition(c.s, a, S.SUBMITTED, event="admin_resolve", reason="Manually confirmed by candidate")
        elif action == "resolve_failed":
            if S(a.status) not in {S.UNKNOWN, S.VERIFICATION_TIMEOUT, S.FAILED}:
                raise IllegalTransition("Only UNKNOWN / VERIFICATION_TIMEOUT / FAILED applications can be reconciled")
            if a.submit_clicked_at is not None and form.get("confirm") != "NOT SUBMITTED":
                raise IllegalTransition("Submit was clicked for this application. Check your email and the employer "
                                        "site, then type NOT SUBMITTED to confirm no application was received")
            if S(a.status) != S.FAILED:
                transition(c.s, a, S.FAILED, event="admin_resolve", reason=f"Marked not submitted by {c.user.email}")
            log_event(c.s, a, "reconciled_not_submitted", detail={"by": c.user.email})
        else:
            raise IllegalTransition("Unknown action")
        c.audit(f"application_{action}", f"application:{a.id}")
    except IllegalTransition as e:
        c.s.rollback()
        return back(c, f"/applications/{app_id}", f"Refused: {e}")
    return back(c, f"/applications/{app_id}", f"{action} applied")


@app.get("/evidence/{ev_id}.png")
def evidence_png(request: Request, ev_id: int):
    if not (c := authed_get(request)):
        raise HTTPException(401)
    ev = c.s.get(ApplicationEvidence, ev_id)
    if ev is None or not ev.file_path:
        c.close()
        raise HTTPException(404)
    data = read_evidence_png(ev)
    c.audit("view_evidence", f"evidence:{ev_id}")
    c.close()
    return Response(data, media_type="image/png")


# ------------------------------------------------------------------ jobs & sources


@app.get("/jobs", response_class=HTMLResponse)
def jobs(request: Request, decision: str | None = None):
    if not (c := authed_get(request)):
        return _login_redirect()
    from ..models import JobMatch

    q = select(Job).outerjoin(JobMatch).order_by(Job.id.desc()).limit(500)
    if decision:
        q = q.where(JobMatch.decision == decision)
    return render(c, "jobs.html", jobs=c.s.scalars(q).all(), decision=decision)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int):
    if not (c := authed_get(request)):
        return _login_redirect()
    j = c.s.get(Job, job_id)
    if j is None:
        c.close()
        raise HTTPException(404)
    apps = c.s.scalars(select(Application).where(Application.job_id == j.id)).all()
    dups = c.s.scalars(select(Job).where(Job.duplicate_of_id == j.id)).all()
    return render(c, "job.html", j=j, apps=apps, dups=dups, supported=j.apply_method in SUPPORTED_APPLY_METHODS)


@app.post("/jobs/{job_id}/queue")
async def job_queue(request: Request, job_id: int):
    """Manual override: queue an application the rules skipped (still fully grounded)."""
    c, form = await authed_post(request)
    j = c.s.get(Job, job_id)
    auto = load(c.s, AutomationSettings)
    if j is None or j.apply_method not in SUPPORTED_APPLY_METHODS:
        return back(c, f"/jobs/{job_id}", "Refused: this job cannot be applied to automatically")
    if c.s.scalar(select(Application).where(Application.job_id == j.id, Application.mode == auto.mode)):
        return back(c, f"/jobs/{job_id}", "An application for this job already exists in this mode")
    cv = prof.active_cv(c.s, prof.get_or_create_profile(c.s, c.user.id))
    if cv is None:
        return back(c, f"/jobs/{job_id}", "Refused: upload a CV first")
    a = Application(job_id=j.id, mode=auto.mode, status=S.EVALUATED.value, cv_version_id=cv.id)
    c.s.add(a)
    c.s.flush()
    transition(c.s, a, S.QUEUED, event="admin_queue", reason=f"Manually queued by {c.user.email}")
    c.audit("queue_job", f"job:{j.id}", application_id=a.id)
    return back(c, f"/applications/{a.id}", "Queued")


@app.get("/sources", response_class=HTMLResponse)
def sources(request: Request):
    if not (c := authed_get(request)):
        return _login_redirect()
    return render(c, "sources.html", sources=c.s.scalars(select(JobSource).order_by(JobSource.id)).all())


@app.post("/sources")
async def sources_post(request: Request):
    c, form = await authed_post(request)
    action = form.get("action")
    if action == "add":
        connector = str(form.get("connector"))
        ident = str(form.get("identifier", "")).strip()
        from ..connectors.discovery import DISCOVERY_CONNECTORS, _SAFE_ID

        if connector not in DISCOVERY_CONNECTORS or not _SAFE_ID.match(ident):
            return back(c, "/sources", "Invalid connector or identifier")
        opts = {}
        if form.get("company_name"):
            opts["company_name"] = str(form.get("company_name"))[:200]
        if form.get("region") == "eu":
            opts["region"] = "eu"
        if c.s.scalar(select(JobSource).where(JobSource.connector == connector, JobSource.identifier == ident)):
            return back(c, "/sources", "Source already exists")
        c.s.add(JobSource(connector=connector, identifier=ident, display_name=opts.get("company_name"), options=opts))
        c.audit("source_add", f"{connector}:{ident}")
        return back(c, "/sources", "Source added")
    src = c.s.get(JobSource, int(form.get("source_id", 0)))
    if src is None:
        return back(c, "/sources", "Unknown source")
    if action == "toggle":
        src.enabled = not src.enabled
    elif action == "delete":
        c.s.delete(src)
    elif action == "run":
        tid = queue.enqueue(c.s, "discover", {"source_id": src.id},
                            dedupe_key=f"discover:{src.id}:manual:{int(utcnow().timestamp())}", priority=20)
        c.audit("run_search_now", f"source:{src.id}", task_id=tid)
        return back(c, "/sources", f"Search queued (task {tid}); a worker must be running to execute it")
    c.audit(f"source_{action}", f"source:{src.id}")
    return back(c, "/sources", f"{action} done")


# ------------------------------------------------------------------ platforms & credentials


@app.get("/platforms", response_class=HTMLResponse)
def platforms(request: Request):
    if not (c := authed_get(request)):
        return _login_redirect()
    creds = {v.platform_key: v for v in list_credentials(c.s, c.user.id)}
    plats = c.s.scalars(select(Platform).order_by(Platform.automatable.desc(), Platform.key)).all()
    return render(c, "platforms.html", platforms=plats, creds=creds)


@app.post("/platforms/{key}")
async def platform_post(request: Request, key: str):
    c, form = await authed_post(request)
    p = c.s.get(Platform, key)
    if p is None or not p.automatable:
        return back(c, "/platforms", "Refused: platform is NOT AUTOMATABLE")
    action = form.get("action")
    if action == "config" and p.requires_login:
        from ..browser.login import PortalLoginConfig

        try:
            cfg = PortalLoginConfig(login_url=str(form.get("login_url")), username_selector=str(form.get("username_selector")),
                                    password_selector=str(form.get("password_selector")),
                                    submit_selector=str(form.get("submit_selector")),
                                    success_selector=str(form.get("success_selector") or "") or None,
                                    success_url_regex=str(form.get("success_url_regex") or "") or None)
        except Exception as e:
            return back(c, "/platforms", f"Invalid configuration: {e}")
        p.config = json.loads(cfg.model_dump_json())
        c.audit("platform_config", key)
        return back(c, "/platforms", "Configuration saved")
    if action == "test_login":
        tid = queue.enqueue(c.s, "login_test", {"platform_key": key, "user_id": c.user.id},
                            dedupe_key=f"login_test:{key}:{int(utcnow().timestamp())}", priority=15, max_attempts=1)
        c.audit("test_login", key, task_id=tid)
        return back(c, "/platforms", f"Login test queued (task {tid}); result appears here after a worker runs it")
    return back(c, "/platforms", "Unknown action")


@app.get("/credentials", response_class=HTMLResponse)
def credentials(request: Request):
    if not (c := authed_get(request)):
        return _login_redirect()
    plats = [p.key for p in c.s.scalars(select(Platform).where(Platform.automatable.is_(True), Platform.requires_login.is_(True)))]
    return render(c, "credentials.html", creds=list_credentials(c.s, c.user.id),
                  platform_keys=plats + ["ai:anthropic", "ai:openai", "notify:smtp", "notify:telegram",
                                         "reconcile:imap"])


@app.post("/credentials")
async def credentials_post(request: Request):
    c, form = await authed_post(request)
    action = form.get("action")
    if action == "store":
        key = str(form.get("platform_key", ""))
        p = c.s.get(Platform, key)
        if not key.startswith(("ai:", "notify:", "reconcile:")) and (p is None or not p.automatable):
            return back(c, "/credentials", "Refused: credentials are only stored for automatable platforms")
        secret = str(form.get("secret", ""))
        if not secret:
            return back(c, "/credentials", "Secret is required")
        rot = form.get("rotate_after_days")
        store_credential(c.s, user_id=c.user.id, platform_key=key, username=str(form.get("username") or "") or None,
                         secret=secret, mfa_mode=str(form.get("mfa_mode") or "none"),
                         rotate_after_days=int(rot) if rot else None)
        if p is not None and p.requires_login:
            p.status, p.status_reason = "NOT_CONFIGURED", "Credential stored; not yet tested (use TEST LOGIN)"
        c.audit("credential_store", key)  # the secret itself is never logged
        return back(c, "/credentials", "Stored (encrypted). Not tested yet.")
    if action == "delete":
        ok = delete_credential(c.s, c.user.id, int(form.get("credential_id", 0)))
        c.audit("credential_delete", str(form.get("credential_id")))
        return back(c, "/credentials", "Deleted" if ok else "Not found")
    return back(c, "/credentials", "Unknown action")


# ------------------------------------------------------------------ profile, facts, CV


@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    if not (c := authed_get(request)):
        return _login_redirect()
    p = prof.get_or_create_profile(c.s, c.user.id)
    facts = c.s.scalars(select(CandidateFact).where(CandidateFact.profile_id == p.id)
                        .order_by(CandidateFact.category, CandidateFact.group_key, CandidateFact.key)).all()
    kb = prof.knowledge(c.s, p)
    return render(c, "profile.html", p=p, facts=facts, prefs=prof.preferences(p), rules=prof.rules(p),
                  categories=FACT_CATEGORIES, statuses=[x.value for x in FactStatus],
                  pro_years=kb.professional_years())


@app.post("/profile/facts")
async def profile_facts(request: Request):
    c, form = await authed_post(request)
    p = prof.get_or_create_profile(c.s, c.user.id)
    action = form.get("action")
    if action == "add":
        cat = str(form.get("category"))
        key = str(form.get("key", "")).strip()[:128]
        if cat not in FACT_CATEGORIES or not key:
            return back(c, "/profile", "Category and key are required")
        group = str(form.get("group_key") or "").strip() or None
        if group == "new":
            group = prof.new_group_key({"employment": "emp", "education": "edu", "project": "proj"}.get(cat, cat))
        prof.set_fact(c.s, p, cat, key, str(form.get("value", "")), group_key=group,
                      status=FactStatus(str(form.get("status") or "VERIFIED")))
        c.audit("fact_set", f"{cat}.{key}")
        return back(c, "/profile", f"Saved {cat}.{key}")
    if action == "verify_all_extracted":
        n = 0
        for f in c.s.scalars(select(CandidateFact).where(CandidateFact.profile_id == p.id,
                                                          CandidateFact.status == "EXTRACTED")):
            prof.verify_fact(c.s, p, f.id)
            n += 1
        c.audit("facts_verify_all", None, count=n)
        return back(c, "/profile", f"{n} extracted facts confirmed as VERIFIED")
    f = c.s.get(CandidateFact, int(form.get("fact_id", 0)))
    if f is None or f.profile_id != p.id:
        return back(c, "/profile", "Fact not found")
    if action == "verify":
        prof.verify_fact(c.s, p, f.id, str(form.get("value")) if form.get("value") is not None else None)
    elif action == "status":
        f.status = FactStatus(str(form.get("status"))).value
        f.updated_at = utcnow()
    elif action == "delete":
        c.s.delete(f)
    c.audit(f"fact_{action}", f"fact:{f.id}")
    return back(c, "/profile", f"{action} done")


@app.post("/profile/preferences")
async def profile_preferences(request: Request):
    c, form = await authed_post(request)
    p = prof.get_or_create_profile(c.s, c.user.id)
    try:
        prefs = Preferences(
            target_roles=_split(form.get("target_roles")), target_industries=_split(form.get("target_industries")),
            target_locations=_split(form.get("target_locations")),
            workplace_types=[w for w in _split(form.get("workplace_types")) if w in ("remote", "hybrid", "onsite")],
            min_salary={"amount": float(form.get("min_salary_amount")) if form.get("min_salary_amount") else None,
                        "currency": str(form.get("min_salary_currency") or "") or None,
                        "interval": str(form.get("min_salary_interval") or "month")},
            max_commute_km=float(form.get("max_commute_km")) if form.get("max_commute_km") else None,
            max_required_experience_years=float(form.get("max_required_experience_years"))
            if form.get("max_required_experience_years") else None,
            exclude_keywords=_split(form.get("exclude_keywords")), exclude_companies=_split(form.get("exclude_companies")),
            employment_types=_split(form.get("employment_types")), keywords=_split(form.get("keywords")),
            required_skills=_split(form.get("required_skills")), optional_skills=_split(form.get("optional_skills")),
            min_match_score=float(form.get("min_match_score") or 60),
        )
    except Exception as e:
        return back(c, "/profile", f"Invalid preferences: {e}")
    p.preferences = prefs.model_dump()
    p.updated_at = utcnow()
    c.audit("preferences_update", None)
    return back(c, "/profile", "Preferences saved")


@app.post("/profile/rules")
async def profile_rules(request: Request):
    c, form = await authed_post(request)
    p = prof.get_or_create_profile(c.s, c.user.id)
    b = lambda k: form.get(k) == "on"  # noqa: E731
    try:
        r = Rules(
            require_target_role=b("require_target_role"), require_location_match=b("require_location_match"),
            require_employment_type_match=b("require_employment_type_match"), require_min_score=b("require_min_score"),
            skip_if_experience_exceeds=b("skip_if_experience_exceeds"),
            on_rule_failure=str(form.get("on_rule_failure")), on_unknown_mandatory_answer=str(form.get("on_unknown_mandatory_answer")),
            allow_inferred_answers=b("allow_inferred_answers"), treat_unlisted_skills_as_no=b("treat_unlisted_skills_as_no"),
            eeo_decline_if_available=b("eeo_decline_if_available"), accept_privacy_notices=b("accept_privacy_notices"),
            referral_source_answer=str(form.get("referral_source_answer") or "") or None,
            generate_cover_letters=b("generate_cover_letters"),
        )
    except Exception as e:
        return back(c, "/profile", f"Invalid rules: {e}")
    before = p.rules
    p.rules = r.model_dump()
    p.updated_at = utcnow()
    c.audit("rules_update", None, before=json.dumps(before), after=json.dumps(p.rules))
    return back(c, "/profile", "Rules saved")


@app.get("/profile/export")
def profile_export(request: Request):
    if not (c := authed_get(request)):
        raise HTTPException(401)
    data = prof.export_profile(c.s, prof.get_or_create_profile(c.s, c.user.id))
    c.audit("profile_export")
    c.close()
    return Response(json.dumps(data, indent=2, default=str), media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=candidate-data.json"})


@app.post("/profile/delete")
async def profile_delete(request: Request):
    c, form = await authed_post(request)
    if form.get("confirm") != "DELETE":
        return back(c, "/profile", "Type DELETE to confirm")
    prof.delete_candidate_data(c.s, prof.get_or_create_profile(c.s, c.user.id))
    c.audit("profile_delete")
    return back(c, "/profile", "Candidate facts and CV files deleted")


@app.get("/cv", response_class=HTMLResponse)
def cv_page(request: Request):
    if not (c := authed_get(request)):
        return _login_redirect()
    p = prof.get_or_create_profile(c.s, c.user.id)
    cvs = c.s.scalars(select(CVVersion).where(CVVersion.profile_id == p.id).order_by(CVVersion.version.desc())).all()
    usage = {cv.id: prof.cv_usage(c.s, cv.id) for cv in cvs}
    return render(c, "cv.html", cvs=cvs, usage=usage, max_mb=get_config().max_upload_mb)


@app.post("/cv")
async def cv_post(request: Request):
    c, form = await authed_post(request)
    p = prof.get_or_create_profile(c.s, c.user.id)
    action = form.get("action")
    if action == "upload":
        up = form.get("file")
        if up is None or not getattr(up, "filename", None):
            return back(c, "/cv", "Choose a file")
        data = await up.read(get_config().max_upload_mb * 1024 * 1024 + 1)
        try:
            cv = prof.store_cv(c.s, p, up.filename, data)
        except CVParseError as e:
            return back(c, "/cv", f"Rejected: {e}")
        c.audit("cv_upload", f"cv:{cv.id}", sha256=cv.sha256, version=cv.version)
        return back(c, "/cv", f"Version {cv.version} stored ({cv.parse_status}). Review extracted facts on the Profile page.")
    cv = c.s.get(CVVersion, int(form.get("cv_id", 0)))
    if cv is None or cv.profile_id != p.id:
        return back(c, "/cv", "Not found")
    if action == "activate":
        prof.activate_cv(c.s, p, cv)
        c.audit("cv_activate", f"cv:{cv.id}")
        return back(c, "/cv", f"Version {cv.version} is now used for new applications")
    return back(c, "/cv", "Unknown action")


@app.get("/cv/{cv_id}/download")
def cv_download(request: Request, cv_id: int):
    if not (c := authed_get(request)):
        raise HTTPException(401)
    p = prof.get_or_create_profile(c.s, c.user.id)
    cv = c.s.get(CVVersion, cv_id)
    if cv is None or cv.profile_id != p.id:
        c.close()
        raise HTTPException(404)
    data = prof.read_cv(cv)
    c.audit("cv_download", f"cv:{cv.id}")
    c.close()
    return Response(data, media_type=cv.mime_type,
                    headers={"Content-Disposition": f"attachment; filename=\"cv-v{cv.version}\""})


# ------------------------------------------------------------------ automation, reports, errors, audit, settings


@app.get("/automation", response_class=HTMLResponse)
def automation(request: Request):
    if not (c := authed_get(request)):
        return _login_redirect()
    tasks = c.s.scalars(select(Task).order_by(Task.id.desc()).limit(50)).all()
    return render(c, "automation.html", tasks=tasks)


@app.post("/automation")
async def automation_post(request: Request):
    c, form = await authed_post(request)
    auto = load(c.s, AutomationSettings)
    action = form.get("action")
    before = auto.model_dump()
    if action in ("start", "resume"):
        auto.state = "RUNNING"
    elif action == "pause":
        auto.state = "PAUSED"
    elif action == "stop":
        auto.state = "STOPPED"
        queue.cancel_pending(c.s, ["discover", "apply"])
    elif action == "mode":
        target = str(form.get("mode"))
        if target == "LIVE" and form.get("confirm") != "LIVE":
            return back(c, "/automation", "Type LIVE to confirm real submissions")
        if target not in ("LIVE", "DRY_RUN"):
            return back(c, "/automation", "Invalid mode")
        from ..security.destinations import live_submissions_allowed

        if target == "LIVE" and not live_submissions_allowed():
            return back(c, "/automation", f"Refused: LIVE mode requires JOBAP_ENVIRONMENT=production "
                                          f"(this deployment is '{get_config().environment}')")
        auto.mode = target
    elif action == "settings":
        try:
            auto = AutomationSettings.model_validate({**auto.model_dump(), **{
                k: (form.get(k) == "on" if k == "apply_to_duplicates" else form.get(k))
                for k in ("search_interval_minutes", "min_minutes_between_applications", "max_applications_per_day",
                          "max_applications_per_platform_per_day", "allowed_hours_start", "allowed_hours_end",
                          "timezone", "daily_report_time", "max_retries", "retry_base_seconds",
                          "request_min_interval_seconds", "apply_to_duplicates")}})
        except Exception as e:
            return back(c, "/automation", f"Invalid settings: {e}")
    elif action == "search_now":
        n = 0
        for src in c.s.scalars(select(JobSource).where(JobSource.enabled.is_(True))):
            if queue.enqueue(c.s, "discover", {"source_id": src.id},
                             dedupe_key=f"discover:{src.id}:manual:{int(utcnow().timestamp())}", priority=20):
                n += 1
        c.audit("run_search_now", None, sources=n)
        return back(c, "/automation", f"{n} search task(s) queued" + ("" if n else " (no enabled sources)"))
    elif action == "report_now":
        r = generate(c.s, trigger="manual")
        c.audit("generate_report_now", f"report:{r.id}")
        return back(c, f"/reports/{r.id}", "Report generated from current database values")
    else:
        return back(c, "/automation", "Unknown action")
    save(c.s, auto)
    c.audit(f"automation_{action}", None, before=json.dumps(before), after=json.dumps(auto.model_dump()))
    return back(c, "/automation", f"{action}: state={auto.state}, mode={auto.mode}")


@app.get("/reports", response_class=HTMLResponse)
def reports(request: Request):
    if not (c := authed_get(request)):
        return _login_redirect()
    return render(c, "reports.html", reports=c.s.scalars(select(Report).order_by(Report.id.desc()).limit(200)).all())


@app.get("/reports/{rid}", response_class=HTMLResponse)
def report_detail(request: Request, rid: int):
    if not (c := authed_get(request)):
        return _login_redirect()
    r = c.s.get(Report, rid)
    if r is None:
        c.close()
        raise HTTPException(404)
    return render(c, "report.html", r=r)


@app.get("/errors", response_class=HTMLResponse)
def errors(request: Request):
    if not (c := authed_get(request)):
        return _login_redirect()
    return render(c, "errors.html", errors=c.s.scalars(select(ErrorRecord).order_by(ErrorRecord.id.desc()).limit(300)).all())


@app.post("/errors/{eid}/resolve")
async def error_resolve(request: Request, eid: int):
    c, _ = await authed_post(request)
    e = c.s.get(ErrorRecord, eid)
    if e:
        e.resolved = True
        c.audit("error_resolve", f"error:{eid}")
    return back(c, "/errors", "Marked resolved")


@app.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request):
    if not (c := authed_get(request)):
        return _login_redirect()
    return render(c, "audit.html", rows=c.s.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(500)).all())


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    if not (c := authed_get(request)):
        return _login_redirect()
    from ..settings_store import NotificationSettings, ReconcileSettings

    return render(c, "settings.html", ai=load(c.s, AISettings), ns=load(c.s, NotificationSettings),
                  rs=load(c.s, ReconcileSettings), env=get_config().environment,
                  public_base_url=get_config().public_base_url)


@app.post("/settings")
async def settings_post(request: Request):
    c, form = await authed_post(request)
    ai = load(c.s, AISettings)
    from ..settings_store import NotificationSettings, ReconcileSettings

    if form.get("action") == "notifications":
        try:
            ns = NotificationSettings(
                email_enabled=form.get("email_enabled") == "on", smtp_host=str(form.get("smtp_host") or "").strip(),
                smtp_port=int(form.get("smtp_port") or 587), smtp_security=str(form.get("smtp_security") or "starttls"),
                smtp_username=str(form.get("smtp_username") or "").strip(),
                email_from=str(form.get("email_from") or "").strip(), email_to=str(form.get("email_to") or "").strip(),
                telegram_enabled=form.get("telegram_enabled") == "on",
                telegram_chat_id=str(form.get("telegram_chat_id") or "").strip(),
                telegram_api_base=str(form.get("telegram_api_base") or "https://api.telegram.org").strip())
        except Exception as e:
            return back(c, "/settings", f"Invalid notification settings: {e}")
        save(c.s, ns)
        c.audit("notification_settings", None, email=ns.email_enabled, telegram=ns.telegram_enabled)
        return back(c, "/settings", "Notification settings saved")
    if form.get("action") == "test_notify":
        from ..notifications import enabled_channels, notify

        n = notify(c.s, "test", "Test notification", "If you can read this, this channel works.",
                   link_path="/notifications")
        queue.enqueue(c.s, "deliver_notifications", {}, dedupe_key=f"notify:test:{n.id}", priority=3, max_attempts=1)
        c.audit("test_notification", None, channels=",".join(enabled_channels(c.s)))
        return back(c, "/notifications", "Test notification created; external channels are sent by a worker")
    if form.get("action") == "reconcile":
        try:
            rs = ReconcileSettings(imap_enabled=form.get("imap_enabled") == "on",
                                   imap_host=str(form.get("imap_host") or "").strip(),
                                   imap_port=int(form.get("imap_port") or 993),
                                   imap_username=str(form.get("imap_username") or "").strip(),
                                   imap_folder=str(form.get("imap_folder") or "INBOX").strip(),
                                   lookback_days=int(form.get("lookback_days") or 3))
        except Exception as e:
            return back(c, "/settings", f"Invalid reconciliation settings: {e}")
        save(c.s, rs)
        c.audit("reconcile_settings", None, enabled=rs.imap_enabled)
        return back(c, "/settings", "Reconciliation settings saved")
    if form.get("action") == "test_ai":
        tid = queue.enqueue(c.s, "ai_health", {"user_id": c.user.id},
                            dedupe_key=f"ai_health:{int(utcnow().timestamp())}", priority=15, max_attempts=1)
        c.audit("test_ai", None, task_id=tid)
        return back(c, "/settings", f"AI connectivity test queued (task {tid})")
    try:
        ai = AISettings.model_validate({**ai.model_dump(), "provider": form.get("provider"),
                                        "model": str(form.get("model") or "").strip(),
                                        "base_url": str(form.get("base_url") or "").strip().rstrip("/"),
                                        "allow_candidate_data": form.get("allow_candidate_data") == "on",
                                        "last_check_ok": None, "last_check_message": None, "last_check_at": None})
    except Exception as e:
        return back(c, "/settings", f"Invalid: {e}")
    save(c.s, ai)
    c.audit("ai_settings", None, provider=ai.provider, model=ai.model, allow_candidate_data=ai.allow_candidate_data)
    return back(c, "/settings", "AI settings saved (not yet tested)")


from . import ops  # noqa: E402,F401  (registers operations / verification routes)
