from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.errors import ApplicationError, application_error_handler
from app.core.logging import configure_logging
from app.core.request_context import RequestContextMiddleware
from app.core.rate_limit import rate_limiter
from app.db.session import database

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("application_started", environment=settings.environment)
    yield
    await rate_limiter.close()
    await database.dispose()
    logger.info("application_stopped")


app = FastAPI(
    title="World of Islam API",
    version="0.3.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
    root_path=settings.root_path,
)
app.add_exception_handler(ApplicationError, application_error_handler)  # type: ignore[arg-type]
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin).rstrip("/") for origin in settings.allowed_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
)
# Health checks stay unprefixed and unversioned: orchestrators and reverse
# proxies probe them directly and must not depend on the API version or the
# public /worldofislam base path.
app.include_router(health_router)
app.include_router(router, prefix="/api/v1")
