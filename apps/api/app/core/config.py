from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced entirely from environment variables.

    Fails fast at startup if a required value is missing rather than
    silently running with an insecure default in a non-development
    environment.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_base_url: str = Field(default="http://localhost:8000")
    cors_allowed_origins: str = Field(default="http://localhost:3000")
    api_docs_disabled: bool = Field(default=False)

    app_secret_key: str = Field(...)

    session_cookie_name: str = Field(default="cops_session")
    session_cookie_secure: bool = Field(default=False)
    session_absolute_ttl_hours: int = Field(default=12)
    session_idle_ttl_minutes: int = Field(default=60)

    database_url: str = Field(...)
    migration_database_url: str = Field(...)

    redis_url: str = Field(default="redis://localhost:6379/0")
    rate_limit_redis_url: str = Field(default="redis://localhost:6379/3")
    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")

    storage_backend: str = Field(default="local")
    storage_local_root: str = Field(default="/data/storage")
    s3_endpoint_url: str | None = Field(default=None)
    s3_bucket: str = Field(default="cops-dev")
    s3_region: str = Field(default="us-east-1")
    s3_access_key_id: str | None = Field(default=None)
    s3_secret_access_key: str | None = Field(default=None)
    s3_use_path_style: bool = Field(default=True)

    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=1025)
    smtp_user: str | None = Field(default=None)
    smtp_password: str | None = Field(default=None)
    smtp_use_tls: bool = Field(default=False)
    email_from_address: str = Field(default="no-reply@dev.internal")
    email_from_name: str = Field(default="Client Operations Platform")

    seed_platform_admin_email: str = Field(default="platform-admin@dev.internal")
    seed_platform_admin_password: str = Field(default="ChangeMe!12345")
    seed_demo_tenant_slug: str = Field(default="rafana-advisory-demo")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
