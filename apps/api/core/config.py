from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The exact insecure default values this file ships for local development.
# A production boot is refused if any of these literal defaults is still in
# effect — see `Settings._validate_production_safety`. Named constants
# (not inlined into both the field default and the check) so the two can
# never silently drift apart.
_DEV_VAULT_MASTER_KEY = "dev-only-insecure-master-key-do-not-use-in-production-00000000"
_DEV_OBJECT_STORAGE_ACCESS_KEY = "gridkeep"
_DEV_OBJECT_STORAGE_SECRET_KEY = "gridkeep-dev-secret"
# The superuser credential — used only for DATABASE_MIGRATION_URL since
# Milestone 31; never for DATABASE_URL, which the app itself connects
# with (see _DEV_APP_DB_PASSWORD below).
_DEV_DB_CREDENTIAL_MARKER = "gridkeep:gridkeep@"
# Milestone 31 (finding C-01): the least-privilege role the application
# actually connects as, and its shipped development password. Matches the
# literal default in migration 34016597f04f — kept as an independent
# constant (not imported across the migrations/app boundary) since a
# migration file's contents must never change after it ships, while this
# one is free to gain new checks.
_DEV_APP_DB_ROLE = "gridkeep_app"
_DEV_APP_DB_PASSWORD = "gridkeep-app-dev-only-insecure-do-not-use-in-production"
_DEV_APP_DB_CREDENTIAL_MARKER = f"{_DEV_APP_DB_ROLE}:{_DEV_APP_DB_PASSWORD}@"


