"""FastAPI application factory for the policy-engine service."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from policy_engine import __version__
from policy_engine.config import Settings


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


def create_app() -> FastAPI:
    settings = Settings.from_env()
    app = FastAPI(
        title="GRIDKEEP Policy Engine",
        version=__version__,
        description=(
            "Milestone 1 foundation: service scaffolding only. "
            "Sovereignty policy evaluation, simulation, and conflict "
            "detection are implemented in Milestone 3."
        ),
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__, environment=settings.environment)

    return app


app = create_app()
