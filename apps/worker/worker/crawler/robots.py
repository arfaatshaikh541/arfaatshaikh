"""robots.txt handling for the enrichment crawler.

`robots.txt` itself is fetched through the same SSRF-safe `safe_get` every
other crawl request uses. One `RobotsChecker` is created per crawl (one
business's enrichment run) - not cached across runs, since a site's
robots.txt can legitimately change between visits and re-fetching it once
per crawl is cheap.
"""

import urllib.robotparser
from urllib.parse import urljoin

import httpx

from worker.crawler.safety import FetchError, UnsafeUrlError, safe_get

DEFAULT_USER_AGENT = "GridkeepLeadIntelBot"


class RobotsChecker:
    def __init__(
        self,
        origin_url: str,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._user_agent = user_agent
        self._parser = urllib.robotparser.RobotFileParser()
        self._loaded = False
        self._robots_url = urljoin(origin_url, "/robots.txt")
        self._transport = transport

    async def load(self) -> None:
        try:
            response = await safe_get(self._robots_url, transport=self._transport)
        except (UnsafeUrlError, FetchError):
            # No robots.txt reachable/safe to fetch - the conventional
            # default when robots.txt is absent is "everything allowed".
            self._parser.parse([])
            self._loaded = True
            return

        if response.status_code >= 400:
            self._parser.parse([])
        else:
            self._parser.parse(response.text.splitlines())
        self._loaded = True

    def can_fetch(self, url: str) -> bool:
        if not self._loaded:
            raise RuntimeError("RobotsChecker.load() must be awaited before can_fetch().")
        return self._parser.can_fetch(self._user_agent, url)

    def crawl_delay(self) -> float | None:
        if not self._loaded:
            raise RuntimeError("RobotsChecker.load() must be awaited before crawl_delay().")
        delay = self._parser.crawl_delay(self._user_agent)
        return float(delay) if delay is not None else None
