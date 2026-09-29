"""Process-level configuration (environment variables only).

User-editable runtime settings (rules, schedule, AI provider, mode) live in the
database (see ``autopilot.settings_store``), not here.
"""
from __future__ import annotations

import os
import socket
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    # Settings come from environment variables, or from a .env file in the working directory
    # (written by `autopilot setup`). Real environment variables win over the file.
    model_config = SettingsConfigDict(env_prefix="JOBAP_", env_file=os.environ.get("JOBAP_ENV_FILE", ".env"),
                                      env_file_encoding="utf-8", extra="ignore")

    # Run a private PostgreSQL inside JOBAP_DATA_DIR (pip package `pgserver`) when no URL is given.
    embedded_db: bool = False
    database_url: str = Field(
        default="",
        description="SQLAlchemy URL, e.g. postgresql+psycopg://user:pass@host/db",
    )
    # Base64 (urlsafe or standard) encoded 32 byte key. Prefer master_key_file.
    master_key: str = ""
    master_key_file: str = ""
    # Comma separated retired keys, used only to decrypt during rotation.
    old_master_keys: str = ""
    data_dir: Path = Path("./data")
    browser_executable: str = ""
    headless: bool = True
    secure_cookies: bool = True
    session_hours: int = 12
    # Unique per process start (in containers the PID is always the same, so add randomness).
    worker_id: str = Field(default_factory=lambda: f"{socket.gethostname()}-{os.getpid()}-{os.urandom(2).hex()}")
    max_upload_mb: int = 10
    log_level: str = "INFO"
    # Seconds a claimed task is leased before another worker may reclaim it. Workers renew the
    # lease while they are alive (heartbeat), so this is the crash-detection delay.
    task_lease_seconds: int = 300
    # production | development | test. LIVE submissions are refused unless production, and in
    # production job/application URLs must resolve to public hosts (no localhost/private ranges).
    environment: str = "development"
    # Internal remote-browser session server inside each worker. Bound to the container network
    # only; never publish this port. The web process proxies authenticated users to it.
    session_server_port: int = 9310
    session_bind_host: str = "0.0.0.0"
    session_advertise_host: str = ""
    # Public https URL of the dashboard, used in notification links (e.g. https://autopilot.example.com).
    public_base_url: str = ""
    # File containing a bearer token for GET /metrics (Prometheus). Unset = /metrics needs a login session.
    metrics_token_file: str = ""
    # Worker self-watchdog: exit (container restarts) if the main loop makes no progress for this long.
    watchdog_stall_seconds: int = 1800

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    @property
    def evidence_dir(self) -> Path:
        return self.data_dir / "evidence"


@lru_cache
def get_config() -> Config:
    cfg = Config()
    if not cfg.database_url and cfg.embedded_db:
        from .embedded_db import ensure_embedded_database

        cfg = ensure_embedded_database(cfg)
    if not cfg.database_url:
        raise RuntimeError(
            "JOBAP_DATABASE_URL is NOT CONFIGURED. Set it to a PostgreSQL URL, e.g. "
            "postgresql+psycopg://autopilot:<password>@localhost/autopilot"
        )
    return cfg


def reset_config_cache() -> None:
    get_config.cache_clear()
