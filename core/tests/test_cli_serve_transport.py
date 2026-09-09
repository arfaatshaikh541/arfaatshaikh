"""Section 1/4's real fix: `aura serve` must never crash on Windows the
way it did before this pass. The root cause was verified directly
against the installed interpreter's own asyncio source (see
resolve_serve_transport's docstring in cli.py): CPython's
asyncio.base_events.BaseEventLoop.create_unix_server raises
NotImplementedError by default, and only Unix's event loop
(asyncio/unix_events.py) overrides it with a real implementation --
Windows' event loops do not. uvicorn.run(app, uds=path) therefore
crashes immediately on native Windows Python, which is exactly the kind
of install-time failure a platform-unaware default transport would
produce. resolve_serve_transport is the pure decision function that
routes around this; these tests exercise it directly with an injected
platform name, since this sandbox cannot literally run on Windows.
"""
from __future__ import annotations

from aura_core.cli import resolve_serve_transport


def test_windows_defaults_to_loopback_tcp_not_a_unix_socket():
    kind, target = resolve_serve_transport(None, None, "/some/sandbox", system="Windows")

    assert kind == "tcp"
    assert target == "127.0.0.1"


def test_linux_defaults_to_a_real_unix_domain_socket():
    kind, target = resolve_serve_transport(None, None, "/some/sandbox", system="Linux")

    assert kind == "uds"
    assert target.endswith("core.sock")


def test_macos_also_defaults_to_a_real_unix_domain_socket():
    kind, target = resolve_serve_transport(None, None, "/some/sandbox", system="Darwin")

    assert kind == "uds"


def test_an_explicit_host_always_wins_regardless_of_platform():
    kind, target = resolve_serve_transport(None, "0.0.0.0", "/some/sandbox", system="Linux")

    assert (kind, target) == ("tcp", "0.0.0.0")


def test_an_explicit_socket_path_always_wins_even_on_windows():
    """An owner or script that explicitly asked for a Unix socket gets
    exactly that -- this function never silently substitutes a different
    transport for an explicit request; a real attempt (and a real,
    honest crash if the platform can't do it) is more useful than a
    silent switch the caller didn't ask for."""
    kind, target = resolve_serve_transport("/custom/path.sock", None, "/some/sandbox", system="Windows")

    assert (kind, target) == ("uds", "/custom/path.sock")


def test_host_takes_priority_over_socket_path_if_both_are_somehow_set():
    kind, target = resolve_serve_transport("/custom/path.sock", "127.0.0.1", "/some/sandbox", system="Linux")

    assert (kind, target) == ("tcp", "127.0.0.1")


def test_windows_default_uses_the_real_platform_module_when_system_not_injected(monkeypatch):
    """Proves the `system` parameter is genuinely optional and falls
    back to the real platform.system() -- not merely decorative."""
    import aura_core.cli as cli_module

    monkeypatch.setattr(cli_module.platform, "system", lambda: "Windows")

    kind, target = resolve_serve_transport(None, None, "/some/sandbox")

    assert (kind, target) == ("tcp", "127.0.0.1")
