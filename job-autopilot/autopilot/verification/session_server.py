"""Remote browser session server (runs inside each worker, on the internal network only).

Chromium itself is launched by Playwright over a pipe: no remote-debugging port exists.
This server exposes nothing but the page a worker is *holding for human verification*:

  web gateway --(ws://worker:9310/session/<vid>?t=<signed token>)--> this server
     binary frames  : JPEG screenshots of the held page's viewport
     text frames    : status JSON
     client -> here : {"type": click|type|key|scroll|done, ...}  (validated, queued)

Input is applied to the page by the worker's main thread (Playwright is single-threaded);
this server only moves bytes. Typed text is never logged.
"""
from __future__ import annotations

import asyncio
import json
import logging
import queue
import socket
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

from websockets.asyncio.server import serve

from . import tokens

log = logging.getLogger(__name__)

ALLOWED_KEYS = {"Enter", "Tab", "Backspace", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space",
                "Delete", "Home", "End"}


@dataclass
class SessionChannel:
    vid: int
    viewport: tuple[int, int]
    inbound: "queue.Queue[dict]" = field(default_factory=lambda: queue.Queue(maxsize=500))
    frame: bytes | None = None
    seq: int = 0
    status: dict = field(default_factory=dict)
    status_seq: int = 0
    clients: int = 0
    ever_connected: bool = False
    closed: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)

    def publish(self, jpeg: bytes) -> None:
        with self.lock:
            self.frame = jpeg
            self.seq += 1

    def set_status(self, **st) -> None:
        with self.lock:
            self.status = st
            self.status_seq += 1


def validate_event(raw: str, viewport: tuple[int, int]) -> dict | None:
    try:
        e = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(e, dict):
        return None
    t = e.get("type")
    w, h = viewport
    if t in ("click", "dblclick"):
        try:
            x, y = float(e["x"]), float(e["y"])
        except (KeyError, TypeError, ValueError):
            return None
        return {"type": t, "x": x, "y": y} if 0 <= x <= w and 0 <= y <= h else None
    if t == "type":
        text = e.get("text")
        return {"type": "type", "text": text} if isinstance(text, str) and 0 < len(text) <= 256 else None
    if t == "key":
        return {"type": "key", "key": e.get("key")} if e.get("key") in ALLOWED_KEYS else None
    if t == "scroll":
        try:
            dy = max(-3000.0, min(3000.0, float(e.get("dy", 0))))
        except (TypeError, ValueError):
            return None
        return {"type": "scroll", "dy": dy}
    if t == "done":
        return {"type": "done"}
    return None


class SessionServer:
    def __init__(self, host: str, port: int, advertise_host: str = ""):
        self.host, self.port = host, port
        self.channels: dict[int, SessionChannel] = {}
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._error: Exception | None = None
        self.advertise_host = advertise_host or socket.gethostbyname(socket.gethostname())
        self._thread = threading.Thread(target=self._run, name="session-server", daemon=True)
        self._thread.start()
        self._ready.wait(10)
        if self._error:
            raise self._error

    @property
    def endpoint(self) -> str:
        return f"{self.advertise_host}:{self.port}"

    def _run(self) -> None:
        async def main():
            try:
                async with serve(self._handler, self.host, self.port, max_size=64 * 1024, ping_interval=20):
                    self._ready.set()
                    await asyncio.Future()
            except Exception as e:  # pragma: no cover - bind failures
                self._error = e
                self._ready.set()

        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(main())

    def open(self, vid: int, viewport: tuple[int, int]) -> SessionChannel:
        ch = SessionChannel(vid, viewport)
        with self._lock:
            self.channels[vid] = ch
        return ch

    def close(self, vid: int, message: str) -> None:
        with self._lock:
            ch = self.channels.pop(vid, None)
        if ch:
            ch.set_status(state="closed", message=message)
            ch.closed = True

    async def _handler(self, ws) -> None:
        req = urlsplit(ws.request.path)
        parts = req.path.strip("/").split("/")
        if len(parts) != 2 or parts[0] != "session" or not parts[1].isdigit():
            await ws.close(4404, "not found")
            return
        vid = int(parts[1])
        token = (parse_qs(req.query).get("t") or [""])[0]
        if tokens.verify(token, vid) is None:
            await ws.close(4401, "unauthorized")
            return
        ch = self.channels.get(vid)
        if ch is None or ch.closed:
            await ws.close(4410, "session not held")
            return
        ch.clients += 1
        ch.ever_connected = True
        await ws.send(json.dumps({"type": "hello", "viewport": list(ch.viewport)}))

        async def sender():
            last_seq = last_status = -1
            while True:
                if ch.status_seq != last_status:
                    last_status = ch.status_seq
                    await ws.send(json.dumps({"type": "status", **ch.status}))
                if ch.closed:
                    await ws.close(1000, "session closed")
                    return
                with ch.lock:
                    seq, frame = ch.seq, ch.frame
                if frame is not None and seq != last_seq:
                    last_seq = seq
                    await ws.send(frame)
                await asyncio.sleep(0.15)

        async def receiver():
            async for raw in ws:
                if isinstance(raw, bytes):
                    continue
                evt = validate_event(raw, ch.viewport)
                if evt is not None:
                    try:
                        ch.inbound.put_nowait(evt)
                    except queue.Full:
                        pass

        tasks = [asyncio.ensure_future(sender()), asyncio.ensure_future(receiver())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:
                t.cancel()
            ch.clients = max(0, ch.clients - 1)
