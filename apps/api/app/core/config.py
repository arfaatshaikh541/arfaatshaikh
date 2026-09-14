from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
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

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("WOI_SECRET_KEY must contain at least 32 characters")
        return value

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
