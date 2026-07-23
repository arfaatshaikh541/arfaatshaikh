"""FastAPI application factory for the policy-engine service."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from policy_engine import __version__
from policy_engine.config import Settings
from policy_engine.conflicts import ConflictCheckRequest, ConflictCheckResult, find_conflicts
from policy_engine.evaluate import evaluate
from policy_engine.schema import EvaluationRequest, EvaluationResult


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
            "Milestone 3: deterministic sovereignty-policy evaluation and "
            "conflict detection. Policy CRUD, versioning, and dual-control "
            "publish/approve/rollback live in control-api -- this service "
            "is a stateless evaluator control-api calls."
        ),
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__, environment=settings.environment)

    @app.post("/evaluate", response_model=EvaluationResult)
    def evaluate_endpoint(request: EvaluationRequest) -> EvaluationResult:
        # Also serves control-api's "simulation mode": simulation and real
        # evaluation run the identical deterministic pipeline (this service
        # has no side effects to suppress either way) -- the only
        # difference is whether the *caller* persists a PolicyEvaluationRecord
        # afterward, which is a control-api-side decision, not this
        # endpoint's.
        return evaluate(request)

    @app.post("/conflicts", response_model=ConflictCheckResult)
    def conflicts_endpoint(request: ConflictCheckRequest) -> ConflictCheckResult:
        return find_conflicts(request)

    return app


app = create_app()
