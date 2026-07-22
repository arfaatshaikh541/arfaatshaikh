"""Entrypoint: python -m policy_engine"""

from __future__ import annotations

import uvicorn

from policy_engine.config import Settings


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run("policy_engine.app:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
