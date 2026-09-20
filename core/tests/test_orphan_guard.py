from __future__ import annotations

import subprocess
import sys
import time

from aura_core.diagnostics import OrphanProcessGuard


def _wait_until_dead(child: subprocess.Popen, timeout: float = 5.0) -> bool:
    """Uses child.poll() (waitpid under the hood), not os.kill(pid, 0) --
    a terminated-but-unreaped child is a zombie and still answers
    os.kill(pid, 0) as if it were alive until its parent reaps it."""
    try:
        child.wait(timeout=timeout)
        return True
    except subprocess.TimeoutExpired:
        return False


def test_no_pidfile_means_nothing_to_reap(tmp_path):
    guard = OrphanProcessGuard(str(tmp_path / "aura.pid"))

    result = guard.check_and_reap()

    assert result.found_orphan is False
    assert "no pidfile" in result.detail


def test_a_stale_pidfile_pointing_at_a_dead_process_is_left_alone(tmp_path):
    guard = OrphanProcessGuard(str(tmp_path / "aura.pid"))
    # A PID this high is essentially guaranteed not to correspond to any
    # live process on a real machine.
    guard.record_current(pid=999999, command_fragment="aura_core.voice_bridge")

    result = guard.check_and_reap()

    assert result.found_orphan is False
    assert "not running" in result.detail


def test_a_real_orphaned_process_matching_the_expected_command_is_terminated(tmp_path):
    """Proves the guard actually kills a genuine leftover process -- a
    real subprocess left running from a 'previous run' that the current
    Supervisor no longer owns -- not just a unit test of string matching."""
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
    )
    try:
        guard = OrphanProcessGuard(str(tmp_path / "aura.pid"))
        guard.record_current(pid=child.pid, command_fragment="import time; time.sleep(60)")

        result = guard.check_and_reap(terminate_timeout_seconds=3.0)

        assert result.found_orphan is True
        assert "terminated" in result.detail or "killed" in result.detail
        assert _wait_until_dead(child)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


def test_a_live_process_whose_command_line_no_longer_matches_is_not_touched(tmp_path):
    """A PID can be reused by an unrelated process by the time this check
    runs -- the guard must never kill a process just because a number
    matches, only when the command line still looks like the one it
    started."""
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        guard = OrphanProcessGuard(str(tmp_path / "aura.pid"))
        guard.record_current(pid=child.pid, command_fragment="some_totally_unrelated_command_marker")

        result = guard.check_and_reap()

        assert result.found_orphan is False
        assert "not reaping" in result.detail
        assert child.poll() is None  # still alive
    finally:
        child.kill()
        child.wait()
