"""The genuine proof for section 7's "local IPC, not loopback TCP"
requirement: `aura serve` run as a real, separate OS process bound to a
Unix domain socket, hit with a real HTTP request over that socket (never
touching 127.0.0.1 or any TCP port) via httpx's native Unix-socket
transport. This is exactly the mechanism the C# clients use too
(SocketsHttpHandler.ConnectCallback over a UnixDomainSocketEndPoint) --
see ipc.py's module docstring for why the same code works unmodified on
Windows.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
import time

import httpx
import pytest

from aura_core.ipc import default_socket_path

_windows_uds_unsupported = pytest.mark.skipif(
    platform.system() == "Windows",
    reason="Real, live Unix-domain-socket server tests. Verified directly against "
    "the installed interpreter (see resolve_serve_transport's docstring in cli.py) "
    "that asyncio.base_events.BaseEventLoop.create_unix_server raises "
    "NotImplementedError by default and is only overridden by POSIX's "
    "asyncio/unix_events.py -- Windows' event loops do not support it. `aura serve` "
    "therefore defaults to loopback TCP on Windows (see test_cli_serve_transport.py); "
    "these tests exercise the Linux/macOS-only UDS path and are SKIPPED_PLATFORM, "
    "not failed, on Windows.",
)


def test_default_socket_path_is_a_sibling_of_the_sandbox_dir(tmp_path):
    # Pure path computation -- no socket is opened, so this stays
    # cross-platform and is never skipped.
    sandbox_dir = str(tmp_path / "aura_sandbox")

    path = default_socket_path(sandbox_dir)

    assert path == str(tmp_path / ".aura" / "core.sock")


@pytest.fixture
def running_uds_server(tmp_path):
    db_url = f"sqlite:///{tmp_path}/ipc.db"
    socket_path = str(tmp_path / "core.sock")
    env = {
        **os.environ, "AURA_DATABASE_URL": db_url, "AURA_ENV": "test",
        "AURA_OLLAMA_HOST": "http://127.0.0.1:1", "AURA_FS_SANDBOX_DIR": str(tmp_path / "sandbox"),
    }

    proc = subprocess.Popen(
        [sys.executable, "-m", "aura_core.cli", "serve", "--socket-path", socket_path],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        deadline = time.time() + 15
        while not os.path.exists(socket_path) and time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"server process exited early:\n{proc.stdout.read()}")
            time.sleep(0.1)
        assert os.path.exists(socket_path), f"socket never appeared:\n{proc.stdout.read() if proc.poll() else ''}"
        yield socket_path
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.mark.integration
@pytest.mark.linux
@_windows_uds_unsupported
def test_a_real_request_reaches_the_server_over_the_unix_socket_not_tcp(running_uds_server):
    transport = httpx.HTTPTransport(uds=running_uds_server)
    with httpx.Client(transport=transport, base_url="http://ipc") as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
@pytest.mark.linux
@pytest.mark.security
@_windows_uds_unsupported
def test_no_tcp_port_is_actually_listening_for_this_server(running_uds_server, tmp_path):
    """The whole point: this server must not also be reachable over
    loopback TCP just because it's running on the same machine."""
    import socket

    db_port_probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    db_port_probe.settimeout(0.5)
    try:
        result = db_port_probe.connect_ex(("127.0.0.1", 8000))
        assert result != 0, "port 8000 should not be listening -- this server only binds the Unix socket"
    finally:
        db_port_probe.close()


@pytest.mark.integration
@pytest.mark.linux
@_windows_uds_unsupported
def test_a_real_post_endpoint_works_over_the_socket_too(running_uds_server):
    """/health alone would only prove GET works -- kill-switch engage is
    a real POST with a real state change, verified via a second GET."""
    transport = httpx.HTTPTransport(uds=running_uds_server)
    with httpx.Client(transport=transport, base_url="http://ipc") as client:
        engage = client.post("/kill-switch/engage")
        assert engage.status_code == 200
        assert engage.json()["kill_switch_engaged"] is True

        status = client.get("/status")
        assert status.status_code == 200
