from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

# Ensures every model module is registered (and cross-module string FK
# targets like Campaign.tenant_id -> "tenants.id" are resolvable) before
# any request touches the ORM, regardless of which routers happen to
# import which model modules. See worker/celery_app.py for the same
# requirement on the worker side, and the ADR-0007-adjacent bug this
# guards against.
from app.core import model_registry  # noqa: F401
from app.core.config import get_settings
from app.core.db import engine
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.modules.audit.routes import router as audit_router
from app.modules.businesses.routes import duplicates_router, merges_router
from app.modules.businesses.routes import router as businesses_router
from app.modules.campaigns.routes import router as campaigns_router
from app.modules.identity.routes import router as identity_router
from app.modules.leads.routes import router as leads_router
from app.modules.leads.routes import saved_views_router
from app.modules.platform_admin.routes import router as platform_admin_router
from app.modules.subscriptions.routes import router as subscriptions_router
from app.modules.tenancy.routes import router as tenancy_router
from app.modules.usage.routes import router as usage_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    yield
    await engine.dispose()


settings = get_settings()

app = FastAPI(
    title="GRIDKEEP Lead Intelligence API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-Id"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)

register_exception_handlers(app)

app.include_router(identity_router)
app.include_router(tenancy_router)
app.include_router(campaigns_router)
app.include_router(businesses_router)
app.include_router(duplicates_router)
app.include_router(merges_router)
app.include_router(leads_router)
app.include_router(saved_views_router)
app.include_router(usage_router)
app.include_router(subscriptions_router)
app.include_router(audit_router)
app.include_router(platform_admin_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ready"}
