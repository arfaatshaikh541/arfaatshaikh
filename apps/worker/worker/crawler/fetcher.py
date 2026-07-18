"""Orchestrates a bounded, same-domain crawl of one business's website: a
fixed candidate page set (homepage plus likely paths - see
`CANDIDATE_PATHS`), respecting robots.txt, a per-domain minimum request
interval, and a hard page-count limit. Never a full-site crawl.

The per-domain rate limit here is process-local (a sleep between
consecutive requests within one crawl), not a distributed/cross-worker
limiter - sufficient for its actual purpose, which is spacing out the
handful of requests *this one crawl* makes to *this one site*, not
coordinating across every worker process that might ever crawl the same
domain for a different business. See docs/adr/0012.
"""

import asyncio
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from worker.crawler.robots import RobotsChecker
from worker.crawler.safety import FetchError, SafeResponse, UnsafeUrlError, safe_get

MAX_PAGES_PER_SITE = 6
MIN_SECONDS_BETWEEN_REQUESTS = 1.5

# Homepage first, then the pages most likely to carry contact/booking/
# ordering signals - matches the architecture's explicit "search a
# limited set of likely pages" requirement, not a full-site crawl.
CANDIDATE_PATHS = (
    "/",
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
    "/booking",
    "/reservations",
    "/order",
    "/menu",
    "/services",
)


@dataclass
class CrawledPage:
    url: str
    response: SafeResponse


@dataclass
class CrawlResult:
    pages: list[CrawledPage]
    site_reachable: bool
    ssl_failure: bool  # https:// was requested/expected but only http:// worked
    final_scheme: str | None  # the scheme that actually worked, if any


async def _probe_scheme(
    origin_host: str, *, prefer_https: bool, transport: httpx.AsyncBaseTransport | None
) -> tuple[str | None, bool]:
    """Tries https first (if preferred), falling back to http. Returns
    (working_scheme_or_None, ssl_failure) - ssl_failure is True only when
    https specifically failed but http on the same host succeeded.

    Probes by fetching `/robots.txt`, not the homepage: robots.txt is
    always exempt from robots-compliance rules (fetching it to *find out*
    the rules obviously can't itself require checking them first), so this
    determines connectivity/scheme without either (a) fetching a real
    content page before robots.txt has even been loaded, which would
    ignore a `Disallow: /`, or (b) requiring the homepage to be fetched
    twice - once to probe, once in the crawl loop below as the first
    candidate path."""
    schemes_to_try = ["https", "http"] if prefer_https else ["http", "https"]
    first_scheme, second_scheme = schemes_to_try
    try:
        await safe_get(f"{first_scheme}://{origin_host}/robots.txt", transport=transport)
        return first_scheme, False
    except (UnsafeUrlError, FetchError):
        pass

    try:
        await safe_get(f"{second_scheme}://{origin_host}/robots.txt", transport=transport)
        return second_scheme, prefer_https and first_scheme == "https"
    except (UnsafeUrlError, FetchError):
        return None, False


async def crawl_site(
    website_url: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> CrawlResult:
    """Fetches up to `MAX_PAGES_PER_SITE` pages from the same host as
    `website_url`. Returns whatever pages were successfully and safely
    fetched - a partial result (even zero pages) is a valid, non-exceptional
    outcome; "the site didn't have a /booking page" is not an error.

    `transport` is a test-only seam threaded down to every `safe_get`
    call - see `worker.crawler.safety.safe_get`. Never set in production."""
    parsed_root = urlparse(website_url)
    prefer_https = parsed_root.scheme != "http"
    working_scheme, ssl_failure = await _probe_scheme(
        parsed_root.netloc, prefer_https=prefer_https, transport=transport
    )

    if working_scheme is None:
        return CrawlResult(pages=[], site_reachable=False, ssl_failure=False, final_scheme=None)

    origin = f"{working_scheme}://{parsed_root.netloc}"
    robots = RobotsChecker(origin, transport=transport)
    await robots.load()
    delay = max(robots.crawl_delay() or 0.0, MIN_SECONDS_BETWEEN_REQUESTS)

    pages: list[CrawledPage] = []
    last_request_at = 0.0
    seen_urls: set[str] = set()
    for path in CANDIDATE_PATHS:
        if len(pages) >= MAX_PAGES_PER_SITE:
            break
        candidate_url = urljoin(origin, path)
        if candidate_url in seen_urls or not robots.can_fetch(candidate_url):
            continue
        seen_urls.add(candidate_url)

        elapsed = time.monotonic() - last_request_at
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        last_request_at = time.monotonic()

        try:
            response = await safe_get(candidate_url, transport=transport)
        except (UnsafeUrlError, FetchError):
            continue
        if response.status_code >= 400:
            continue
        pages.append(CrawledPage(url=candidate_url, response=response))

    return CrawlResult(
        pages=pages, site_reachable=True, ssl_failure=ssl_failure, final_scheme=working_scheme
    )
