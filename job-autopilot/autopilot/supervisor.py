"""`autopilot run`: web + scheduler + worker(s) as supervised child processes (no Docker needed).

Plays the role of Docker's restart policy: a child that exits unexpectedly is restarted with
exponential backoff. Ctrl+C / SIGTERM stops everything gracefully (workers get up to 2 minutes to
finish the current step - the same guarantee as the container stop_grace_period).
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

WINDOWS = os.name == "nt"


class Child:
    def __init__(self, name: str, args: list[str], grace_s: float):
        self.name, self.args, self.grace_s = name, args, grace_s
        self.proc: subprocess.Popen | None = None
        self.restarts = 0
        self.backoff = 1.0
        self.next_start = 0.0
        self.started_at = 0.0

    def start(self) -> None:
        kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS else {}
        self.proc = subprocess.Popen([sys.executable, "-m", "autopilot.cli", *self.args], **kw)
        self.started_at = time.monotonic()
        print(f"[supervisor] started {self.name} (pid {self.proc.pid})", flush=True)

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.CTRL_BREAK_EVENT if WINDOWS else signal.SIGTERM)

    def wait(self) -> None:
        if not self.proc:
            return
        try:
            self.proc.wait(self.grace_s)
        except subprocess.TimeoutExpired:
            print(f"[supervisor] {self.name} did not stop within {self.grace_s:.0f}s; killing", flush=True)
            self.proc.kill()
            self.proc.wait(10)


def run(host: str, port: int, workers: int) -> int:
    children = [Child("web", ["web", "--host", host, "--port", str(port)], 15),
                Child("scheduler", ["scheduler"], 30)]
    children += [Child(f"worker-{i + 1}" if workers > 1 else "worker", ["worker"], 120) for i in range(workers)]
    stopping = False

    def on_signal(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, on_signal)

    for c in children:
        c.start()
    print(f"[supervisor] dashboard: http://{host}:{port}   (Ctrl+C to stop)", flush=True)
    try:
        while not stopping:
            now = time.monotonic()
            for c in children:
                if c.proc is not None and c.proc.poll() is not None and not stopping:
                    code = c.proc.returncode
                    if now - c.started_at > 120:
                        c.backoff = 1.0  # it had been running fine; reset the backoff
                    c.restarts += 1
                    c.next_start = now + c.backoff
                    print(f"[supervisor] {c.name} exited with code {code}; restart #{c.restarts} in {c.backoff:.0f}s",
                          flush=True)
                    c.backoff = min(60.0, c.backoff * 2)
                    c.proc = None
                if c.proc is None and not stopping and now >= c.next_start:
                    c.start()
            time.sleep(1)
    finally:
        print("[supervisor] stopping (workers finish their current step first)...", flush=True)
        for c in children:
            c.stop()
        for c in reversed(children):
            c.wait()
        from .embedded_db import stop_embedded_database

        stop_embedded_database()
        print("[supervisor] all processes stopped", flush=True)
    return 0
