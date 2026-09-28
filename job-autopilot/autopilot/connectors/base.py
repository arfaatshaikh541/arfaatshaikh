"""Connector base types and a polite HTTP client."""
from __future__ import annotations

import datetime as dt
import html
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

from ..lifecycle import sleep
from ..ratelimit import penalize, relax, wait_for_slot

USER_AGENT = "JobAutopilot/0.1 (candidate-operated job search; respects rate limits)"


class ConnectorError(Exception):
    pass


class TransientError(ConnectorError):
    """Network/5xx/429 - safe to retry later."""


class PermanentError(ConnectorError):
    """404, bad board token, schema change - do not retry blindly."""


@dataclass
class NormalizedJob:
    platform: str
    board: str
    external_id: str
    url: str
    apply_url: str | None
    apply_method: str
    title: str
    company: str | None = None
    location: str | None = None
    workplace_type: str | None = None  # None = UNKNOWN
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_interval: str | None = None
    salary_text: str | None = None
    description_text: str | None = None
    published_at: dt.datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def html_to_text(s: str | None) -> str | None:
    if not s:
        return None
    s = html.unescape(s)  # Greenhouse double-encodes content
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>|</div>", "\n", s)
    s = re.sub(r"(?i)<li[^>]*>", "\n• ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s.strip()


def parse_iso(v: Any) -> dt.datetime | None:
    if not v:
        return None
    if isinstance(v, (int, float)):
        return dt.datetime.fromtimestamp(v / 1000 if v > 1e11 else v, dt.timezone.utc)
    try:
        d = dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


class PoliteClient:
    def __init__(self, min_interval_s: float = 3.0, max_attempts: int = 4, timeout: float = 30.0):
        self.min_interval_s = min_interval_s
        self.max_attempts = max_attempts
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=timeout, follow_redirects=True
        )

    def get_json(self, url: str, params: dict | None = None) -> Any:
        host = urlparse(url).hostname or url
        last: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            wait_for_slot(f"host:{host}", self.min_interval_s)
            try:
                r = self.client.get(url, params=params)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last = TransientError(f"{type(e).__name__} fetching {url}")
                penalize(f"host:{host}")
                sleep(min(30, 2**attempt))
                continue
            if r.status_code == 200:
                relax(f"host:{host}")
                try:
                    return r.json()
                except ValueError as e:
                    raise PermanentError(f"Non-JSON response from {url}") from e
            if r.status_code in (429, 500, 502, 503, 504):
                ra = r.headers.get("retry-after")
                penalize(f"host:{host}", float(ra) if ra and ra.isdigit() else None)
                last = TransientError(f"HTTP {r.status_code} from {url}")
                sleep(min(30, 2**attempt))
                continue
            if r.status_code in (401, 403):
                raise PermanentError(f"HTTP {r.status_code} (access denied) from {url}")
            if r.status_code == 404:
                raise PermanentError(f"HTTP 404: board/company not found at {url}")
            raise PermanentError(f"HTTP {r.status_code} from {url}")
        raise last or TransientError(f"Failed to fetch {url}")

    def close(self) -> None:
        self.client.close()


class DiscoveryConnector:
    key: str = ""

    def __init__(self, client: PoliteClient):
        self.http = client

    def fetch(self, identifier: str, options: dict[str, Any]) -> list[NormalizedJob]:
        raise NotImplementedError
