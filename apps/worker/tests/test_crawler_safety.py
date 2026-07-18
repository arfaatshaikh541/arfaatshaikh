"""Tests for `worker.crawler.safety.safe_get` - the SSRF-safe fetcher.

Two distinct kinds of test here, deliberately not blended:

1. SSRF-blocking tests use **real DNS resolution** (no mocking) against
   real blocked targets - loopback, the cloud metadata link-local address,
   a private RFC1918 address, `localhost`, and a disallowed scheme. These
   prove the actual resolve-and-validate defense works, not a stand-in for
   it.
2. Fetch-mechanics tests (redirects, size cap, status codes) use an
   injected `httpx.MockTransport` against `example.com` purely as a DNS
   target that genuinely resolves to a public IP - no real request to it
   is ever made, since the mock transport intercepts every request
   regardless of host. Live internet crawling is not exercised by this
   suite; see docs/adr/0012 for why (this sandbox's egress proxy blocks
   general internet access).
"""

import httpx
import pytest
from worker.crawler.safety import (
    MAX_REDIRECTS,
    FetchError,
    UnsafeUrlError,
    safe_get,
)

pytestmark = pytest.mark.asyncio


async def test_blocks_loopback_ip():
    with pytest.raises(UnsafeUrlError):
        await safe_get("http://127.0.0.1:1/")


async def test_blocks_localhost_hostname():
    with pytest.raises(UnsafeUrlError):
        await safe_get("http://localhost/")


async def test_blocks_cloud_metadata_link_local_address():
    with pytest.raises(UnsafeUrlError):
        await safe_get("http://169.254.169.254/latest/meta-data/")


async def test_blocks_private_rfc1918_address():
    with pytest.raises(UnsafeUrlError):
        await safe_get("http://10.0.0.5/")


async def test_blocks_disallowed_scheme():
    with pytest.raises(UnsafeUrlError):
        await safe_get("file:///etc/passwd")


async def test_blocks_ftp_scheme():
    with pytest.raises(UnsafeUrlError):
        await safe_get("ftp://example.com/")


async def test_fetch_mechanics_successful_response_returns_text_and_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="hello world")

    response = await safe_get("https://example.com/", transport=httpx.MockTransport(handler))
    assert response.status_code == 200
    assert response.text == "hello world"
    assert response.used_https is True


async def test_fetch_mechanics_follows_redirect_and_revalidates_target():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(302, headers={"location": "https://example.com/new"})
        return httpx.Response(200, text="destination page")

    response = await safe_get("https://example.com/old", transport=httpx.MockTransport(handler))
    assert response.text == "destination page"
    assert response.url == "https://example.com/new"


async def test_fetch_mechanics_redirect_to_unsafe_target_is_blocked():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/steal"})

    with pytest.raises(UnsafeUrlError):
        await safe_get("https://example.com/", transport=httpx.MockTransport(handler))


async def test_fetch_mechanics_too_many_redirects_raises_fetch_error():
    def handler(request: httpx.Request) -> httpx.Response:
        n = int(request.url.path.lstrip("/") or "0")
        return httpx.Response(302, headers={"location": f"https://example.com/{n + 1}"})

    with pytest.raises(FetchError):
        await safe_get("https://example.com/0", transport=httpx.MockTransport(handler))


async def test_fetch_mechanics_redirect_without_location_header_raises_fetch_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302)

    with pytest.raises(FetchError):
        await safe_get("https://example.com/", transport=httpx.MockTransport(handler))


async def test_fetch_mechanics_response_over_size_cap_raises_fetch_error(monkeypatch):
    monkeypatch.setattr("worker.crawler.safety.MAX_RESPONSE_BYTES", 100)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="x" * 1000)

    with pytest.raises(FetchError):
        await safe_get("https://example.com/", transport=httpx.MockTransport(handler))


async def test_fetch_mechanics_passes_through_4xx_status_without_raising():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    response = await safe_get("https://example.com/missing", transport=httpx.MockTransport(handler))
    assert response.status_code == 404


async def test_max_redirects_constant_is_reasonable():
    # Guards against an accidental huge/zero value silently defeating the
    # protection the "too many redirects" test above exercises.
    assert 1 <= MAX_REDIRECTS <= 10
