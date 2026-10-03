"""Safe source probes: can this environment reach a source, its licence page, its terms and its data, and may we fetch it automatically?

A probe only ever sends GET/HEAD requests to the URLs a target names, identifies itself, honours robots.txt for the data URL and never
sends credentials. It records what happened (DNS, TLS, HTTP status, redirects, proxy refusals) and nothing else. A reachable source is
NOT a licensed one: `rights_note` always says so, and the registry/manifest decide rights, never the probe.
"""
from __future__ import annotations

import socket
import ssl
import time
import urllib.error
import urllib.request
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from urllib.parse import urlsplit

USER_AGENT = "WorldOfIslam-source-probe/1.0 (+https://app.arfaat.com/worldofislam)"
RIGHTS_NOTE = "Reachability is not permission: licence, terms and provenance must still be read and recorded before any import."


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def dns_check(host: str) -> dict:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return {"ok": True, "addresses": sorted({i[4][0] for i in infos})[:4]}
    except OSError as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}


def http_check(url: str, *, method: str = "GET", timeout: float = 20, max_bytes: int = 2048) -> dict:
    """One request. Never raises: the outcome, including a proxy refusal, is the result."""
    started = time.monotonic()
    request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            body = response.read(max_bytes) if method == "GET" else b""
            return {"url": url, "reachable": True, "status": response.status, "final_url": response.geturl(), "content_type": response.headers.get("Content-Type"),
                    "bytes_read": len(body), "ms": int((time.monotonic() - started) * 1000), "tls": url.startswith("https://"), "error": None}
    except urllib.error.HTTPError as exc:
        # The server answered: DNS, TLS and routing worked, even though the answer is an error status.
        return {"url": url, "reachable": True, "status": exc.code, "final_url": url, "content_type": exc.headers.get("Content-Type") if exc.headers else None,
                "bytes_read": 0, "ms": int((time.monotonic() - started) * 1000), "tls": url.startswith("https://"), "error": f"HTTP {exc.code} {exc.reason}"}
    except (urllib.error.URLError, OSError, ssl.SSLError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        kind = "proxy_or_policy_refusal" if "Tunnel connection failed" in str(reason) else "tls_error" if isinstance(reason, ssl.SSLError) else "network_error"
        return {"url": url, "reachable": False, "status": None, "final_url": None, "content_type": None, "bytes_read": 0, "ms": int((time.monotonic() - started) * 1000),
                "tls": None, "error": f"{kind}: {reason}"[:240]}


def robots_allows(url: str, timeout: float = 15) -> dict:
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        request = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read(200_000).decode("utf-8", "replace")
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(text.splitlines())
        return {"checked": True, "allowed": parser.can_fetch(USER_AGENT, url), "robots_url": robots_url}
    except urllib.error.HTTPError as exc:
        # No robots.txt (404) means no restriction was published; any other status is recorded as unknown.
        return {"checked": True, "allowed": True if exc.code == 404 else None, "robots_url": robots_url, "note": f"HTTP {exc.code}"}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"checked": False, "allowed": None, "robots_url": robots_url, "note": f"{type(exc).__name__}"}


def probe_target(target: dict) -> dict:
    """target: {source_id, domain, urls: {main, licence, terms, data}, importer?}. Returns one record in the schema the reports use."""
    urls = {k: v for k, v in (target.get("urls") or {}).items() if v}
    host = urlsplit(urls.get("main") or next(iter(urls.values()))).hostname or ""
    results = {name: http_check(url) for name, url in urls.items()}
    robots = robots_allows(urls["data"]) if urls.get("data") else {"checked": False, "allowed": None, "note": "no data URL"}

    def ok(name: str) -> bool:
        r = results.get(name)
        return bool(r and r["reachable"] and r["status"] is not None and r["status"] < 400)

    return {
        "source_id": target["source_id"], "domain": target.get("domain"), "host": host, "last_checked": _now(),
        "dns": dns_check(host) if host else {"ok": False, "error": "no host"},
        "accessible": ok("main"), "licence_page_accessible": ok("licence") if "licence" in urls else None,
        "terms_accessible": ok("terms") if "terms" in urls else None, "data_accessible": ok("data") if "data" in urls else None,
        "robots": robots, "importer_available": target.get("importer"), "requests": results, "rights_note": RIGHTS_NOTE,
    }


def probe_all(targets: list[dict], workers: int = 8) -> list[dict]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(probe_target, targets))


def summarise(records: list[dict]) -> dict:
    return {"total": len(records), "accessible": sum(1 for r in records if r["accessible"]), "data_accessible": sum(1 for r in records if r["data_accessible"]),
            "blocked_or_unreachable": [r["source_id"] for r in records if not r["accessible"]]}
