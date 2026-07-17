from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-derived configuration. No environment-specific code
    branches elsewhere in the app — everything conditional lives here."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="development")  # development | staging | production
    debug: bool = Field(default=True)

    database_url: str = Field(
        default="postgresql+asyncpg://gridkeep:gridkeep@localhost:5432/gridkeep"
    )
    database_migration_url: str = Field(
        default="postgresql+psycopg://gridkeep:gridkeep@localhost:5432/gridkeep"
    )
    db_pool_size: int = Field(default=10)
    db_max_overflow: int = Field(default=5)

    redis_url: str = Field(default="redis://localhost:6379/0")

    session_cookie_name: str = Field(default="gridkeep_session")
    session_ttl_seconds: int = Field(default=60 * 60 * 12)  # 12h
    csrf_cookie_name: str = Field(default="gridkeep_csrf")

    # Master key for the LOCAL credential-vault envelope-encryption adapter.
    # Production deployments must use the secrets-manager adapter instead —
    # see modules/credential_vault/adapters/production.py.
    vault_local_master_key: str = Field(
        default="dev-only-insecure-master-key-do-not-use-in-production-00000000"
    )

    cors_allow_origins: list[str] = Field(default=["http://localhost:3000"])

    rate_limit_login_per_minute: int = Field(default=10)
    rate_limit_login_per_hour_per_account: int = Field(default=20)

    object_storage_endpoint: str = Field(default="http://localhost:9000")
    object_storage_bucket: str = Field(default="gridkeep-evidence")
    object_storage_access_key: str = Field(default="gridkeep")
    object_storage_secret_key: str = Field(default="gridkeep-dev-secret")

    # Real local-disk evidence file storage (see core/storage.py) — not the
    # S3/MinIO-compatible object store the settings above describe. That
    # remains dormant: a real MinIO instance needs a Docker daemon this
    # environment doesn't have. This is a genuinely real, but intentionally
    # scoped-down, local equivalent.
    evidence_storage_root: str = Field(default="var/evidence-storage")

    mail_capture_host: str = Field(default="localhost")
    mail_capture_port: int = Field(default=1025)
    mail_from_address: str = Field(default="no-reply@gridkeep.local")

    @field_validator("environment")
    @classmethod
    def _validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
