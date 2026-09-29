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
    st = sub.add_parser("setup", help="One-time setup without Docker: config file, master key, browser, database")
    st.add_argument("--data-dir", default="autopilot-data")
    st.add_argument("--database-url", default="", help="use your own PostgreSQL instead of the embedded one")
    st.add_argument("--skip-browser", action="store_true", help="do not download Chromium")
    st.add_argument("--email", default="", help="also create the admin login for this email")
    rn = sub.add_parser("run", help="Run web + scheduler + worker together (restarts crashed processes)")
    rn.add_argument("--host", default="127.0.0.1")
    rn.add_argument("--port", type=int, default=8000)
    rn.add_argument("--workers", type=int, default=1)
    a = ap.parse_args(argv)

    if a.cmd == "gen-master-key":
        from .security.vault import generate_master_key

        print(generate_master_key())
        return 0
    if a.cmd == "setup":
        return _setup(a)
    if a.cmd == "run":
        from .config import get_config
        from .db import init_db
        from .logging_setup import setup_logging

        setup_logging(get_config().log_level)  # starts the embedded database first if configured
        init_db()
        from .supervisor import run

        return run(a.host, a.port, a.workers)

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
        return _create_admin(a.email)
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


def _create_admin(email: str) -> int:
    from sqlalchemy import select

    from .audit import audit
    from .db import session_scope
    from .models import User
    from .security.passwords import hash_password

    while True:
        pw = getpass.getpass("New admin password (min 12 chars): ")
        if len(pw) < 12:
            print("  too short - use at least 12 characters", file=sys.stderr)
            continue
        if pw != getpass.getpass("Repeat: "):
            print("  passwords differ - try again", file=sys.stderr)
            continue
        break
    with session_scope() as s:
        if s.scalar(select(User).where(User.email == email.lower())):
            print("user exists", file=sys.stderr)
            return 1
        s.add(User(email=email.lower(), password_hash=hash_password(pw)))
        audit(s, "cli", "create_admin", email.lower())
    print(f"admin created: {email.lower()}")
    return 0


def _setup(a) -> int:
    import os
    import subprocess
    from pathlib import Path

    from .security.vault import generate_master_key

    if sys.version_info < (3, 11):
        print("Python 3.11 or newer is required", file=sys.stderr)
        return 1
    data = Path(a.data_dir).resolve()
    data.mkdir(parents=True, exist_ok=True)
    key = data / "master.key"
    if key.exists():
        print(f"- keeping existing master key {key}")
    else:
        key.write_text(generate_master_key())
        os.chmod(key, 0o600)
        print(f"- created master key {key}   <-- BACK THIS FILE UP (without it your secrets cannot be decrypted)")
    env = Path(".env")
    if env.exists():
        print(f"- keeping existing {env.resolve()} (delete it to regenerate)")
    else:
        if not a.database_url:
            try:
                import pgserver  # noqa: F401
            except ImportError:
                msg = ("The built-in database needs Python 3.11 or 3.12 (you have %d.%d) and: pip install -e '.[embedded]'\n"
                       "Or install PostgreSQL yourself and pass:  --database-url postgresql+psycopg://user:pass@localhost/autopilot"
                       % sys.version_info[:2])
                print(msg, file=sys.stderr)
                return 1
        lines = [
            "# Job Autopilot configuration (written by `autopilot setup`). Keep this file private.",
            f"JOBAP_DATA_DIR={data}",
            f"JOBAP_MASTER_KEY_FILE={key}",
            (f"JOBAP_DATABASE_URL={a.database_url}" if a.database_url else "JOBAP_EMBEDDED_DB=true"),
            "# production = real applications to real (public https) sites; they only happen in LIVE mode.",
            "JOBAP_ENVIRONMENT=production",
            "# Local use over plain http://127.0.0.1 - set to true when you serve the dashboard over https.",
            "JOBAP_SECURE_COOKIES=false",
            "JOBAP_PUBLIC_BASE_URL=http://127.0.0.1:8000",
            "JOBAP_SESSION_BIND_HOST=127.0.0.1",
            "JOBAP_SESSION_ADVERTISE_HOST=127.0.0.1",
        ]
        env.write_text("\n".join(lines) + "\n")
        try:
            os.chmod(env, 0o600)
        except OSError:
            pass
        print(f"- wrote {env.resolve()}")
    if not a.skip_browser:
        print("- downloading Chromium for Playwright (one time, ~150 MB)...")
        r = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
        if r.returncode != 0:
            print("  Chromium download failed (check your internet connection / proxy). On Linux you may also need\n"
                  "  the system libraries:  sudo python -m playwright install-deps chromium\n"
                  "  You can retry later with:  python -m playwright install chromium", file=sys.stderr)
    from .config import get_config, reset_config_cache

    reset_config_cache()
    from .db import init_db
    from .logging_setup import setup_logging

    setup_logging("WARNING")
    get_config()  # starts the embedded database when configured
    init_db()
    print("- database ready")
    if a.email:
        _create_admin(a.email)
    print("\nSetup complete. Start everything with:\n    autopilot run\nthen open http://127.0.0.1:8000")
    if not a.email:
        print("Create your login first (in another terminal or before `run`):\n"
              "    autopilot create-admin --email you@example.com")
    return 0


if __name__ == "__main__":
    sys.exit(main())
