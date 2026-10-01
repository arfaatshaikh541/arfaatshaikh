"""Structural security rules enforced over every route, so a new endpoint cannot silently skip authentication,
CSRF protection or the administrator check."""
import inspect

from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session, get_current_user, require_csrf
from app.api.dependencies.platform_admin import require_platform_administrator
from app.main import app

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
# Endpoints that are reachable before a session exists (each is rate limited in its handler).
PRE_SESSION = {"/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/verify-email", "/api/v1/auth/password-reset/request", "/api/v1/auth/password-reset/confirm"}
# POST endpoints that only read (search/verification) and therefore need no CSRF token.
READ_ONLY_POST = {"/api/v1/verification/text", "/api/v1/retrieval/query", "/api/v1/assistant/classify", "/api/v1/assistant/assemble"}
# "/admin" in the path but intentionally open to any signed-in user (they only *request* a review; decisions are admin-only).
ADMIN_PATH_EXCEPTIONS = {"/api/v1/sources/admin/passages/{passage_id}/corrections"}


class RouteView:
    """Uniform view of a route across FastAPI versions (newer versions wrap included routers lazily)."""

    def __init__(self, route, path: str, methods: set):
        self.route, self.path, self.methods = route, path, methods
        self.dependant, self.endpoint = route.dependant, route.endpoint


def routes() -> list:
    found = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            found.append(RouteView(r, r.path, set(r.methods)))
        elif hasattr(r, "effective_route_contexts"):
            for ctx in r.effective_route_contexts():
                if isinstance(ctx.original_route, APIRoute):
                    found.append(RouteView(ctx.original_route, ctx.path, set(ctx.methods) or set(ctx.original_route.methods)))
    return found


def test_route_discovery_sees_the_whole_application():
    # Guards against the other tests passing vacuously if FastAPI changes how routers are exposed.
    assert len(routes()) > 300
    assert any(r.path == "/api/v1/auth/login" for r in routes())


def dependency_calls(route) -> set:
    found: set = set()

    def walk(dep):
        found.add(dep.call)
        for sub in dep.dependencies:
            walk(sub)
    walk(route.dependant)
    return found


def test_every_mutating_route_requires_csrf_unless_pre_session_or_pure():
    problems = []
    for r in routes():
        if not (r.methods & MUTATING) or r.path in PRE_SESSION or r.path in READ_ONLY_POST:
            continue
        if require_csrf in dependency_calls(r):
            continue
        takes_db = any(p.annotation is AsyncSession or "AsyncSession" in str(p.annotation) or "DbSession" in str(p.annotation) for p in inspect.signature(r.endpoint).parameters.values())
        if takes_db:
            problems.append(f"{sorted(r.methods)} {r.path}: writes with a database session but has no CSRF check")
    assert problems == []


def test_every_admin_route_requires_a_platform_administrator():
    problems = [f"{sorted(r.methods)} {r.path}" for r in routes() if "/admin" in r.path and r.path not in ADMIN_PATH_EXCEPTIONS
                and require_platform_administrator not in dependency_calls(r)]
    assert problems == []


def test_mutating_routes_other_than_pre_session_are_authenticated():
    problems = [f"{sorted(r.methods)} {r.path}" for r in routes() if (r.methods & MUTATING) and r.path not in PRE_SESSION and r.path not in READ_ONLY_POST
                and not ({get_current_user, get_current_session} & dependency_calls(r))]
    assert problems == []


def test_pre_session_routes_exist_and_are_exactly_the_documented_set():
    anonymous_mutating = {r.path for r in routes() if (r.methods & MUTATING) and not ({get_current_user, get_current_session} & dependency_calls(r))}
    assert anonymous_mutating <= PRE_SESSION | READ_ONLY_POST, anonymous_mutating - (PRE_SESSION | READ_ONLY_POST)


def test_raw_model_generation_is_not_available_to_ordinary_users():
    route = next(r for r in routes() if r.path == "/api/v1/intelligence/generate")
    assert require_platform_administrator in dependency_calls(route) and require_csrf in dependency_calls(route)


def test_openapi_docs_are_not_served_in_production_mode():
    import os
    import subprocess
    import sys
    code = "from app.main import app; print(app.docs_url, app.redoc_url, app.openapi_url)"
    env = {**os.environ, "WOI_ENVIRONMENT": "production", "WOI_COOKIE_SECURE": "true", "WOI_ALLOWED_ORIGINS": "https://app.example.org",
           "WOI_SECRET_KEY": "k" * 48, "WOI_S3_SECRET_KEY": "s" * 40, "WOI_DATABASE_URL": "postgresql+asyncpg://u:Zk39sd8f2jk@db/x", "WOI_REDIS_URL": "redis://:Zk39sd8f2jk@r/0"}
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, cwd=".")
    assert out.stdout.strip() == "None None None", out.stderr[-400:]
