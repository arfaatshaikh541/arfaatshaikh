"""Runtime configuration, read from environment variables.

AURA_ENV distinguishes "test" (this build environment, CI) from "local"
(your machine, where a real Ollama instance is expected). This distinction
matters because the test-only echo model provider is only permitted to run
in AURA_ENV=test — it must never silently stand in for a real model outside
of tests, or a chat response could be mistaken for genuine model output.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    env: str
    database_url: str
    ollama_host: str
    ollama_model: str
    ollama_fast_model: str | None
    ollama_embedding_model: str
    allow_test_provider: bool
    filesystem_sandbox_dir: str
    http_allowed_hosts: list[str]
    telephony_from_number: str
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_use_starttls: bool
    smtp_from_address: str
    browser_executable_path: str | None
    browser_profile_dir: str | None
    github_token: str | None
    imap_host: str | None
    imap_port: int
    imap_username: str | None
    imap_password: str | None
    imap_use_ssl: bool


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def load_settings() -> Settings:
    env = os.environ.get("AURA_ENV", "local")
    return Settings(
        env=env,
        database_url=os.environ.get("AURA_DATABASE_URL", "sqlite:///./aura_core.db"),
        ollama_host=os.environ.get("AURA_OLLAMA_HOST", "http://localhost:11434"),
        ollama_model=os.environ.get("AURA_OLLAMA_MODEL", "llama3.1"),
        ollama_fast_model=os.environ.get("AURA_OLLAMA_FAST_MODEL"),
        ollama_embedding_model=os.environ.get("AURA_OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        allow_test_provider=env == "test",
        filesystem_sandbox_dir=os.environ.get("AURA_FS_SANDBOX_DIR", "./aura_sandbox"),
        http_allowed_hosts=_split_csv(os.environ.get("AURA_HTTP_ALLOWED_HOSTS")),
        telephony_from_number=os.environ.get("AURA_TELEPHONY_FROM_NUMBER", "+10000000000"),
        smtp_host=os.environ.get("AURA_SMTP_HOST"),
        smtp_port=int(os.environ.get("AURA_SMTP_PORT", "587")),
        smtp_username=os.environ.get("AURA_SMTP_USERNAME"),
        smtp_password=os.environ.get("AURA_SMTP_PASSWORD"),
        smtp_use_starttls=os.environ.get("AURA_SMTP_STARTTLS", "true").lower() == "true",
        smtp_from_address=os.environ.get("AURA_SMTP_FROM_ADDRESS", "aura@localhost"),
        browser_executable_path=os.environ.get("AURA_PLAYWRIGHT_EXECUTABLE"),
        browser_profile_dir=os.environ.get("AURA_BROWSER_PROFILE_DIR"),
        github_token=os.environ.get("AURA_GITHUB_TOKEN"),
        imap_host=os.environ.get("AURA_IMAP_HOST"),
        imap_port=int(os.environ.get("AURA_IMAP_PORT", "993")),
        imap_username=os.environ.get("AURA_IMAP_USERNAME"),
        imap_password=os.environ.get("AURA_IMAP_PASSWORD"),
        imap_use_ssl=os.environ.get("AURA_IMAP_USE_SSL", "true").lower() == "true",
    )
