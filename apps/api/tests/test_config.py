from app.core.config import Settings


def test_comma_separated_origins_are_parsed() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://x:x@localhost:5432/x",
        redis_url="redis://localhost:6379/0",
        celery_broker_url="redis://localhost:6379/1",
        celery_result_backend="redis://localhost:6379/2",
        s3_endpoint="http://localhost:9000",
        s3_access_key="test",
        s3_secret_key="test-secret",
        allowed_origins="https://example.com,https://ar.example.com",  # type: ignore[arg-type]
        secret_key="test-secret-key-with-more-than-32-characters",
    )

    assert [str(origin).rstrip("/") for origin in settings.allowed_origins] == [
        "https://example.com",
        "https://ar.example.com",
    ]
