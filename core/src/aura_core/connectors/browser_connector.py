"""Browser automation connector via Playwright. Real: launches an actual
headless Chromium and drives it, verified in this build environment
(where Chromium happens to be pre-installed) against real local pages.

Two lifecycle modes: without a profile directory, every action launches
and closes a fresh, throwaway browser (simple, no state to leak between
actions). With one configured (AURA_BROWSER_PROFILE_DIR), every action
still launches and closes a fresh browser *process*, but points it at
the same on-disk Chromium user-data directory via
launch_persistent_context() -- cookies, localStorage, and login sessions
persist across actions and across restarts, closing the "persistent
authenticated profiles" gap without keeping a browser process alive
between broker calls (which would turn every action into a stateful
session with its own lifecycle/cleanup/thread-safety problems -- a much
larger and riskier redesign than what was actually asked for).
"""
from __future__ import annotations

import base64
import json
import os

from ..governance.action_broker import ActionRequest, HandlerResult
from ..status import CapabilityStatus
from .base import Connector, ConnectorManifest

# Deliberately conservative (biased toward false positives, never false
# negatives): per the product spec, AURA must escalate a CAPTCHA to the
# owner rather than attempt to bypass it, so it's far better to
# occasionally over-flag an ordinary page as "maybe a CAPTCHA" than to
# ever proceed with automated action against a real one.
_CAPTCHA_SELECTORS = [
    "iframe[src*='recaptcha' i]",
    "iframe[src*='hcaptcha' i]",
    "iframe[title*='captcha' i]",
    ".g-recaptcha",
    ".h-captcha",
    "[class*='captcha' i]",
    "[id*='captcha' i]",
]


