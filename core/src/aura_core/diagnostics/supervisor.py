"""Supervisor: watchdog/restart-with-backoff for a child process, per
docs/architecture/00-overview.md's assumption that "computers crash" and
docs/testing/README.md's self-recovery requirement. Generic over any
command — used for the API server today, and equally applicable to a
future voice-pipeline process on Windows.
"""
from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SupervisorEvent:
    at: datetime
    kind: str  # "started" | "exited" | "restarting" | "gave_up"
    detail: str


class Supervisor:
    def __init__(
        self, command: list[str], *, max_restarts: int = 5,
        backoff_seconds: float = 1.0, max_backoff_seconds: float = 30.0,
    ) -> None:
        self._command = command
        self._max_restarts = max_restarts
        self._backoff_seconds = backoff_seconds
        self._max_backoff_seconds = max_backoff_seconds
        self.events: list[SupervisorEvent] = []
        self._process: subprocess.Popen | None = None
        self._stop_requested = False
        self._thread: threading.Thread | None = None

    def _log(self, kind: str, detail: str) -> None:
        self.events.append(SupervisorEvent(at=datetime.now(timezone.utc), kind=kind, detail=detail))

    def start(self) -> None:
        """Blocks the calling thread, running the supervise loop. Use
        start_in_background() to run it on a daemon thread instead."""
        self._stop_requested = False
        restarts = 0
        while not self._stop_requested:
            self._process = subprocess.Popen(self._command)
            self._log("started", f"pid={self._process.pid}")
            exit_code = self._process.wait()

            if self._stop_requested:
                self._log("exited", f"stopped by request (exit_code={exit_code})")
                return

            self._log("exited", f"exit_code={exit_code}")

            if exit_code == 0:
                return  # clean exit -- not a crash, nothing to restart

            if restarts >= self._max_restarts:
                self._log("gave_up", f"exceeded max_restarts={self._max_restarts}")
                return

            delay = min(self._backoff_seconds * (2 ** restarts), self._max_backoff_seconds)
            restarts += 1
            self._log("restarting", f"attempt {restarts}/{self._max_restarts} after {delay:.1f}s")
            time.sleep(delay)

    def start_in_background(self) -> threading.Thread:
        self._thread = threading.Thread(target=self.start, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        self._stop_requested = True
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
