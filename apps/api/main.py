from __future__ import annotations

import structlog
from fastapi import FastAPI
from sqlalchemy import text

from core.config import settings
from core.errors import register_exception_handlers
from core.middleware import install_middleware
from db.session import get_engine
from modules.assets.routes import router as assets_router
from modules.credential_vault.routes import router as credential_vault_router
from modules.identity.routes import router as identity_router
from modules.integrations.routes import router as integrations_router
from modules.permissions.routes import router as permissions_router
from modules.platform_admin.routes import router as platform_admin_router
from modules.platform_admin.routes import tenant_router as support_access_tenant_router
from modules.subscriptions.routes import router as subscriptions_router
from modules.tenancy.routes import router as tenancy_router

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

app = FastAPI(
    title="GRIDKEEP Cyber OS API",
    version="0.1.0",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if not settings.is_production else None,
)

install_middleware(app, settings)
register_exception_handlers(app)

app.include_router(tenancy_router)
app.include_router(identity_router)
app.include_router(permissions_router)
app.include_router(subscriptions_router)
app.include_router(credential_vault_router)
app.include_router(platform_admin_router)
app.include_router(support_access_tenant_router)
app.include_router(integrations_router)
app.include_router(assets_router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict:
    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ready"}