class BrowserConnector(Connector):
    def __init__(
        self, executable_path: str | None = None, allowed_hosts: list[str] | None = None,
        profile_dir: str | None = None, download_dir: str | None = None,
    ) -> None:
        # AURA_PLAYWRIGHT_EXECUTABLE lets this run in environments (like
        # this one) where the installed browser revision doesn't match
        # what the playwright pip package expects by default.
        self._executable_path = executable_path or os.environ.get("AURA_PLAYWRIGHT_EXECUTABLE")
        self._allowed_hosts = set(allowed_hosts or [])
        self._profile_dir = profile_dir
        self._download_dir = download_dir
        self.manifest = ConnectorManifest(
            name="browser",
            auth_method="none",
            capabilities=[
                "browser.navigate", "browser.extract_text", "browser.screenshot",
                "browser.extract_text_multi", "browser.download_file",
            ],
            notes=f"headless Chromium via Playwright{'; persistent profile' if profile_dir else ''}",
        )

    def _resolve_download_path(self, save_as: str) -> str | None:
        """Same sandbox-escape protection FilesystemConnector applies --
        a download is a real write to disk, and `save_as` is owner/model-
        supplied text, so `../../whatever` must never land outside the
        configured download directory."""
        if self._download_dir is None:
            return None
        root = os.path.abspath(self._download_dir)
        candidate = os.path.abspath(os.path.join(root, save_as))
        if candidate != root and not candidate.startswith(root + os.sep):
            return None
        return candidate

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

    def _detect_captcha(self, page) -> bool:
        for selector in _CAPTCHA_SELECTORS:
            try:
                if page.query_selector(selector) is not None:
                    return True
            except Exception:  # noqa: BLE001 -- a selector-engine quirk must never crash detection itself
                continue
        return False

    def _launch(self, p):
        """Returns (context, browser_or_none). In persistent-profile mode
        there is no separate browser handle -- context.close() tears
        down the whole launched process; otherwise a plain browser +
        fresh context is used and both must be closed."""
        launch_kwargs = {"args": ["--no-sandbox"]}
        if self._executable_path:
            launch_kwargs["executable_path"] = self._executable_path

        if self._profile_dir:
            os.makedirs(self._profile_dir, exist_ok=True)
            context = p.chromium.launch_persistent_context(self._profile_dir, **launch_kwargs)
            return context, None

        browser = p.chromium.launch(**launch_kwargs)
        return browser.new_context(), browser

    def _with_page(self, url: str, fn):
        from playwright.sync_api import sync_playwright

        denial = self._check_allowed(url)
        if denial:
            return HandlerResult(CapabilityStatus.BLOCKED_BY_POLICY, denial)

        try:
            with sync_playwright() as p:
                context, browser = self._launch(p)
                try:
                    page = context.new_page()
                    page.goto(url, timeout=15000)
                    if self._detect_captcha(page):
                        # Never attempt to solve or work around it --
                        # escalate to the owner instead, per the product
                        # spec's explicit instruction on this exact case.
                        return HandlerResult(
                            CapabilityStatus.BLOCKED_BY_POLICY,
                            f"CAPTCHA detected on {url} -- escalating to the owner rather than attempting to bypass it",
                        )
                    return fn(page)
                finally:
                    context.close()
                    if browser is not None:
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

    def extract_text_multi(self, request: ActionRequest) -> HandlerResult:
        """Genuine multi-tab operation: every target in `targets` gets
        its own Page within one shared browser context, open
        concurrently (not one-at-a-time launch/close per URL), so a
        CAPTCHA or failure on one tab is isolated and reported per-tab
        rather than aborting the whole batch."""
        from playwright.sync_api import sync_playwright

        targets: list[dict] = request.params["targets"]
        for target in targets:
            denial = self._check_allowed(target["url"])
            if denial:
                return HandlerResult(CapabilityStatus.BLOCKED_BY_POLICY, denial)

        try:
            with sync_playwright() as p:
                context, browser = self._launch(p)
                try:
                    pages = [context.new_page() for _ in targets]
                    results = []
                    for page, target in zip(pages, targets):
                        try:
                            page.goto(target["url"], timeout=15000)
                            if self._detect_captcha(page):
                                results.append({
                                    "url": target["url"],
                                    "error": "CAPTCHA detected -- escalating to the owner rather than attempting to bypass it",
                                })
                                continue
                            selector = target.get("selector", "body")
                            results.append({"url": target["url"], "text": page.inner_text(selector)})
                        except Exception as exc:  # noqa: BLE001 -- one tab's failure must not sink the batch
                            results.append({"url": target["url"], "error": str(exc)})
                    return HandlerResult(CapabilityStatus.LIVE, json.dumps(results))
                finally:
                    for page in pages:
                        page.close()
                    context.close()
                    if browser is not None:
                        browser.close()
        except Exception as exc:  # noqa: BLE001
            return HandlerResult(CapabilityStatus.DEGRADED, f"multi-tab browser action failed: {exc}")

    def download_file(self, request: ActionRequest) -> HandlerResult:
        """Real Playwright download handling via page.expect_download(),
        closing the "download handling" gap named in
        FINAL_COMPLETION_AUDIT.md's browser row. Two trigger shapes:
        `trigger_selector` given -- navigate to `url`, click the element
        that starts the download (a real link/button click, not a raw
        HTTP GET, so it works for JS-driven download flows too); omitted
        -- `url` is treated as a direct download link, and the download
        event is caught around the navigation itself (a pure file
        response often aborts Playwright's navigation with an error even
        though the download still fires -- that's expected, not a
        failure, so it's swallowed here specifically).
        """
        from playwright.sync_api import sync_playwright

        url = request.params["url"]
        save_as = request.params["save_as"]
        trigger_selector = request.params.get("trigger_selector")

        target_path = self._resolve_download_path(save_as)
        if target_path is None:
            if self._download_dir is None:
                return HandlerResult(CapabilityStatus.DEGRADED, "no download directory configured -- set AURA_BROWSER_DOWNLOAD_DIR")
            return HandlerResult(CapabilityStatus.DEGRADED, f"'{save_as}' escapes the configured download directory")

        denial = self._check_allowed(url)
        if denial:
            return HandlerResult(CapabilityStatus.BLOCKED_BY_POLICY, denial)

        try:
            with sync_playwright() as p:
                context, browser = self._launch(p)
                try:
                    page = context.new_page()
                    with page.expect_download(timeout=15000) as download_info:
                        if trigger_selector:
                            page.goto(url, timeout=15000)
                            page.click(trigger_selector)
                        else:
                            try:
                                page.goto(url, timeout=15000)
                            except Exception:  # noqa: BLE001 -- a direct-file response legitimately aborts navigation
                                pass
                    download = download_info.value
                    download.save_as(target_path)
                    return HandlerResult(CapabilityStatus.LIVE, json.dumps({
                        "saved_to": target_path, "suggested_filename": download.suggested_filename,
                    }))
                finally:
                    context.close()
                    if browser is not None:
                        browser.close()
        except Exception as exc:  # noqa: BLE001
            return HandlerResult(CapabilityStatus.DEGRADED, f"download failed: {exc}")

    def handlers(self) -> dict:
        return {
            "browser.navigate": self.navigate,
            "browser.extract_text": self.extract_text,
            "browser.screenshot": self.screenshot,
            "browser.extract_text_multi": self.extract_text_multi,
            "browser.download_file": self.download_file,
        }
