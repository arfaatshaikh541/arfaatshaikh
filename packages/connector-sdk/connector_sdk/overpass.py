"""OVERPASS CONNECTOR (Milestone 20) - a real integration against the
public Overpass API (https://overpass-api.de/api/interpreter), the
standard read-only query service for OpenStreetMap data.

Why this exists: every other real-data connector in this codebase
(`GooglePlacesConnector`) needs a paid, credentialed API key. Overpass
needs none - no signup, no card on file, no quota to exhaust - at the
cost of a smaller, community-maintained dataset with real gaps (no
ratings/reviews at all, inconsistent phone/website coverage, and address
tagging that varies a lot by region).

Design notes, mirroring `google_places.py`'s own documented tradeoffs:

- **No cached HTTP client** - same per-task event-loop isolation rule as
  every other connector (ADR-0009): a fresh `httpx.AsyncClient` per
  request, never one held at instance scope.
- **No server-side pagination.** Unlike Google's opaque `nextPageToken`,
  Overpass has no pagination concept at all - a query just returns every
  matching element. This connector re-runs the *same* deterministic query
  on every `search()` call (one per page, exactly like `MockConnector`'s
  own "recompute deterministically, slice by page" contract) and slices
  the page out of the freshly-fetched result list. The cost: a multi-page
  campaign re-queries Overpass once per page instead of once total - a
  real inefficiency, accepted here because it keeps the connector fully
  stateless (no per-query result cache to invalidate or leak across
  tenants) and Overpass's own queries for a single city+category are
  typically fast.
- **No rating/review data, ever.** OSM's schema has no equivalent field.
  `supports_rating_filter = False` makes campaign creation reject
  `min_rating`/`min_reviews` outright for this source (see
  `campaigns.services.create_campaign`) rather than silently accepting
  and ignoring them.
- **A fixed industry -> OSM tag mapping** (`INDUSTRY_TAG_MAP`). OSM has no
  free-text "industry" field - every real-world category is one specific
  tag=value pair (`amenity=restaurant`, `shop=car_repair`, ...). An
  industry string not in this table raises `ConnectorPermanentError`
  rather than silently returning zero (wrong-looking) or misapplied
  (wrong-feeling) results.

Live-network behavior in this module has been reasoned through against
Overpass's documented QL syntax and real-world JSON response shape, but
has not been exercised against the real public API in this environment -
this sandbox's egress proxy rejects every Overpass/OpenStreetMap host
tried (`overpass-api.de`, `overpass.kumi.systems`, `nominatim.
openstreetmap.org`) with a policy-level 403, the same class of
restriction the website crawler and Stripe already carry. Verification
here is via `tests/test_overpass.py`, which mocks the HTTP transport with
response bodies shaped exactly like Overpass's real JSON output - this is
a real, disclosed gap until this connector is exercised from an
environment with unrestricted egress; see docs/adr/0028 and
docs/project-status.md.
"""

import logging
import os
from datetime import UTC, datetime

import httpx

from connector_sdk.base import BaseConnector
from connector_sdk.errors import (
    ConnectorPermanentError,
    ConnectorRateLimitError,
    ConnectorTransientError,
)
from connector_sdk.types import BusinessRecord, SearchPage, SearchQuery

logger = logging.getLogger("connector_sdk.overpass")

DEFAULT_BASE_URL = "https://overpass-api.de/api/interpreter"

