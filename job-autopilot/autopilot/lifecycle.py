"""Process lifecycle: an interruptible sleep tied to graceful shutdown."""
from __future__ import annotations

import threading

STOP = threading.Event()


class ShuttingDown(Exception):
    pass


def sleep(seconds: float) -> None:
    """Sleep that returns early (raising ShuttingDown) when the process is asked to stop."""
    if seconds > 0 and STOP.wait(seconds):
        raise ShuttingDown()
    if STOP.is_set():
        raise ShuttingDown()


# Main-loop progress marker for the worker self-watchdog.
_progress = [0.0]


def touch() -> None:
    import time

    _progress[0] = time.monotonic()


def last_progress() -> float:
    return _progress[0]
