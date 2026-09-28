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
    model_config = SettingsConfigDict(env_prefix="JOBAP_", env_file=None, extra="ignore")

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
    worker_id: str = Field(default_factory=lambda: f"{socket.gethostname()}-{os.getpid()}")
    max_upload_mb: int = 10
    log_level: str = "INFO"
    # Seconds a claimed task is leased before another worker may reclaim it.
    task_lease_seconds: int = 900

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    @property
    def evidence_dir(self) -> Path:
        return self.data_dir / "evidence"


@lru_cache
def get_config() -> Config:
    cfg = Config()
    if not cfg.database_url:
        raise RuntimeError(
            "JOBAP_DATABASE_URL is NOT CONFIGURED. Set it to a PostgreSQL URL, e.g. "
            "postgresql+psycopg://autopilot:<password>@localhost/autopilot"
        )
    return cfg


def reset_config_cache() -> None:
    get_config.cache_clear()