class Settings(BaseSettings):
    """Environment-derived configuration. No environment-specific code
    branches elsewhere in the app — everything conditional lives here.

    Milestone 29: `_validate_production_safety` makes `environment=production`
    a fail-closed boot-time gate — the process refuses to construct its
    `Settings` (and therefore refuses to start at all, since `settings =
    get_settings()` below runs at import time) rather than silently serving
    traffic with a known-insecure development default. This is deliberately
    boot-time, not request-time: a misconfigured production deployment
    should crash-loop loudly in its orchestrator's logs before it ever
    accepts a connection."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="development")  # development | staging | production | test

    # Milestone 31 (finding C-01): the application's own runtime connection
    # — every tenant-facing request goes over this one, so it must be the
    # least-privilege `gridkeep_app` role (NOSUPERUSER NOBYPASSRLS), never
    # the migration superuser below. See migration 34016597f04f for how
    # that role is provisioned, and docs/security-findings-register.md for
    # why this mattered: `gridkeep`, the previous connection for both URLs,
    # is a Postgres superuser and unconditionally bypasses every RLS policy
    # in this codebase regardless of FORCE ROW LEVEL SECURITY.
    database_url: str = Field(
        default=f"postgresql+asyncpg://{_DEV_APP_DB_CREDENTIAL_MARKER}localhost:5432/gridkeep"
    )
    # The migration/DDL connection ONLY — migrations/env.py hard-codes this
    # as the sole URL Alembic ever uses. Deliberately still the superuser:
    # creating roles, tables, and RLS policies needs privileges the
    # application's own runtime role must never hold.
    database_migration_url: str = Field(
        default="postgresql+psycopg://gridkeep:gridkeep@localhost:5432/gridkeep"
    )
    db_pool_size: int = Field(default=10)
    db_max_overflow: int = Field(default=5)

    redis_url: str = Field(default="redis://localhost:6379/0")

    session_cookie_name: str = Field(default="gridkeep_session")
    session_ttl_seconds: int = Field(default=60 * 60 * 12)  # 12h
    csrf_cookie_name: str = Field(default="gridkeep_csrf")

    # Milestone 29: cookies are `Secure` by default now, in every
    # environment (see modules/identity/routes.py:_cookie_secure_kwargs) —
    # this is the explicit, narrowly-named opt-out a developer running the
    # API over plain http://localhost needs. Replaces the previous
    # `secure=settings.is_production` behaviour, which meant a deployment
    # that simply forgot to set ENVIRONMENT=production silently shipped
    # session cookies without the Secure attribute.
    allow_insecure_cookies_for_local_dev: bool = Field(default=False)

    # Master key for the LOCAL credential-vault envelope-encryption adapter
    # — dormant whenever `vault_adapter="vault"` (see below), but still
    # validated in production regardless of which adapter is selected,
    # since a later switch back to "local" shouldn't silently un-mask a
    # stale shipped key nobody ever got around to rotating.
    vault_local_master_key: str = Field(default=_DEV_VAULT_MASTER_KEY)

    # Milestone 32 (finding C-02): which VaultAdapter implementation
    # `modules/credential_vault/service.py:get_vault_adapter` constructs —
    # an environment-driven wiring decision, never an application-logic
    # branch (architecture §11). "local" is the Milestone 1 envelope-
    # encryption adapter (dev/test only, no real key-management backing
    # it); "vault" is the real production adapter, backed by HashiCorp
    # Vault's Transit secrets engine (encryption-as-a-service — the
    # application never holds or derives key material itself). HashiCorp
    # Vault over a specific cloud KMS (AWS/GCP/Azure) because it's the one
    # option in architecture §11's list not tied to a single cloud
    # provider, matching this codebase's actual deployment target
    # (self-hosted docker-compose, no cloud account to bind a KMS to).
    vault_adapter: str = Field(default="local")
    vault_hashicorp_addr: str = Field(default="")
    vault_hashicorp_token: str = Field(default="")
    vault_hashicorp_transit_key_name: str = Field(default="gridkeep-credential-vault")
    vault_hashicorp_mount_point: str = Field(default="transit")

    cors_allow_origins: list[str] = Field(default=["http://localhost:3000"])

    # The frontend's own origin, used to build clickable links in emails
    # (verify-email, reset-password, accept-invitation all read their
    # token from a `?token=` query param). Deliberately separate from
    # `cors_allow_origins` — that's a list for CORS validation, this is a
    # single canonical URL for link-building, and the two could
    # legitimately differ (e.g. multiple allowed CORS origins in a
    # multi-domain deployment, but one canonical link target).
    app_base_url: str = Field(default="http://localhost:3000")

    rate_limit_login_per_minute: int = Field(default=10)
    rate_limit_login_per_hour_per_account: int = Field(default=20)

    object_storage_endpoint: str = Field(default="http://localhost:9000")
    object_storage_bucket: str = Field(default="gridkeep-evidence")
    object_storage_access_key: str = Field(default=_DEV_OBJECT_STORAGE_ACCESS_KEY)
    object_storage_secret_key: str = Field(default=_DEV_OBJECT_STORAGE_SECRET_KEY)

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

    @field_validator("vault_adapter")
    @classmethod
    def _validate_vault_adapter(cls, v: str) -> str:
        allowed = {"local", "vault"}
        if v not in allowed:
            raise ValueError(f"vault_adapter must be one of {allowed}")
        return v

    @model_validator(mode="after")
    def _validate_production_safety(self) -> Settings:
        """Refuses to construct a `production` Settings object that still
        carries any value this file ships as a *development* default. Each
        check below names the exact finding it closes (see
        docs/security-findings-register.md) so a boot failure traces
        straight back to the reason, not just "something is wrong"."""
        if self.environment != "production":
            return self

        problems: list[str] = []

        if self.vault_local_master_key == _DEV_VAULT_MASTER_KEY:
            problems.append(
                "VAULT_LOCAL_MASTER_KEY is still the shipped development default "
                "— set a real, securely-generated value (finding C-02)."
            )
        if self.object_storage_access_key == _DEV_OBJECT_STORAGE_ACCESS_KEY:
            problems.append("OBJECT_STORAGE_ACCESS_KEY is still the shipped development default.")
        if self.object_storage_secret_key == _DEV_OBJECT_STORAGE_SECRET_KEY:
            problems.append("OBJECT_STORAGE_SECRET_KEY is still the shipped development default.")
        if _DEV_DB_CREDENTIAL_MARKER in self.database_url:
            problems.append(
                "DATABASE_URL still connects as the gridkeep superuser — the application's runtime "
                "connection must be the least-privilege gridkeep_app role, never the migration "
                "superuser (finding C-01)."
            )
        if _DEV_APP_DB_CREDENTIAL_MARKER in self.database_url:
            problems.append(
                "DATABASE_URL still uses the development gridkeep_app password — set a real, "
                "securely-generated GRIDKEEP_APP_DB_PASSWORD before running migrations, then use "
                "the same value here (finding C-01)."
            )
        if _DEV_DB_CREDENTIAL_MARKER in self.database_migration_url:
            problems.append(
                "DATABASE_MIGRATION_URL still uses the development gridkeep:gridkeep credential."
            )
        if any("localhost" in origin or "127.0.0.1" in origin for origin in self.cors_allow_origins):
            problems.append(
                "CORS_ALLOW_ORIGINS still contains a localhost/127.0.0.1 origin "
                "— set the real production origin(s) (finding H-02)."
            )
        if "localhost" in self.redis_url or "127.0.0.1" in self.redis_url:
            problems.append("REDIS_URL still points at localhost — set the real production Redis host.")
        if self.allow_insecure_cookies_for_local_dev:
            problems.append(
                "ALLOW_INSECURE_COOKIES_FOR_LOCAL_DEV is true — this flag exists only for local "
                "development over plain HTTP and must never be set in production (finding H-02)."
            )
        if self.vault_adapter == "local":
            problems.append(
                "VAULT_ADAPTER is still \"local\" — the local envelope-encryption adapter has no "
                "real key-management backing it and must never be used in production. Set "
                "VAULT_ADAPTER=vault and configure VAULT_HASHICORP_ADDR/VAULT_HASHICORP_TOKEN for a "
                "real HashiCorp Vault Transit-engine deployment (finding C-02)."
            )
        elif self.vault_adapter == "vault":
            if not self.vault_hashicorp_addr:
                problems.append("VAULT_HASHICORP_ADDR must be set when VAULT_ADAPTER=vault.")
            if not self.vault_hashicorp_token:
                problems.append("VAULT_HASHICORP_TOKEN must be set when VAULT_ADAPTER=vault.")

        if problems:
            raise ValueError(
                "Refusing to start with environment=production while the following "
                "development-only defaults are still in effect:\n- " + "\n- ".join(problems)
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
