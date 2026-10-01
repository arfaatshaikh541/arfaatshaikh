from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar


@dataclass
class FetchResult:
    """What was retrieved: kept in memory so a preview never writes anything."""
    version: str
    checksum: str
    payload: Any
    source_url: str
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    notes: dict = field(default_factory=dict)


@dataclass
class AdapterResult:
    rows: list[dict]
    skipped: dict
    stats: dict


class SourceAdapter:
    """Subclass and register in app/importers/registry.py. `fetch` and `build` are synchronous (they run in a worker thread)."""
    id: ClassVar[str]
    dataset_key: ClassVar[str]
    kind: ClassVar[str]                 # "listings" or "records"
    title: ClassVar[str]
    probe_urls: ClassVar[tuple[str, ...]]  # URLs that must answer for fetch() to work
    licence_summary: ClassVar[str]
    params_help: ClassVar[dict[str, str]] = {}
    max_rows: ClassVar[int] = 50000

    def fetch(self, params: dict) -> FetchResult:  # pragma: no cover - interface
        raise NotImplementedError

    def build(self, fetched: FetchResult, params: dict) -> AdapterResult:  # pragma: no cover - interface
        raise NotImplementedError

    def probe(self, timeout: float = 4.0) -> dict:
        """Can the build/production environment reach this source's hosts? Reported, never assumed."""
        results = {}
        for url in self.probe_urls:
            try:
                request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "WorldOfIslam-importer/1.0"})
                with urllib.request.urlopen(request, timeout=timeout) as response:  # honours the environment's proxy settings
                    results[url] = f"reachable (HTTP {response.status})"
            except urllib.error.HTTPError as exc:  # the host answered; a 4xx/5xx is still an answer, but a 403 may be a proxy refusal
                results[url] = f"answered HTTP {exc.code}"
            except Exception as exc:  # noqa: BLE001 - any failure to connect is the answer
                results[url] = f"unreachable ({exc.__class__.__name__})"
        ok = all(v.startswith("reachable") for v in results.values())
        return {"urls": results, "all_reachable": ok, "checked_at": datetime.now(UTC).isoformat()}

    def describe(self) -> dict:
        return {"id": self.id, "dataset": self.dataset_key, "kind": self.kind, "title": self.title, "probe_urls": list(self.probe_urls), "licence": self.licence_summary, "params": self.params_help}
