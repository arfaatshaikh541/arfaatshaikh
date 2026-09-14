from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.infrastructure.health import DependencyHealth
from app.main import app


def test_readiness_reports_each_dependency() -> None:
    health = DependencyHealth(postgres=True, redis=False, object_storage=True)
    with patch("app.api.routes.health.check_dependencies", new=AsyncMock(return_value=health)):
        with TestClient(app) as client:
            response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "service": "world-of-islam-api",
        "dependencies": {
            "postgres": True,
            "redis": False,
            "object_storage": True,
            "ready": False,
        },
    }
