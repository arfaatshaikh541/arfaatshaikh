from __future__ import annotations

import os
import uuid

import pytest


@pytest.fixture(autouse=True)
def _test_environment(tmp_path, monkeypatch):
    """Force AURA_ENV=test (permits the deterministic test provider fallback)
    and give every test its own throwaway SQLite file so tests never share
    state or depend on prior test order."""
    db_path = tmp_path / f"aura_test_{uuid.uuid4().hex}.db"
    monkeypatch.setenv("AURA_ENV", "test")
    monkeypatch.setenv("AURA_DATABASE_URL", f"sqlite:///{db_path}")
    # Point Ollama at a port nothing listens on, so provider health checks
    # genuinely fail fast and deterministically exercise the fallback path,
    # rather than depending on whether this machine happens to run Ollama.
    monkeypatch.setenv("AURA_OLLAMA_HOST", "http://127.0.0.1:1")
    yield
