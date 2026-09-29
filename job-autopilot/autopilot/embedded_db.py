"""Optional embedded PostgreSQL for running without Docker or a separately installed database.

Uses the `pgserver` pip package (real PostgreSQL binaries shipped as a wheel). The cluster lives in
<JOBAP_DATA_DIR>/pgdata and persists between runs. Several processes (web, scheduler, worker, and
one-off CLI commands) share the same running server; pgserver stops it when the last user exits.
"""
from __future__ import annotations

import os
from pathlib import Path

_server = None  # keep a reference for the lifetime of this process


def ensure_embedded_database(cfg):
    global _server
    try:
        import pgserver
    except ImportError as e:
        raise RuntimeError(
            "JOBAP_EMBEDDED_DB=true but the 'pgserver' package is not installed. "
            "Run: pip install -e '.[embedded]'   (or set JOBAP_DATABASE_URL to your own PostgreSQL)") from e
    pgdata = Path(cfg.data_dir).resolve() / "pgdata"
    pgdata.mkdir(parents=True, exist_ok=True)
    _server = pgserver.get_server(str(pgdata), cleanup_mode="stop")
    uri = _server.get_uri()  # e.g. postgresql://postgres:@/postgres?host=/path/to/socket
    url = uri.replace("postgresql://", "postgresql+psycopg://", 1)
    os.environ["JOBAP_DATABASE_URL"] = url  # inherited by child processes
    return cfg.model_copy(update={"database_url": url})


def stop_embedded_database() -> None:
    """Stop the embedded server explicitly (called by `autopilot run` after all children exited)."""
    global _server
    if _server is None:
        return
    try:
        from pgserver._commands import pg_ctl

        pg_ctl(["-D", str(_server.pgdata), "-w", "-m", "fast", "stop"], user=_server.system_user)
    except Exception:
        pass  # already stopped
    _server = None
