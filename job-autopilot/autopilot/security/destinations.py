"""Environment separation for outbound browser destinations (also SSRF protection).

* production : only public internet hosts. Loopback, private, link-local and reserved
               addresses are refused, so the browser can never be pointed at internal services.
* development / test : only loopback/private hosts (local fixtures). A dev or test
               deployment therefore can never reach, let alone submit to, a real employer site.
               LIVE mode is refused in development; in test it runs only against fixtures.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from ..config import get_config


class DestinationRefused(Exception):
    pass


def _addresses(host: str) -> list[ipaddress._BaseAddress]:
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise DestinationRefused(f"Cannot resolve {host}: {e}") from e
    return [ipaddress.ip_address(i[4][0].split("%")[0]) for i in infos]


def _is_public(a: ipaddress._BaseAddress) -> bool:
    return a.is_global and not (a.is_private or a.is_loopback or a.is_link_local or a.is_reserved or a.is_multicast)


def check_destination(url: str, environment: str | None = None) -> None:
    env = (environment or get_config().environment).lower()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise DestinationRefused(f"Refused non-http(s) destination {url[:80]!r}")
    if env == "production" and parts.scheme != "https":
        raise DestinationRefused("Production destinations must use https")
    addrs = _addresses(parts.hostname)
    if env == "production":
        bad = [str(a) for a in addrs if not _is_public(a)]
        if bad:
            raise DestinationRefused(f"{parts.hostname} resolves to non-public address(es) {bad}; refused in production")
    else:
        pub = [str(a) for a in addrs if _is_public(a)]
        if pub:
            raise DestinationRefused(
                f"{parts.hostname} is a public host; {env} environments may only reach local test fixtures")


def live_submissions_allowed() -> bool:
    """production: real submissions (public hosts only). test: the LIVE code path may run, but
    check_destination confines it to local fixtures. development: LIVE is refused outright."""
    return get_config().environment.lower() in ("production", "test")
