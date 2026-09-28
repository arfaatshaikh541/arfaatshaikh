"""Playwright browser lifecycle.

* Stock Chromium, stock user agent. No stealth plugins, no fingerprint
  spoofing, no automation-flag hiding: sites can see this is automated.
* One isolated BrowserContext per application (no cookie bleed between jobs).
* Tracing/HAR recording is never enabled: they would capture typed secrets.
"""
from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from typing import Iterator

from playwright.sync_api import Browser, BrowserContext, Error as PWError, Playwright, sync_playwright

from ..config import get_config

log = logging.getLogger(__name__)


class BrowserManager:
    def __init__(self) -> None:
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self.launches = 0

    def _launch(self) -> Browser:
        cfg = get_config()
        if self._pw is None:
            self._pw = sync_playwright().start()
        kwargs = {"headless": cfg.headless}
        if cfg.browser_executable:
            kwargs["executable_path"] = cfg.browser_executable
        self._browser = self._pw.chromium.launch(**kwargs)
        self.launches += 1
        log.info("browser launched", extra={"event": "browser_launch", "result": self._browser.version})
        return self._browser

    def browser(self) -> Browser:
        if self._browser is None or not self._browser.is_connected():
            if self._browser is not None:
                log.warning("browser disconnected; restarting", extra={"event": "browser_restart"})
            return self._launch()
        return self._browser

    @contextmanager
    def context(self, storage_state: dict | None = None) -> Iterator[tuple[BrowserContext, str]]:
        """Fresh isolated context. Yields (context, session_id)."""
        sid = uuid.uuid4().hex[:16]
        try:
            ctx = self.browser().new_context(storage_state=storage_state, accept_downloads=False,
                                             viewport={"width": 1366, "height": 900})
        except PWError:
            self.restart()
            ctx = self.browser().new_context(storage_state=storage_state, accept_downloads=False,
                                             viewport={"width": 1366, "height": 900})
        ctx.set_default_timeout(30_000)
        try:
            yield ctx, sid
        finally:
            try:
                ctx.close()
            except PWError:
                pass

    def restart(self) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
        except PWError:
            pass
        self._browser = None

    def health(self) -> tuple[bool, str]:
        try:
            b = self.browser()
            return True, f"Chromium {b.version}"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"[:200]

    def close(self) -> None:
        self.restart()
        if self._pw is not None:
            self._pw.stop()
            self._pw = None
