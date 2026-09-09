"""Native local IPC transport: a Unix domain socket, not loopback TCP.

Section 7 asks for the shell/voice apps to talk to core over "LOCAL, NOT
LOCALHOST" transport -- named pipes on Windows, or an equivalent
authenticated, local-only mechanism. A Unix domain socket satisfies this
literally and identically on both platforms: Windows has shipped native
AF_UNIX support since Windows 10 build 17063 (GA since version 1809 /
Windows Server 2019), .NET's `UnixDomainSocketEndPoint` has worked on
Windows since .NET Core 3.0, and Python's `socket` module has supported
AF_UNIX on Windows since 3.9 -- so this one implementation runs
unmodified on both, rather than needing a second, named-pipe-specific
code path that could only ever be tested on a Windows machine this
project has never had access to.

A Unix domain socket is not "local" merely by convention the way a
127.0.0.1 TCP port is (any process that can reach loopback can connect,
including from inside a container's shared network namespace, and the
listening port is visible to `netstat`/`ss`); it never touches the TCP/IP
stack at all, is addressed by filesystem path, and access is governed by
filesystem permissions -- a real difference, not a paper one.

Serving stays on FastAPI/uvicorn and the client stays on HttpClient in
both C# apps: the entire existing HTTP/1.1 request/response/SSE-streaming
code (AuraApiClient, HttpProviders, and every test against them) keeps
working completely unmodified, because uvicorn's `uds=` parameter and
.NET's `SocketsHttpHandler.ConnectCallback` both let the transport be
swapped out from under an otherwise-ordinary HTTP client/server pair.
"""
from __future__ import annotations

import os


def default_socket_path(sandbox_dir: str) -> str:
    """Same sibling-of-the-sandbox convention as identity/token_store.py's
    default_token_path -- one predictable, owner-writable location for
    this installation's local runtime state."""
    parent = os.path.dirname(os.path.abspath(sandbox_dir))
    return os.path.join(parent, ".aura", "core.sock")
