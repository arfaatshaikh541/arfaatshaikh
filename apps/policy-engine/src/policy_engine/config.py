"""Environment-driven configuration. No secret has a hardcoded default."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    environment: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            host=os.environ.get("POLICY_ENGINE_HOST", "0.0.0.0"),
            port=int(os.environ.get("POLICY_ENGINE_PORT", "8090")),
            environment=os.environ.get("CONTROL_API_ENV", "development"),
        )
