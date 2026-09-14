from app.core.config import Settings
from app.services.ai_provider import ExternalProvider, OllamaProvider, get_ai_provider


def _settings(**overrides) -> Settings:
    base = dict(
        database_url="postgresql+asyncpg://x:x@localhost:5432/x",
        redis_url="redis://localhost:6379/0",
        celery_broker_url="redis://localhost:6379/1",
        celery_result_backend="redis://localhost:6379/2",
        s3_endpoint="http://localhost:9000",
        s3_access_key="test",
        s3_secret_key="test-secret",
        secret_key="test-secret-key-with-more-than-32-characters",
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


async def test_ollama_provider_reports_unavailable_when_no_daemon_is_running():
    # No Ollama daemon exists in the test environment - this exercises the
    # real, expected-in-CI failure path, not a mock.
    provider = OllamaProvider(
        base_url="http://localhost:11434", model="llama3.1", timeout_seconds=1.0,
    )
    assert await provider.is_available() is False
    result = await provider.generate("What is the ruling on X?")
    assert result.available is False
    assert result.provider == "ollama"
    assert result.text is None
    assert result.error is not None
    assert "local_ai_unavailable" in result.error


async def test_ollama_provider_never_raises_on_connection_failure():
    provider = OllamaProvider(base_url="http://127.0.0.1:1", model="llama3.1", timeout_seconds=1.0)
    result = await provider.generate("hello")
    assert result.available is False


async def test_external_provider_is_always_unavailable_by_construction():
    provider = ExternalProvider()
    assert await provider.is_available() is False
    result = await provider.generate("anything")
    assert result.available is False
    assert "disabled" in (result.error or "")


def test_get_ai_provider_defaults_to_local_ollama():
    provider = get_ai_provider(_settings())
    assert isinstance(provider, OllamaProvider)


def test_get_ai_provider_returns_external_stub_even_when_mode_is_external_but_not_enabled():
    provider = get_ai_provider(_settings(ai_mode="external", external_ai_enabled=False))
    assert isinstance(provider, ExternalProvider)


def test_get_ai_provider_never_returns_a_provider_that_can_reach_a_paid_api():
    # Even the maximally-permissive configuration this codebase supports
    # (external mode + the opt-in flag) resolves to the disabled stub,
    # because no concrete paid-API implementation is wired in here.
    provider = get_ai_provider(_settings(ai_mode="external", external_ai_enabled=True))
    assert isinstance(provider, ExternalProvider)
