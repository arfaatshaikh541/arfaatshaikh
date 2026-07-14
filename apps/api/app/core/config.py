from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    app_name: str = "LeadFlow"
    api_prefix: str = "/api"

    database_url: str = "postgresql+psycopg://leadflow:leadflow@localhost:5432/leadflow"
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "local-only-insecure-secret-key-change-me"
    field_encryption_key: str = "local-only-insecure-32-byte-key!!"

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    cors_origins: str = "http://localhost:3000"

    cookie_secure: bool = False
    cookie_domain: str | None = None

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    email_from_address: str = "no-reply@leadflow-demo.io"
    email_from_name: str = "LeadFlow"

    web_base_url: str = "http://localhost:3000"

    storage_backend: str = "local"
    storage_local_path: str = "./var/storage"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_region: str = "me-central-1"

    login_rate_limit_attempts: int = 5
    login_rate_limit_window_minutes: int = 15

    signup_rate_limit_attempts: int = 5
    signup_rate_limit_window_minutes: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @field_validator("secret_key", "field_encryption_key")
    @classmethod
    def _reject_placeholder_outside_local(cls, value: str, info) -> str:  # type: ignore[no-untyped-def]
        # Values are validated together with `environment` in `assert_production_safe`,
        # since pydantic v2 field order isn't guaranteed during validation.
        return value

    def assert_production_safe(self) -> None:
        if self.environment in ("local", "test"):
            return
        placeholders = {
            "local-only-insecure-secret-key-change-me",
            "local-only-insecure-32-byte-key!!",
        }
        if self.secret_key in placeholders or self.field_encryption_key in placeholders:
            raise RuntimeError(
                "Refusing to start: placeholder SECRET_KEY/FIELD_ENCRYPTION_KEY "
                f"detected outside local/test environment (environment={self.environment!r})."
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.assert_production_safe()
    return settings
