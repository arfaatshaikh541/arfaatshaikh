from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WOI_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database_url: str
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle_seconds: int = 1800
    db_echo: bool = False
    redis_url: str
    celery_broker_url: str
    celery_result_backend: str
    s3_endpoint: AnyHttpUrl
    s3_access_key: str
    s3_secret_key: SecretStr
    s3_bucket: str = "world-of-islam"
    allowed_origins: Annotated[list[AnyHttpUrl], NoDecode] = Field(default_factory=list)
    secret_key: SecretStr
    session_cookie_name: str = "woi_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 30
    email_verification_ttl_seconds: int = 60 * 60 * 24
    password_reset_ttl_seconds: int = 60 * 30
    cookie_secure: bool = False
    # Scopes the session cookie to the deployment's base path (e.g. "/worldofislam")
    # so it is never sent to unrelated applications sharing the same host.
    cookie_path: str = "/"
    auth_rate_limit: int = 10
    # Set when a reverse proxy forwards the external subpath verbatim instead of
    # stripping it (e.g. "/worldofislam/api"), so generated OpenAPI/docs URLs and
    # redirects resolve correctly. Leave empty when the proxy strips the prefix
    # before forwarding to this service (the documented default).
    root_path: str = ""

    # --- AI provider (see app/services/ai_provider.py) ---
    # "local" (default) only ever talks to a self-hosted Ollama instance.
    # "external" is a hard opt-in: it does nothing unless external_ai_enabled
    # is ALSO set to true, so a deployment can never silently start billing
    # a paid AI API just because this field was set carelessly.
    ai_mode: Literal["local", "external"] = "local"
    external_ai_enabled: bool = False
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_timeout_seconds: float = 30.0

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("WOI_SECRET_KEY must contain at least 32 characters")
        return value

    @model_validator(mode="after")
    def enforce_production_safety(self) -> "Settings":
        if self.environment == "production":
            problems = production_problems(self)
            if problems:
                raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


PLACEHOLDER_MARKERS = ("replace-with", "change-me", "change-this", "local-redis-password", "devpassword", "example")


def production_problems(settings: "Settings") -> list[str]:
    """Configuration mistakes that must stop a production process from starting."""
    problems: list[str] = []
    if not settings.cookie_secure:
        problems.append("WOI_COOKIE_SECURE must be true")
    if not settings.allowed_origins:
        problems.append("WOI_ALLOWED_ORIGINS must list the public origin")
    for origin in settings.allowed_origins:
        text = str(origin)
        if origin.scheme != "https" or origin.host in {"localhost", "127.0.0.1", "::1"}:
            problems.append(f"WOI_ALLOWED_ORIGINS entry {text} must be an https, non-localhost origin")
    secrets = {
        "WOI_SECRET_KEY": settings.secret_key.get_secret_value(),
        "WOI_S3_SECRET_KEY": settings.s3_secret_key.get_secret_value(),
        "WOI_DATABASE_URL": settings.database_url,
        "WOI_REDIS_URL": settings.redis_url,
    }
    for name, value in secrets.items():
        if any(marker in value.lower() for marker in PLACEHOLDER_MARKERS):
            problems.append(f"{name} still contains a placeholder value")
    if settings.external_ai_enabled:
        problems.append("WOI_EXTERNAL_AI_ENABLED must stay false unless the owner has approved an external provider (not supported in this release)")
    return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
