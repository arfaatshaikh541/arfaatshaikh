# ADR-0012: SSRF-safe website crawling, and its sandbox verification gap

## Status
Accepted, with one explicitly unresolved verification gap (see Consequences) -
the same shape of gap ADR-0010 documented for the Google Places connector.

## Context
Milestone 4 requires crawling a business's own website - a URL that,
unlike Milestone 3's Google Places responses, is not a value under this
system's control. `Business.website` is supplied by a connector today
(Google Places) and will be supplied by CSV import and other sources
later (Milestone 8); a malicious or compromised source could set it to a
URL that resolves to an internal service - a cloud metadata endpoint
(`169.254.169.254`), a database bound to `localhost`, an internal admin
panel on a private IP - instead of a real external website. The
architecture's own Website Enrichment section is explicit about this
threat: block localhost/private/link-local/metadata-endpoint addresses,
prevent DNS rebinding, validate redirects, cap response size, apply
strict timeouts, and rate-limit per domain.

## Decision

**Every crawl request goes through one function, `safe_get`**
(`worker.crawler.safety`), never a bare `httpx` call - `RobotsChecker` and
`crawl_site` both call only this function, so the safety checks below
apply uniformly to robots.txt fetches, redirect hops, and every candidate
page.

**Resolve-and-validate always runs first, unconditionally**, before
anything else happens with the URL. The hostname is resolved via
asyncio's own non-blocking resolver (`loop.getaddrinfo`); every resolved
address - not just the first - must be public, using Python's
`ipaddress` module to reject private, loopback, link-local (this is what
catches the cloud metadata endpoint), multicast, reserved, and
unspecified addresses, for both IPv4 and IPv6, including IPv4-mapped IPv6
(`::ffff:169.254.169.254` is unwrapped and checked as the IPv4 address it
actually represents). A hostname that resolves to *any* non-public
address is rejected outright, even if it also resolves to a public one.

**DNS rebinding is defended against by connecting to the literal
validated IP, never by hostname** - when no proxy is in play (see below),
the actual TCP connection targets the specific IP address that passed
validation, with the original hostname preserved only in the `Host`
header and TLS SNI extension. This closes the TOCTOU window a DNS
rebinding attack depends on: without this, a hostname that resolves to a
safe IP at check time could be re-resolved to an internal IP by the
connection layer moments later, and the check above would have been
meaningless.

**Proxy-aware connection strategy is a deliberate, documented exception to
the rule above.** This project's own dev sandbox enforces a mandatory
policy-enforcing `HTTPS_PROXY`/`HTTP_PROXY` that rejects a direct-IP
CONNECT tunnel outright (`403 Forbidden`), because an HTTP CONNECT proxy
fundamentally needs the real hostname to establish its tunnel - connecting
to a raw IP breaks that regardless of what the target actually is. When
`HTTP_PROXY`/`HTTPS_PROXY` is configured in the environment
(`_proxy_env_configured`), `safe_get` connects by the original hostname
through that proxy instead of by IP. The resolve-and-validate check above
still runs first and unconditionally in this configuration - only the
connection *strategy* changes, not whether the check happens - and the
operator-configured proxy is trusted to apply its own network-layer
egress controls for the connection itself, the same tradeoff any
HTTP-CONNECT-proxied service makes, since no client-side DNS pinning is
possible through a tunnel the client doesn't control. This mirrors a
common production deployment shape (a service behind a managed egress
proxy) as much as it describes this sandbox.

**Redirects are followed manually, one hop at a time**, with the exact
same scheme/resolve/validate checks re-applied to every redirect target -
`httpx`'s built-in redirect following is deliberately not used
(`follow_redirects=False`), since letting the HTTP client itself follow a
redirect would skip these checks on the second hop. A same-domain page
cannot be used to smuggle a redirect through an internal address, and
`MAX_REDIRECTS` (5) caps the chain length.

**The response body is streamed, not buffered, with a hard 5 MB cap
(`MAX_RESPONSE_BYTES`) enforced per chunk as it arrives** - a page (or a
deliberately hostile response) that would decompress or simply grow past
that size is aborted the moment it crosses the threshold, not after being
fully downloaded into memory first. Strict connect (5s) and read (10s)
timeouts bound how long any single request can hang.

