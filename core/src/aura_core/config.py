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
    allow_test_provider: bool


def load_settings() -> Settings:
    env = os.environ.get("AURA_ENV", "local")
    return Settings(
        env=env,
        database_url=os.environ.get("AURA_DATABASE_URL", "sqlite:///./aura_core.db"),
        ollama_host=os.environ.get("AURA_OLLAMA_HOST", "http://localhost:11434"),
        ollama_model=os.environ.get("AURA_OLLAMA_MODEL", "llama3.1"),
        allow_test_provider=env == "test",
    )
