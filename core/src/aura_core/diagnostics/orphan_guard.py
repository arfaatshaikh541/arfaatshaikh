"""Orphan-process detection: a pidfile-based guard against a supervised
child process outliving its Supervisor -- e.g. AURA's own process is
killed (OOM, `kill -9`, power loss) without a chance to terminate a child
it had started, leaving that child running unsupervised. On the next
startup, a fresh Supervisor spawning a new child would end up with two
processes competing for the same resource (a port, a lock file). This
guard record who currently owns a given role's process, and on startup
reaps any process left behind by a previous, no-longer-running owner
before a new one is started.

Deliberately narrow: it only ever acts on a PID recorded in its own
pidfile, and only after confirming the live process's command line still
looks like the one AURA started (a bare PID can be reused by an unrelated
process by the time this check runs) -- it never scans the whole process
table.
"""
from __future__ import annotations

import json
import os
import signal
import time
from dataclasses import dataclass


@dataclass
class OrphanCheckResult:
    found_orphan: bool
    detail: str


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _cmdline(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            return handle.read().decode(errors="replace").replace("\x00", " ").strip()
    except OSError:
        return ""


class OrphanProcessGuard:
    def __init__(self, pidfile_path: str) -> None:
        self._pidfile_path = pidfile_path

    def record_current(self, pid: int, command_fragment: str) -> None:
        os.makedirs(os.path.dirname(self._pidfile_path), exist_ok=True)
        with open(self._pidfile_path, "w") as handle:
            json.dump({"pid": pid, "command_fragment": command_fragment}, handle)

    def _read(self) -> dict | None:
        if not os.path.exists(self._pidfile_path):
            return None
        try:
            with open(self._pidfile_path) as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None

    def check_and_reap(self, *, terminate_timeout_seconds: float = 5.0) -> OrphanCheckResult:
        """Call this before starting a new supervised process. If the
        pidfile names a PID that is still alive and whose command line
        still contains the expected fragment, it is a genuine orphan from
        a previous run -- terminate it (SIGTERM, then SIGKILL if it does
        not exit in time) so the new process does not collide with it."""
        record = self._read()
        if record is None:
            return OrphanCheckResult(False, "no pidfile -- nothing to check")

        pid = record.get("pid")
        fragment = record.get("command_fragment", "")

        if pid is None or not _is_alive(pid):
            return OrphanCheckResult(False, f"pidfile pid {pid} is not running -- stale pidfile, nothing to reap")

        actual_cmdline = _cmdline(pid)
        if fragment and fragment not in actual_cmdline:
            return OrphanCheckResult(
                False,
                f"pid {pid} is alive but its command line no longer matches "
                f"'{fragment}' -- the PID was reused by an unrelated process, not reaping it",
            )

        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + terminate_timeout_seconds
        while time.monotonic() < deadline:
            if not _is_alive(pid):
                return OrphanCheckResult(True, f"orphaned process {pid} ('{fragment}') terminated with SIGTERM")
            time.sleep(0.1)

        os.kill(pid, signal.SIGKILL)
        return OrphanCheckResult(True, f"orphaned process {pid} ('{fragment}') did not exit; killed with SIGKILL")
