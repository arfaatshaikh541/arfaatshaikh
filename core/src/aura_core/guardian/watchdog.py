"""GuardianWatchdog: runs SecurityGuardian.evaluate() on a timer,
independent of whatever process is actually submitting actions -- the
out-of-process half of "independent oversight"
(docs/architecture/04-agent-architecture.md#security-guardian-independent-oversight).

FINAL_COMPLETION_AUDIT.md flagged the remaining gap plainly: Guardian's
evaluate() was only ever invoked via the Action Broker's own on_audit
hook, in the same process as everything it's supposed to be
independently overseeing. A hung or compromised core process could stop
calling that hook silently, and the Guardian would never fire again.

This closes that gap by making the Guardian runnable as a genuinely
separate OS process (`aura guardian watch`), which works with zero IPC
of its own because PolicyEngine's kill switch and AuditLog are both
real, persisted, shared SQLite state -- any process pointed at the same
database URL sees the same audit entries and can engage the same kill
switch. The Action Broker checks PolicyEngine.is_kill_switch_engaged()
fresh from the database on every submit() call, so a kill switch
engaged by this separate watchdog process genuinely blocks the main
process's next action, not just its own in-memory copy of anything.
"""
from __future__ import annotations

import threading
import time

from .guardian import SecurityGuardian


class GuardianWatchdog:
    def __init__(self, guardian: SecurityGuardian, poll_interval_seconds: float = 5.0) -> None:
        self._guardian = guardian
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.polls_run = 0

    def poll_once(self):
        events = self._guardian.evaluate()
        self.polls_run += 1
        return events

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self.poll_once()
            self._stop_event.wait(self.poll_interval_seconds)

    def start_in_background(self) -> threading.Thread:
        """For embedding the watchdog inside a larger process (or a fast,
        deterministic test) without giving up in-process control. Real
        out-of-process independence -- the actual point of this class --
        comes from running it as its own OS process via `aura guardian
        watch`, not from this method."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.poll_interval_seconds + 5)

    def run_forever(self) -> None:
        """Blocks the calling thread -- for a standalone watchdog process,
        not a background thread inside a larger app."""
        try:
            while True:
                self.poll_once()
                time.sleep(self.poll_interval_seconds)
        except KeyboardInterrupt:
            pass
