"""SSRF-safe HTTP fetching for the website enrichment crawler.

Threat model: `Business.website` values come from a connector (Google
Places today, eventually CSV import - see Milestone 8) and are not fully
trusted input - a malicious or compromised source could supply a URL that
resolves to an internal service (a cloud metadata endpoint, a database on
localhost, an internal admin panel) instead of a real public website.
Every enrichment page fetch goes through `safe_get` in this module, which
refuses anything but a genuinely public HTTP(S) resource:

- **Scheme allowlist**: only `http`/`https` - no `file://`, no `ftp://`,
  no `gopher://`.
- **Resolve-and-validate always runs first, unconditionally.** The
  hostname is resolved via asyncio's own (non-blocking) resolver, and
  every resolved address must be public - private, loopback, link-local
  (this covers cloud metadata endpoints like 169.254.169.254), multicast,
  reserved, and unspecified addresses are all rejected, for both IPv4 and
  IPv6 (including IPv4-mapped IPv6). A hostname that resolves to *any*
  non-public address is rejected outright, even if it also resolves to a
  public one. This check is the primary defense and applies no matter
  what happens next.
- **Proxy-aware connection strategy.** If no `HTTP_PROXY`/`HTTPS_PROXY` is
  configured in the environment, the actual TCP connection is made
  directly to the one validated IP from the check above - never by
  hostname, which would let the connection layer re-resolve DNS at
  connect time and reopen the exact TOCTOU window a DNS-rebinding attack
  needs. If a proxy *is* configured, the request goes through it by
  hostname instead: an HTTP CONNECT proxy needs the real hostname to
  establish its tunnel, and connecting to a raw IP breaks that (a
  policy-enforcing proxy, like this project's own dev sandbox, rejects it
  outright as a 403). In that configuration, the resolve-and-validate
  check above is still enforced first, but the operator-configured proxy
  is trusted to apply its own network-layer egress controls for the
  connection itself - the same tradeoff any HTTP-CONNECT-proxied service
  makes, since no client-side DNS pinning is possible through a tunnel it
  doesn't control. See docs/adr/0012.
- **Redirects are followed manually**, one hop at a time, with the exact
  same validation re-applied to every redirect target - a same-domain
  chain cannot be used to smuggle a hop through an internal address. A
  hard cap (`MAX_REDIRECTS`) prevents infinite/absurd redirect chains.
- **A strict connect/read timeout and a hard, streamed response-size
  cap** - the body is never buffered unbounded, so a decompression bomb
  or an enormous page is aborted once it exceeds `MAX_RESPONSE_BYTES`,
  not after it's already been downloaded.

No cached HTTP client at module/instance scope, for the same ADR-0009
reason `GooglePlacesConnector` documents (`packages/connector-sdk/
connector_sdk/google_places.py`) - a fresh client is opened per fetch.
"""

import asyncio
import ipaddress
import os
import socket
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

ALLOWED_SCHEMES = {"http", "https"}
MAX_REDIRECTS = 5
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB
CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 10.0
USER_AGENT = "GridkeepLeadIntelBot/1.0 (+https://gridkeep.example/bot; enrichment crawler)"

_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}


class UnsafeUrlError(Exception):
    """A URL failed an SSRF safety check - permanent, never retry it."""


class FetchError(Exception):
    """A safe-target fetch still failed (timeout, connection error,
    too many redirects, response too large) - may be worth retrying."""