# A deliberately non-exhaustive mapping covering common lead-generation
# categories. Case-insensitive lookup against `query.category or
# query.industry` (category preferred when present, same precedence
# `GooglePlacesConnector._build_text_query` uses) - not a fabricated
# guess for anything not listed here; see the module docstring.
INDUSTRY_TAG_MAP: dict[str, tuple[str, str]] = {
    "restaurants": ("amenity", "restaurant"),
    "restaurant": ("amenity", "restaurant"),
    "cafes": ("amenity", "cafe"),
    "cafe": ("amenity", "cafe"),
    "coffee": ("amenity", "cafe"),
    "bars": ("amenity", "bar"),
    "pubs": ("amenity", "pub"),
    "bakeries": ("shop", "bakery"),
    "bakery": ("shop", "bakery"),
    "hotels": ("tourism", "hotel"),
    "accommodation": ("tourism", "hotel"),
    "auto repair": ("shop", "car_repair"),
    "car repair": ("shop", "car_repair"),
    "car wash": ("shop", "car_wash"),
    "hair salons": ("shop", "hairdresser"),
    "hairdressers": ("shop", "hairdresser"),
    "barbers": ("shop", "hairdresser"),
    "spas": ("shop", "beauty"),
    "beauty salons": ("shop", "beauty"),
    "gyms": ("leisure", "fitness_centre"),
    "fitness": ("leisure", "fitness_centre"),
    "pharmacies": ("amenity", "pharmacy"),
    "pharmacy": ("amenity", "pharmacy"),
    "supermarkets": ("shop", "supermarket"),
    "grocery": ("shop", "supermarket"),
    "clothing stores": ("shop", "clothes"),
    "clothing": ("shop", "clothes"),
    "banks": ("amenity", "bank"),
    "dentists": ("amenity", "dentist"),
    "doctors": ("amenity", "doctors"),
    "clinics": ("amenity", "clinic"),
    "veterinary": ("amenity", "veterinary"),
    "laundries": ("shop", "laundry"),
    "dry cleaners": ("shop", "dry_cleaning"),
    "real estate": ("office", "estate_agent"),
    "electronics stores": ("shop", "electronics"),
    "furniture stores": ("shop", "furniture"),
    "bookstores": ("shop", "books"),
}

# A small, defensive buffer above `result_limit` so pagination has real
# data to slice into pages without a second network round-trip inside a
# single `search()` call - never a substitute for `result_limit` itself.
_FETCH_BUFFER = 50