**No cached HTTP client at module/instance scope** - the same ADR-0009
rule `GooglePlacesConnector` (ADR-0010) already had to apply: a fresh
`httpx.AsyncClient` is opened per `safe_get` call, since Celery's
per-task `asyncio.run()` pattern means a cached client bound to one
task's event loop would break (or silently misbehave) on the next task.

**The crawl itself is bounded, not a full-site crawl.** `crawl_site`
(`worker.crawler.fetcher`) only ever visits a fixed candidate path set -
homepage, `/contact`, `/contact-us`, `/about`, `/about-us`, `/booking`,
`/reservations`, `/order`, `/menu`, `/services` - capped at
`MAX_PAGES_PER_SITE` (6) pages, respecting `robots.txt` (fetched via the
same `safe_get`, defaulting to "everything allowed" if robots.txt itself
is unreachable - the conventional interpretation of an absent robots.txt)
and a per-domain minimum request interval (`MIN_SECONDS_BETWEEN_REQUESTS`,
1.5s, or robots.txt's own `Crawl-delay` if longer). Scheme/reachability
probing (`_probe_scheme`) fetches `/robots.txt` rather than the homepage
specifically so that (a) the very first request the crawler makes to a
site is never a real content page fetched before robots.txt has been
loaded and checked, and (b) the homepage isn't fetched twice (once to
probe, once as the first real candidate page).

**No authentication/CAPTCHA bypass, no JavaScript execution.** The
crawler is a plain HTTP GET client - there is no code path that submits
credentials, solves a challenge, or executes page scripts, satisfying the
architecture's explicit prohibition directly by omission rather than by
an added check.

## Consequences
- `apps/worker/worker/crawler/` (`safety.py`, `robots.py`, `fetcher.py`,
  `detectors.py`) and `apps/worker/worker/enrichment_tasks.py` are new;
  `queue.enrichment` is a new, separate Celery queue from `queue.search`
  so a backlog of (slower) enrichment crawls can never starve (faster)
  campaign search-page processing.
- **The SSRF-blocking logic itself is verified against real DNS
  resolution**, not mocked - `tests/test_crawler_safety.py` calls
  `safe_get` against real blocked targets (`127.0.0.1`, `localhost`,
  `169.254.169.254`, a private `10.x` address, `file://`, `ftp://`) with
  no transport override, so these tests exercise the genuine
  `loop.getaddrinfo` resolution and `ipaddress`-based validation path, not
  a stand-in for it.
- **Fetch mechanics (redirects, size cap, status handling) and the full
  bounded-crawl orchestration are verified via `httpx.MockTransport`**
  against `example.com` used purely as a DNS target (it genuinely
  resolves to a public IP, satisfying the resolve-and-validate check,
  which still runs even with a mock transport injected) - no real request
  to `example.com` or any other host is ever made in these tests, since
  the mock transport intercepts every request regardless of hostname.
- **A live crawl of a real external website has not been exercised in
  this sandbox**, for the same reason ADR-0010 documents for the Google
  Places connector: this project's dev sandbox enforces an
  allowlist-based egress proxy that rejects general internet access
  outright (confirmed via direct testing - both a raw HTTPS request to a
  real domain and the direct-IP-connect strategy this crawler's own
  no-proxy code path uses were rejected by the proxy with policy-level
  403s). Per the proxy's own operating instructions, this is a policy
  denial to report and design around, not to retry or bypass - the
  proxy-aware branching this ADR documents above is that design response,
  not a workaround of it.
- Before relying on this crawler against real business websites in
  production, it should be smoke-tested against a small set of real,
  known-safe external sites from an environment without this sandbox's
  restrictive egress policy - the mocked tests prove this module's own
  logic (URL validation, redirect handling, detector extraction) is
  correct against the HTTP contract it's written against, but, exactly as
  with ADR-0010's connector, that is not the same claim as "this has
  succeeded against real websites' actual, sometimes-idiosyncratic
  behavior" (redirect chains through CDNs, unusual robots.txt syntax,
  non-UTF-8 encodings, slow servers near the timeout boundary).
- The whole-crawl "missing X" signals (`missing_whatsapp`,
  `missing_online_booking`, `missing_online_ordering`,
  `missing_contact_method`) are computed by `worker.enrichment_tasks`, not
  by any individual detector in `worker.crawler.detectors` - see that
  module's own docstring - and are only ever recorded when the site was
  genuinely reachable and its candidate pages actually checked; an
  unreachable site gets `website_unavailable` instead of five separate
  claims about content nobody saw.
