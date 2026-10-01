import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE = dict(
    database_url="postgresql+asyncpg://woi:Zk39sd8f2jk@postgres:5432/woi",
    redis_url="redis://:Zk39sd8f2jk@redis:6379/0",
    celery_broker_url="redis://:Zk39sd8f2jk@redis:6379/1",
    celery_result_backend="redis://:Zk39sd8f2jk@redis:6379/2",
    s3_endpoint="http://minio:9000",
    s3_access_key="woi",
    s3_secret_key="x" * 40,
    secret_key="k" * 48,
    environment="production",
    cookie_secure=True,
    allowed_origins=["https://app.arfaat.com"],
)


def make(**over):
    return Settings(_env_file=None, **{**BASE, **over})


def test_valid_production_settings_load():
    assert make().environment == "production"


@pytest.mark.parametrize("over", [
    {"cookie_secure": False},
    {"allowed_origins": []},
    {"allowed_origins": ["http://app.arfaat.com"]},
    {"allowed_origins": ["https://localhost"]},
    {"secret_key": "replace-with-at-least-32-random-characters"},
    {"s3_secret_key": "change-this-minio-secret"},
    {"redis_url": "redis://:local-redis-password@redis:6379/0"},
    {"external_ai_enabled": True},
])
def test_unsafe_production_settings_are_refused(over):
    with pytest.raises(ValidationError):
        make(**over)


def test_development_keeps_local_defaults():
    assert make(environment="development", cookie_secure=False, allowed_origins=["http://localhost:3000"]).environment == "development"
