"""Browser automation connector via Playwright. Real: launches an actual
headless Chromium and drives it, verified in this build environment
(where Chromium happens to be pre-installed) against real local pages.
Launches a fresh browser per action — simpler and safer than managing
persistent browser state across calls, at some latency cost; worth
revisiting once real usage patterns are known.
"""
from __future__ import annotations

import base64
import os

from ..governance.action_broker import ActionRequest, HandlerResult
from ..status import CapabilityStatus
from .base import Connector, ConnectorManifest


class BrowserConnector(Connector):
    def __init__(self, executable_path: str | None = None, allowed_hosts: list[str] | None = None) -> None:
        # AURA_PLAYWRIGHT_EXECUTABLE lets this run in environments (like
        # this one) where the installed browser revision doesn't match
        # what the playwright pip package expects by default.
        self._executable_path = executable_path or os.environ.get("AURA_PLAYWRIGHT_EXECUTABLE")
        self._allowed_hosts = set(allowed_hosts or [])
        self.manifest = ConnectorManifest(
            name="browser",
            auth_method="none",
            capabilities=["browser.navigate", "browser.extract_text", "browser.screenshot"],
            notes="headless Chromium via Playwright",
        )

    def _check_allowed(self, url: str) -> str | None:
        from urllib.parse import urlparse
        if not self._allowed_hosts:
            return None  # no allowlist configured -- open by owner's choice
        host = urlparse(url).hostname
        if host not in self._allowed_hosts:
            return f"'{host}' is not on the browser egress allowlist {sorted(self._allowed_hosts)}"
        return None

    def health_check(self) -> HandlerResult:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return HandlerResult(CapabilityStatus.NOT_CONNECTED, "playwright package is not installed")

        try:
            with sync_playwright() as p:
                launch_kwargs = {"args": ["--no-sandbox"]}
                if self._executable_path:
                    launch_kwargs["executable_path"] = self._executable_path
                browser = p.chromium.launch(**launch_kwargs)
                browser.close()
            return HandlerResult(CapabilityStatus.LIVE, "headless Chromium launches successfully")
        except Exception as exc:  # noqa: BLE001 -- health check must never raise
            return HandlerResult(CapabilityStatus.UNAVAILABLE, f"browser launch failed: {exc}")

    def _with_page(self, url: str, fn):
        from playwright.sync_api import sync_playwright

        denial = self._check_allowed(url)
        if denial:
            return HandlerResult(CapabilityStatus.BLOCKED_BY_POLICY, denial)

        try:
            with sync_playwright() as p:
                launch_kwargs = {"args": ["--no-sandbox"]}
                if self._executable_path:
                    launch_kwargs["executable_path"] = self._executable_path
                browser = p.chromium.launch(**launch_kwargs)
                try:
                    page = browser.new_page()
                    page.goto(url, timeout=15000)
                    return fn(page)
                finally:
                    browser.close()
        except Exception as exc:  # noqa: BLE001
            return HandlerResult(CapabilityStatus.DEGRADED, f"browser action failed: {exc}")

    def navigate(self, request: ActionRequest) -> HandlerResult:
        return self._with_page(request.params["url"], lambda page: HandlerResult(CapabilityStatus.LIVE, page.title()))

    def extract_text(self, request: ActionRequest) -> HandlerResult:
        selector = request.params.get("selector", "body")
        return self._with_page(
            request.params["url"],
            lambda page: HandlerResult(CapabilityStatus.LIVE, page.inner_text(selector)),
        )

    def screenshot(self, request: ActionRequest) -> HandlerResult:
        def take(page):
            png_bytes = page.screenshot()
            return HandlerResult(CapabilityStatus.LIVE, base64.b64encode(png_bytes).decode("ascii"))

        return self._with_page(request.params["url"], take)

    def handlers(self) -> dict:
        return {
            "browser.navigate": self.navigate,
            "browser.extract_text": self.extract_text,
            "browser.screenshot": self.screenshot,
        }