@dataclass
class SafeResponse:
    url: str  # the final URL actually fetched, after any redirects
    status_code: int
    headers: dict[str, str]
    text: str
    used_https: bool


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _proxy_env_configured(scheme: str) -> bool:
    """Whether an env-configured proxy would apply to a request of this
    scheme, mirroring httpx's own default `trust_env` proxy discovery
    (HTTPS_PROXY/https_proxy for https, HTTP_PROXY/http_proxy for http).
    Deliberately does not replicate NO_PROXY's finer-grained per-host
    exemptions - website enrichment targets are external business sites,
    which practically never match a NO_PROXY list (those are typically
    internal/cluster hostnames, as in this project's own dev sandbox's
    NO_PROXY) - see the module docstring's proxy-aware paragraph."""
    if scheme == "https":
        return bool(os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"))
    return bool(os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"))


async def _resolve_safe_ip(hostname: str, port: int) -> str:
    """Resolves `hostname` and returns one validated-public IP as a
    string. Raises UnsafeUrlError if the hostname doesn't resolve, or if
    *any* resolved address is private/internal."""
    loop = asyncio.get_running_loop()
    try:
        results = await loop.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"Could not resolve host: {hostname}") from exc
    if not results:
        raise UnsafeUrlError(f"Could not resolve host: {hostname}")

    resolved_ips = {str(info[4][0]) for info in results}
    for ip_str in resolved_ips:
        ip = ipaddress.ip_address(ip_str.split("%")[0])  # strip IPv6 zone id, if any
        if not _is_public_ip(ip):
            raise UnsafeUrlError(
                f"Host {hostname!r} resolves to a non-public address ({ip_str}) - refusing to fetch."
            )
    return next(iter(resolved_ips))


async def safe_get(
    url: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    _redirect_count: int = 0,
) -> SafeResponse:
    """Fetches `url` if (and only if) it passes every SSRF safety check
    above, manually following same-safety-checked redirects up to
    `MAX_REDIRECTS`.

    `transport` is a test-only seam (mirrors `GooglePlacesConnector`'s
    same parameter) for injecting an `httpx.MockTransport` - the
    resolve-and-validate check above still runs against real DNS even in
    tests; only the actual HTTP exchange is substituted. Never set in
    production code."""
    if _redirect_count > MAX_REDIRECTS:
        raise FetchError(f"Too many redirects (> {MAX_REDIRECTS}) resolving {url}")

    parsed = httpx.URL(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"Unsupported scheme: {parsed.scheme!r}")
    if not parsed.host:
        raise UnsafeUrlError("URL has no host")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    # Always resolve-and-validate first, regardless of what happens next -
    # this is the primary defense and applies unconditionally, even when a
    # test transport is injected below (only the actual HTTP exchange is
    # substituted in tests, never this check).
    await _resolve_safe_ip(parsed.host, port)

    if transport is not None:
        # Test seam: a MockTransport matches requests by the original
        # hostname, not a resolved IP or a proxy tunnel - see docstring.
        request_url = parsed
        headers = {"User-Agent": USER_AGENT}
        extensions: dict[str, object] = {}
    elif _proxy_env_configured(parsed.scheme):
        # A proxy is in play: connect by hostname (through the
        # operator-configured, trusted proxy) rather than by IP, since an
        # HTTP CONNECT tunnel needs the real hostname - see module
        # docstring.
        request_url = parsed
        headers = {"User-Agent": USER_AGENT}
        extensions = {}
    else:
        # No proxy - connect directly to the pre-validated IP so nothing
        # between the check above and the actual connection can
        # re-resolve DNS to a different (possibly internal) address.
        resolved_ip = await _resolve_safe_ip(parsed.host, port)
        request_url = parsed.copy_with(host=resolved_ip)
        headers = {"Host": parsed.host, "User-Agent": USER_AGENT}
        extensions = {"sni_hostname": parsed.host}

    timeout = httpx.Timeout(
        connect=CONNECT_TIMEOUT_SECONDS,
        read=READ_TIMEOUT_SECONDS,
        write=READ_TIMEOUT_SECONDS,
        pool=READ_TIMEOUT_SECONDS,
    )
    try:
        async with (
            httpx.AsyncClient(
                timeout=timeout, follow_redirects=False, transport=transport
            ) as client,
            client.stream(
                "GET", str(request_url), headers=headers, extensions=extensions
            ) as response,
        ):
            if response.status_code in _REDIRECT_STATUS_CODES:
                location = response.headers.get("location")
                if not location:
                    raise FetchError(f"Redirect from {url} had no Location header")
                # Resolved against the *original* (hostname-based) URL,
                # not the IP-substituted request_url, so relative
                # redirects behave the way the site actually intends.
                next_url = urljoin(str(parsed), location)
                await response.aclose()
                return await safe_get(
                    next_url, transport=transport, _redirect_count=_redirect_count + 1
                )

            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise FetchError(f"Response from {url} exceeded {MAX_RESPONSE_BYTES} bytes")
            text = body.decode(response.encoding or "utf-8", errors="replace")
            return SafeResponse(
                url=str(parsed),
                status_code=response.status_code,
                headers=dict(response.headers),
                text=text,
                used_https=parsed.scheme == "https",
            )
    except httpx.TimeoutException as exc:
        raise FetchError(f"Timed out fetching {url}: {exc}") from exc
    except httpx.TransportError as exc:
        raise FetchError(f"Connection failed for {url}: {exc}") from exc
