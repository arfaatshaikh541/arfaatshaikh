"""Tests for `worker.crawler.fetcher.crawl_site` - the bounded per-site
crawl orchestrator. Uses an injected `httpx.MockTransport` against
`example.com` purely as a DNS target (see test_crawler_safety.py's module
docstring for why a real-resolving hostname is required even in mock-
transport tests). `MIN_SECONDS_BETWEEN_REQUESTS` is monkeypatched down so
these tests don't spend real wall-clock time on the crawler's per-domain
rate limiting, which is exercised at its default value implicitly (a
sleep of *some* positive duration occurs) but not timed precisely here.
"""

import httpx
import pytest
from worker.crawler import fetcher as fetcher_module
from worker.crawler.fetcher import CANDIDATE_PATHS, crawl_site

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _fast_rate_limit(monkeypatch):
    monkeypatch.setattr(fetcher_module, "MIN_SECONDS_BETWEEN_REQUESTS", 0.01)


ROBOTS_ALLOW_ALL = "User-agent: *\nAllow: /\n"


async def test_crawl_site_fetches_homepage_and_candidate_pages():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS_ALLOW_ALL)
        if request.url.path in ("/", "/contact", "/about"):
            return httpx.Response(200, text=f"<html><body>{request.url.path}</body></html>")
        return httpx.Response(404)

    result = await crawl_site("https://example.com/", transport=httpx.MockTransport(handler))
    assert result.site_reachable is True
    fetched_paths = {p.url for p in result.pages}
    assert "https://example.com/" in fetched_paths
    assert "https://example.com/contact" in fetched_paths
    assert "https://example.com/about" in fetched_paths
    # 404s for the rest of the candidate paths are simply not included -
    # not an error, not a reason to stop the crawl.
    assert len(result.pages) == 3


async def test_crawl_site_never_exceeds_max_pages_per_site(monkeypatch):
    monkeypatch.setattr(fetcher_module, "MAX_PAGES_PER_SITE", 2)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS_ALLOW_ALL)
        return httpx.Response(200, text="<html><body>page</body></html>")

    result = await crawl_site("https://example.com/", transport=httpx.MockTransport(handler))
    assert len(result.pages) == 2


async def test_crawl_site_only_visits_the_fixed_candidate_path_set():
    visited_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS_ALLOW_ALL)
        visited_paths.append(request.url.path)
        return httpx.Response(200, text="<html><body>page</body></html>")

    await crawl_site("https://example.com/", transport=httpx.MockTransport(handler))
    assert set(visited_paths) <= set(CANDIDATE_PATHS)


async def test_crawl_site_respects_robots_disallow():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /contact\n")
        return httpx.Response(200, text=f"<html><body>{request.url.path}</body></html>")

    result = await crawl_site("https://example.com/", transport=httpx.MockTransport(handler))
    fetched_paths = {p.url for p in result.pages}
    assert "https://example.com/contact" not in fetched_paths
    assert "https://example.com/" in fetched_paths


async def test_crawl_site_missing_robots_txt_defaults_to_allow_everything():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text=f"<html><body>{request.url.path}</body></html>")

    result = await crawl_site("https://example.com/", transport=httpx.MockTransport(handler))
    assert len(result.pages) > 0


async def test_crawl_site_unreachable_host_reports_not_reachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    result = await crawl_site("https://example.com/", transport=httpx.MockTransport(handler))
    assert result.site_reachable is False
    assert result.pages == []


async def test_crawl_site_falls_back_from_https_to_http_and_flags_ssl_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        # SSL failure is connection-level - it applies to every path on
        # this host over https, robots.txt included, so that check must
        # come before the robots.txt special-case below.
        if request.url.scheme == "https":
            raise httpx.ConnectError("ssl handshake failed", request=request)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS_ALLOW_ALL)
        return httpx.Response(200, text="<html><body>http only</body></html>")

    result = await crawl_site("https://example.com/", transport=httpx.MockTransport(handler))
    assert result.site_reachable is True
    assert result.ssl_failure is True
    assert result.final_scheme == "http"
    assert all(p.url.startswith("http://") for p in result.pages)


async def test_crawl_site_never_visits_the_same_url_twice():
    visited = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS_ALLOW_ALL)
        visited.append(request.url.path)
        return httpx.Response(200, text="<html><body>page</body></html>")

    await crawl_site("https://example.com/", transport=httpx.MockTransport(handler))
    assert len(visited) == len(set(visited))