class OverpassConnector(BaseConnector):
    connector_id = "osm"
    source_type = "osm"
    # OSM has no rating/review schema at all - see the module docstring.
    supports_rating_filter = False

    def __init__(
        self,
        *,
        base_url: str | None = None,
        http_timeout_seconds: float = 25.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url or os.environ.get("OVERPASS_API_URL", DEFAULT_BASE_URL)
        self._timeout = http_timeout_seconds
        # None in production (a real network transport); tests inject an
        # `httpx.MockTransport` here - see tests/test_overpass.py.
        self._transport = transport
        self.api_calls_made = 0

    @staticmethod
    def _resolve_tag(query: SearchQuery) -> tuple[str, str]:
        subject = (query.category or query.industry).strip().lower()
        tag = INDUSTRY_TAG_MAP.get(subject)
        if tag is None:
            raise ConnectorPermanentError(
                f"The OpenStreetMap connector has no tag mapping for industry/category "
                f"{subject!r}. Supported values: {sorted(INDUSTRY_TAG_MAP)}."
            )
        return tag

    @staticmethod
    def _build_query(query: SearchQuery, tag_key: str, tag_value: str, *, limit: int) -> str:
        area_clauses = ""
        if query.country:
            area_clauses += (
                f'area["name"="{query.country}"]["admin_level"="2"]->.country;\n'
                f'area["name"="{query.city}"](area.country)->.searchArea;\n'
            )
        else:
            area_clauses += f'area["name"="{query.city}"]->.searchArea;\n'

        return (
            "[out:json][timeout:25];\n"
            f"{area_clauses}"
            "(\n"
            f'  node["{tag_key}"="{tag_value}"](area.searchArea);\n'
            f'  way["{tag_key}"="{tag_value}"](area.searchArea);\n'
            ");\n"
            f"out center {limit};\n"
        )

    async def _fetch_all(self, query: SearchQuery) -> list[BusinessRecord]:
        tag_key, tag_value = self._resolve_tag(query)
        ql = self._build_query(query, tag_key, tag_value, limit=query.result_limit + _FETCH_BUFFER)

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(self._base_url, data={"data": ql})
        except httpx.TimeoutException as exc:
            raise ConnectorTransientError(f"Overpass request timed out: {exc}") from exc
        except httpx.TransportError as exc:
            raise ConnectorTransientError(f"Overpass request failed: {exc}") from exc

        self.api_calls_made += 1
        logger.info(
            "overpass_api_call tag=%s=%s status_code=%s calls_made=%s",
            tag_key,
            tag_value,
            response.status_code,
            self.api_calls_made,
        )

        if response.status_code == 429:
            raise ConnectorRateLimitError("Overpass rate-limited this request (429).")
        if response.status_code >= 500:
            raise ConnectorTransientError(f"Overpass server error ({response.status_code}).")
        if response.status_code >= 400:
            raise ConnectorPermanentError(
                f"Overpass rejected the query ({response.status_code}): {response.text[:200]}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            # Overpass sometimes returns an HTML error page (e.g. under
            # load) instead of JSON even with a 200 status - treat any
            # unparseable body as transient rather than silently
            # returning wrong/empty data.
            raise ConnectorTransientError(f"Overpass returned a non-JSON response: {exc}") from exc

        elements = body.get("elements", [])
        now = datetime.now(UTC).isoformat()
        return [
            self._business_from_element(el, tag_value, query, now)
            for el in elements
            if "tags" in el
        ]

    def _business_from_element(
        self, element: dict, category: str, query: SearchQuery, collected_at: str
    ) -> BusinessRecord:
        tags: dict = element.get("tags", {})
        element_type = element["type"]
        element_id = element["id"]
        source_native_id = f"{element_type}/{element_id}"

        name = tags.get("name") or f"OSM {element_type} {element_id}"

        if element_type == "node":
            latitude, longitude = element.get("lat"), element.get("lon")
        else:
            center = element.get("center", {})
            latitude, longitude = center.get("lat"), center.get("lon")

        address = None
        if tags.get("addr:housenumber") and tags.get("addr:street"):
            address = f"{tags['addr:housenumber']} {tags['addr:street']}"
        elif tags.get("addr:street"):
            address = tags["addr:street"]

        # A record with no `disused:`/`abandoned:` lifecycle-prefixed tag
        # is left with `business_status=None` (genuinely unknown) - OSM
        # doesn't reliably track operating status, so "operational" is
        # never assumed, only "known closed" when the data says so.
        business_status = None
        if any(k.startswith("disused:") or k.startswith("abandoned:") for k in tags):
            business_status = "closed_permanently"

        osm_url = f"https://www.openstreetmap.org/{element_type}/{element_id}"

        return BusinessRecord(
            source="osm",
            source_native_id=source_native_id,
            name=name,
            category=category,
            address=address,
            # OSM's own tags take priority; the queried country/city is a
            # defensible fallback only because the Overpass query itself
            # already scoped the search to that named administrative
            # area - never used for region/area, which the query does
            # not actually filter by (see the module docstring).
            country=tags.get("addr:country") or query.country,
            region=tags.get("addr:state"),
            city=tags.get("addr:city") or query.city,
            area=tags.get("addr:suburb") or tags.get("addr:neighbourhood"),
            latitude=latitude,
            longitude=longitude,
            phone=tags.get("phone") or tags.get("contact:phone"),
            website=tags.get("website") or tags.get("contact:website"),
            google_maps_url=osm_url,
            rating=None,
            review_count=None,
            business_status=business_status,
            source_url=osm_url,
            collected_at=collected_at,
        )

    def _apply_client_side_filters(
        self, businesses: list[BusinessRecord], query: SearchQuery
    ) -> list[BusinessRecord]:
        result = businesses
        if query.must_have_phone:
            result = [b for b in result if b.phone]
        if query.website_requirement == "required":
            result = [b for b in result if b.website]
        elif query.website_requirement == "missing":
            result = [b for b in result if not b.website]
        # Deliberately no min_rating/min_reviews filtering here - see
        # `supports_rating_filter = False` and the module docstring.
        return result

    async def estimate_cost(self, query: SearchQuery) -> float:
        return float(query.result_limit)

    async def search(self, query: SearchQuery) -> SearchPage:
        already_returned = int(query.cursor) if query.cursor else 0

        all_businesses = await self._fetch_all(query)
        all_businesses = self._apply_client_side_filters(all_businesses, query)

        remaining_capacity = max(0, query.result_limit - already_returned)
        remaining_available = max(0, len(all_businesses) - already_returned)
        count_this_page = min(query.page_size, remaining_capacity, remaining_available)
        page_businesses = all_businesses[already_returned : already_returned + count_this_page]

        new_count = already_returned + count_this_page
        has_more = (
            new_count < query.result_limit
            and new_count < len(all_businesses)
            and count_this_page == query.page_size
        )
        next_cursor = str(new_count) if has_more else None

        return SearchPage(
            businesses=page_businesses,
            next_cursor=next_cursor,
            has_more=has_more,
            page_number=already_returned // max(query.page_size, 1),
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    self._base_url, data={"data": "[out:json][timeout:5];node(1);out 1;"}
                )
        except (httpx.TimeoutException, httpx.TransportError):
            return False
        if response.status_code >= 400:
            return False
        try:
            response.json()
        except ValueError:
            return False
        return True
