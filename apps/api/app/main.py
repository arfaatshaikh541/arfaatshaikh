import time

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.db import engine
from app.core.errors import NotFoundError, register_exception_handlers
from app.core.logging import (
    configure_logging,
    new_request_id,
    request_id_var,
    tenant_id_var,
    user_id_var,
)
from app.core.storage import LocalDiskAdapter, get_storage_adapter
from app.modules.assignment.routes import router as assignment_router
from app.modules.booking.routes import (
    appointment_types_router,
    availability_router,
)
from app.modules.booking.routes import (
    public_router as public_booking_router,
)
from app.modules.booking.routes import (
    router as appointments_router,
)
from app.modules.communications.routes import router as communications_router
from app.modules.crm.routes import (
    leads_crm_router,
    pipelines_router,
    tags_router,
    tasks_router,
)
from app.modules.deadlines.routes import router as deadlines_router
from app.modules.documents.routes import (
    public_router as public_documents_router,
)
from app.modules.documents.routes import (
    router as document_requests_router,
)
from app.modules.entitlements.routes import router as entitlements_router
from app.modules.identity.routes import router as auth_router
from app.modules.identity.tenant_routes import router as tenant_users_router
from app.modules.leads.routes import (
    public_router as public_capture_router,
)
from app.modules.leads.routes import (
    qualification_forms_router,
)
from app.modules.leads.routes import (
    router as leads_router,
)
from app.modules.leads.routes import (
    services_router as leads_services_router,
)
from app.modules.onboarding.routes import (
    router as onboarding_cases_router,
)
from app.modules.onboarding.routes import (
    templates_router as onboarding_templates_router,
)
from app.modules.permissions.routes import router as roles_router
from app.modules.platform_admin.routes import router as platform_admin_router
from app.modules.portal.routes import (
    auth_router as portal_auth_router,
)
from app.modules.portal.routes import (
    router as portal_content_router,
)
from app.modules.portal.routes import (
    staff_router as portal_accounts_router,
)
from app.modules.proposals.routes import (
    public_router as public_proposals_router,
)
from app.modules.proposals.routes import (
    router as proposals_router,
)
from app.modules.proposals.routes import (
    templates_router as proposal_templates_router,
)
from app.modules.scoring.routes import router as scoring_router
from app.modules.subscriptions.routes import router as subscriptions_router
from app.modules.tenancy.routes import router as tenant_settings_router
from app.modules.workflow_automation.routes import router as workflows_router

settings = get_settings()
configure_logging(settings.log_level)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Stamps every request with a request id (returned in the response
    header for client-side correlation) and clears the per-request
    logging context vars afterward so they never leak across requests on
    a reused worker thread."""

    async def dispatch(self, request: Request, call_next):
        request_id = new_request_id()
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
            tenant_id_var.set("-")
            user_id_var.set("-")
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="Client Operations Platform API",
        version="0.1.0",
        docs_url=None if settings.api_docs_disabled else "/docs",
        redoc_url=None if settings.api_docs_disabled else "/redoc",
        openapi_url=None if settings.api_docs_disabled else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    app.add_middleware(RequestContextMiddleware)

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    register_exception_handlers(app)

    api_router = APIRouter(prefix="/api")
    for router in (
        auth_router,
        tenant_users_router,
        tenant_settings_router,
        roles_router,
        subscriptions_router,
        entitlements_router,
        platform_admin_router,
        public_capture_router,
        leads_router,
        leads_services_router,
        qualification_forms_router,
        pipelines_router,
        leads_crm_router,
        tasks_router,
        tags_router,
        scoring_router,
        assignment_router,
        communications_router,
        public_booking_router,
        appointment_types_router,
        availability_router,
        appointments_router,
        workflows_router,
        public_proposals_router,
        proposal_templates_router,
        proposals_router,
        public_documents_router,
        document_requests_router,
        onboarding_templates_router,
        onboarding_cases_router,
        deadlines_router,
        portal_auth_router,
        portal_content_router,
        portal_accounts_router,
    ):
        api_router.include_router(router)

    @api_router.get("/files/{token}")
    def download_file(token: str) -> Response:
        adapter = get_storage_adapter()
        if not isinstance(adapter, LocalDiskAdapter):
            raise NotFoundError("Not found.")
        key = adapter.resolve_token(token)
        if key is None:
            raise NotFoundError("This download link is invalid or has expired.")
        return Response(content=adapter.read(key), media_type="application/octet-stream")

    app.include_router(api_router)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            return {"status": "not_ready", "database": "unreachable"}
        return {"status": "ready", "database": "reachable"}

    return app


app = create_app()
