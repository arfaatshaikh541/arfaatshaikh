"""Command line: `autopilot <command>`."""
from __future__ import annotations

import argparse
import getpass
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="autopilot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gen-master-key", help="Print a new random master key (store it as a secret file)")
    sub.add_parser("init-db", help="Create tables and platform registry")
    ca = sub.add_parser("create-admin", help="Create the admin login")
    ca.add_argument("--email", required=True)
    w = sub.add_parser("web", help="Run the dashboard")
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--port", type=int, default=8000)
    sub.add_parser("scheduler", help="Run the scheduler (single leader)")
    wk = sub.add_parser("worker", help="Run a worker")
    wk.add_argument("--types", default="", help="comma separated task types (default: all)")
    sub.add_parser("rotate-master-key", help="Re-encrypt secrets under JOBAP_MASTER_KEY (old keys in JOBAP_OLD_MASTER_KEYS)")
    sub.add_parser("report", help="Generate today's report now and print it")
    sub.add_parser("health", help="Print live health")
    a = ap.parse_args(argv)

    if a.cmd == "gen-master-key":
        from .security.vault import generate_master_key

        print(generate_master_key())
        return 0

    from .config import get_config
    from .logging_setup import setup_logging

    setup_logging(get_config().log_level)
    from .db import init_db, session_scope

    if a.cmd == "init-db":
        init_db()
        print("database initialised")
        return 0
    init_db()
    if a.cmd == "create-admin":
        from sqlalchemy import select

        from .models import User
        from .security.passwords import hash_password

        pw = getpass.getpass("New admin password (min 12 chars): ")
        if pw != getpass.getpass("Repeat: "):
            print("passwords differ", file=sys.stderr)
            return 1
        with session_scope() as s:
            if s.scalar(select(User).where(User.email == a.email.lower())):
                print("user exists", file=sys.stderr)
                return 1
            s.add(User(email=a.email.lower(), password_hash=hash_password(pw)))
            from .audit import audit

            audit(s, "cli", "create_admin", a.email.lower())
        print("admin created")
        return 0
    if a.cmd == "web":
        import uvicorn

        uvicorn.run("autopilot.web.app:app", host=a.host, port=a.port, proxy_headers=True, forwarded_allow_ips="*",
                    log_config=None)
        return 0
    if a.cmd == "scheduler":
        from .workers.runtime import run_scheduler

        run_scheduler()
        return 0
    if a.cmd == "worker":
        from .workers.runtime import Worker

        Worker([t for t in a.types.split(",") if t] or None).run_forever()
        return 0
    if a.cmd == "rotate-master-key":
        from .security.credentials import rotate_master_key
        from .security.vault import get_vault

        with session_scope() as s:
            n = rotate_master_key(s, get_vault())
        print(f"re-encrypted {n} secrets. NOTE: CV files and evidence screenshots keep their original key; "
              "keep the old key in JOBAP_OLD_MASTER_KEYS to read them.")
        return 0
    if a.cmd == "report":
        from .reports import generate

        with session_scope() as s:
            print(generate(s, trigger="manual").text)
        return 0
    if a.cmd == "health":
        import json

        from .health import system_health

        with session_scope() as s:
            print(json.dumps(system_health(s), indent=2, default=str))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
