from __future__ import annotations

from click.testing import CliRunner

from aura_core.cli import main


def test_voice_run_supervises_the_real_dotnet_host_project(monkeypatch):
    """`aura voice run` must launch the actual AuraVoice.Windows.Host
    project under Supervisor (real self-recovery for the voice process,
    not just the in-process fail-closed behavior inside it) -- verified
    here by faking Supervisor itself (so the test doesn't need the .NET
    SDK or a live aura_core server) and checking the command it was
    constructed with, rather than mocking away the wiring under test."""
    calls = []

    class FakeSupervisor:
        def __init__(self, command, *, max_restarts, backoff_seconds, on_process_started=None):
            calls.append({"command": command, "max_restarts": max_restarts, "backoff_seconds": backoff_seconds})
            self.events = []

        def start(self):
            pass

    monkeypatch.setattr("aura_core.diagnostics.Supervisor", FakeSupervisor)

    runner = CliRunner()
    result = runner.invoke(main, ["voice", "run"])

    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    command = calls[0]["command"]
    assert command[0] == "dotnet"
    assert command[1] == "run"
    assert "AuraVoice.Windows.Host" in command[-1]
    assert calls[0]["max_restarts"] == 5


def test_voice_run_passes_through_custom_restart_options(monkeypatch):
    calls = []

    class FakeSupervisor:
        def __init__(self, command, *, max_restarts, backoff_seconds, on_process_started=None):
            calls.append((max_restarts, backoff_seconds))
            self.events = []

        def start(self):
            pass

    monkeypatch.setattr("aura_core.diagnostics.Supervisor", FakeSupervisor)

    runner = CliRunner()
    result = runner.invoke(main, ["voice", "run", "--max-restarts", "9", "--backoff-seconds", "0.5"])

    assert result.exit_code == 0, result.output
    assert calls == [(9, 0.5)]
