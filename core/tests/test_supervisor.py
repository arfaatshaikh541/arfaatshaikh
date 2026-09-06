from __future__ import annotations

import sys
import textwrap

from aura_core.diagnostics import Supervisor


def _make_flaky_script(tmp_path, fail_times: int) -> str:
    """A real subprocess (not a mock) that fails `fail_times` times,
    tracking its attempt count in a file on disk, then exits 0."""
    counter_file = tmp_path / "attempts.txt"
    script_path = tmp_path / "flaky.py"
    script_path.write_text(textwrap.dedent(f"""
        import sys
        path = {str(counter_file)!r}
        try:
            with open(path) as f:
                attempts = int(f.read().strip())
        except FileNotFoundError:
            attempts = 0
        attempts += 1
        with open(path, "w") as f:
            f.write(str(attempts))
        sys.exit(1 if attempts <= {fail_times} else 0)
    """))
    return str(script_path)


def test_supervisor_restarts_a_crashing_process_and_eventually_succeeds(tmp_path):
    script = _make_flaky_script(tmp_path, fail_times=2)
    supervisor = Supervisor([sys.executable, script], max_restarts=5, backoff_seconds=0.01)

    supervisor.start()  # blocks until clean exit or give-up

    kinds = [e.kind for e in supervisor.events]
    assert kinds.count("started") == 3  # 1 initial + 2 restarts
    assert kinds[-2:] == ["exited", "exited"] or "gave_up" not in kinds
    assert supervisor.events[-1].kind == "exited"
    assert "exit_code=0" in supervisor.events[-1].detail


def test_supervisor_gives_up_after_max_restarts(tmp_path):
    script = _make_flaky_script(tmp_path, fail_times=100)  # never succeeds
    supervisor = Supervisor([sys.executable, script], max_restarts=2, backoff_seconds=0.01)

    supervisor.start()

    kinds = [e.kind for e in supervisor.events]
    assert kinds.count("started") == 3  # initial + 2 restarts, then gives up
    assert kinds[-1] == "gave_up"


def test_supervisor_does_not_restart_a_clean_exit(tmp_path):
    script_path = tmp_path / "clean.py"
    script_path.write_text("import sys; sys.exit(0)")
    supervisor = Supervisor([sys.executable, str(script_path)], max_restarts=5, backoff_seconds=0.01)

    supervisor.start()

    kinds = [e.kind for e in supervisor.events]
    assert kinds.count("started") == 1  # no restart for a clean (exit 0) run
    assert "restarting" not in kinds


def test_supervisor_stop_prevents_further_restarts(tmp_path):
    script = _make_flaky_script(tmp_path, fail_times=100)
    supervisor = Supervisor([sys.executable, script], max_restarts=100, backoff_seconds=5.0)

    thread = supervisor.start_in_background()
    import time
    time.sleep(0.3)  # let the first crash happen
    supervisor.stop()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert any(e.kind == "started" for e in supervisor.events)
