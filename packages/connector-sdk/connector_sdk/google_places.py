"""GOOGLE PLACES CONNECTOR (Milestone 3) - a real integration against the
Google Places API (New): https://places.googleapis.com/v1/.

Design notes:

- **No cached HTTP client.** `GooglePlacesConnector` instances live as
  module-level singletons in `connector_sdk.registry`, and the worker's
  Celery tasks each run in a fresh `asyncio.run(...)` event loop (see
  ADR-0009). `httpx.AsyncClient` connections are bound to the loop that
  created them, exactly like asyncpg/redis-py - so this connector opens a
  brand new `httpx.AsyncClient` per request instead of holding one at
  instance scope, to avoid reintroducing the same class of bug ADR-0009
  already fixed once for the DB/Redis clients.
- **Statelessness across pages.** `SearchQuery.cursor`/`SearchPage.next_cursor`
  are the *only* state carried between one page and the next (each page is
  a separate Celery task - see `worker.campaign_tasks` - possibly running
  in a different worker process entirely). Google's own `nextPageToken` is
  opaque and says nothing about how many results have been returned so
  far, but the worker relies entirely on `SearchPage.has_more` to decide
  whether to keep paging, with no independent cap-tracking of its own
  (see `MockConnector.search`, which has the identical contract). So this
  connector's cursor is `"{count_so_far}:{google_page_token}"` - carrying
  both pieces of state through the one channel that survives between
  tasks.
- **Page-token activation delay.** Google's docs note a short delay
  before a freshly issued `nextPageToken` becomes valid. Rather than
  sleeping, a page-token-related `INVALID_ARGUMENT` response is mapped to
  `ConnectorTransientError` (retryable) instead of `ConnectorPermanentError` -
  Celery's existing 5-60s retry backoff comfortably covers Google's stated
  activation delay, and a *genuinely* expired/invalid token will keep
  failing until `max_retries`, which is the correct outcome for a token
  that is truly gone.
- **Minimal field masks.** Only the fields this connector's normalization
  actually reads are requested (`X-Goog-FieldMask`) - Google's API bills
  by requested field/SKU, so requesting everything by default is wasteful
  and was deliberately avoided.

Live-network behavior in this module has been reasoned through against
Google's documented Places API (New) contract, but has not been exercised
against the real API in this environment - no Google Cloud API key was
available during implementation. Verification here is via
`tests/test_google_places.py`, which mocks the HTTP transport with
response bodies shaped exactly like Google's documented API (success,
pagination, every error class this module maps, and missing-optional-field
cases) - this is a real gap until a key is supplied and a live smoke test
is run; see docs/adr/0010 and docs/project-status.md.
"""

import logging
import os
from datetime import UTC, datetime

import httpx

from connector_sdk.base import BaseConnector
from connector_sdk.errors import (
    ConnectorAuthError,
    ConnectorPermanentError,
    ConnectorQuotaError,
    ConnectorRateLimitError,
    ConnectorTransientError,
)
from connector_sdk.types import BusinessRecord, SearchPage, SearchQuery

logger = logging.getLogger("connector_sdk.google_places")

BASE_URL = "https://places.googleapis.com/v1"

# Only the fields this connector's normalization (`_business_from_place`)
# actually reads - see the field-mask cost note above.
_PLACE_FIELDS = (
    "id",
    "displayName",
    "formattedAddress",
    "addressComponents",
    "location",
    "rating",
    "userRatingCount",
    "nationalPhoneNumber",
    "internationalPhoneNumber",
    "websiteUri",
    "googleMapsUri",
    "businessStatus",
    "types",
)
TEXT_SEARCH_FIELD_MASK = ",".join(f"places.{f}" for f in _PLACE_FIELDS) + ",nextPageToken"
NEARBY_SEARCH_FIELD_MASK = ",".join(f"places.{f}" for f in _PLACE_FIELDS) + ",nextPageToken"
PLACE_DETAILS_FIELD_MASK = ",".join(_PLACE_FIELDS)

# Google Places API (New) caps Text/Nearby Search pages at 20 results.
_MAX_PAGE_SIZE = 20

_ADDRESS_COMPONENT_TYPE_TO_FIELD = {
    "country": "country",
    "administrative_area_level_1": "region",
    "locality": "city",
    "sublocality": "area",
    "neighborhood": "area",
}


class GooglePlacesConnector(BaseConnector):
    connector_id = "google_places"
    source_type = "google_places"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        http_timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        # Read lazily from the environment rather than at import/registry-
        # construction time, so a process with no key configured yet can
        # still start up - the error only surfaces when this connector is
        # actually invoked (`_require_api_key`), exactly like every other
        # ConnectorAuthError case.
        self._api_key = api_key if api_key is not None else os.environ.get("GOOGLE_PLACES_API_KEY")
        self._timeout = http_timeout_seconds
        # None in production (a real network transport); tests inject an
        # `httpx.MockTransport` here to exercise this connector's request
        # construction and response parsing without a real API key or a
        # real network call - see tests/test_google_places.py.
        self._transport = transport
        self.api_calls_made = 0  # Milestone 3's "API usage measurement" requirement.

    def _require_api_key(self) -> str:
        if not self._api_key:
            raise ConnectorAuthError(
                "GOOGLE_PLACES_API_KEY is not configured - the google_places connector "
                "cannot be used without a real Google Cloud API key with the Places API "
                "(New) enabled."
            )
        return self._api_key

    async def _request(
        self, method: str, path: str, *, field_mask: str, json_body: dict | None = None
    ) -> dict:
        api_key = self._require_api_key()
        headers = {
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": field_mask,
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.request(
                    method, f"{BASE_URL}{path}", headers=headers, json=json_body
                )
        except httpx.TimeoutException as exc:
            raise ConnectorTransientError(f"Google Places request timed out: {exc}") from exc
        except httpx.TransportError as exc:
            raise ConnectorTransientError(f"Google Places request failed: {exc}") from exc

        self.api_calls_made += 1
        logger.info(
            "google_places_api_call path=%s status_code=%s calls_made=%s",
            path,
            response.status_code,
            self.api_calls_made,
        )

        body: dict = response.json() if response.content else {}
        if response.status_code >= 400:
            had_page_token = bool(json_body and json_body.get("pageToken"))
            self._raise_for_google_error(response.status_code, body, had_page_token=had_page_token)
        return body

    @staticmethod
    def _raise_for_google_error(status_code: int, body: dict, *, had_page_token: bool) -> None:
        error = body.get("error", {}) if isinstance(body, dict) else {}
        message = str(error.get("message", "unknown error"))
        google_status = error.get("status", "")

        if status_code == 401 or google_status == "UNAUTHENTICATED":
            raise ConnectorAuthError(f"Google Places authentication failed: {message}")
        if status_code == 403 or google_status == "PERMISSION_DENIED":
            raise ConnectorAuthError(f"Google Places access denied: {message}")
        if status_code == 429 or google_status == "RESOURCE_EXHAUSTED":
            if "quota" in message.lower():
                raise ConnectorQuotaError(f"Google Places quota exhausted: {message}")
            raise ConnectorRateLimitError(f"Google Places rate-limited this request: {message}")
        if status_code == 400 or google_status == "INVALID_ARGUMENT":
            if had_page_token:
                raise ConnectorTransientError(f"Google Places rejected the page token: {message}")
            raise ConnectorPermanentError(f"Google Places rejected the query: {message}")
        if status_code >= 500:
            raise ConnectorTransientError(f"Google Places server error ({status_code}): {message}")
        raise ConnectorPermanentError(f"Unexpected Google Places error ({status_code}): {message}")

    async def estimate_cost(self, query: SearchQuery) -> float:
        # Google Places has no cheap way to learn the total match count
        # without paging through results, so - like MockConnector - this
        # prices 1 credit per requested result; `run_campaign_task`
        # reconciles the reservation to the *actual* number of businesses
        # found once the campaign finishes (see ADR-0004).
        return float(query.result_limit)

    async def health_check(self) -> bool:
        try:
            await self.search(
                SearchQuery(
                    industry="cafe",
                    country="United States",
                    city="Seattle",
                    result_limit=1,
                    page_size=1,
                )
            )
        except ConnectorAuthError:
            return False
        except (ConnectorRateLimitError, ConnectorQuotaError, ConnectorTransientError):
            # The API is reachable and authenticated but temporarily
            # unable to serve - still "unhealthy" from a caller's
            # perspective right now.
            return False
        return True

    def _build_text_query(self, query: SearchQuery) -> str:
        subject = query.category or query.industry
        location_parts = [p for p in (query.area, query.city, query.region, query.country) if p]
        return f"{subject} in {', '.join(location_parts)}"

    async def search(self, query: SearchQuery) -> SearchPage:
        count_so_far = 0
        google_page_token: str | None = None
        if query.cursor:
            count_str, _, token = query.cursor.partition(":")
            count_so_far = int(count_str)
            google_page_token = token or None

        page_size = min(query.page_size, _MAX_PAGE_SIZE)
        body: dict = {"textQuery": self._build_text_query(query), "pageSize": page_size}
        if query.min_rating is not None:
            body["minRating"] = query.min_rating
        if google_page_token:
            body["pageToken"] = google_page_token

        response = await self._request(
            "POST", "/places:searchText", field_mask=TEXT_SEARCH_FIELD_MASK, json_body=body
        )

        places = response.get("places", [])
        businesses = [self._business_from_place(p) for p in places]
        businesses = self._apply_client_side_filters(businesses, query)

        remaining_capacity = max(0, query.result_limit - count_so_far)
        truncated = businesses[:remaining_capacity]
        new_count_so_far = count_so_far + len(truncated)

        google_next_token = response.get("nextPageToken")
        has_more = new_count_so_far < query.result_limit and bool(google_next_token)
        next_cursor = f"{new_count_so_far}:{google_next_token}" if has_more else None

        return SearchPage(
            businesses=truncated,
            next_cursor=next_cursor,
            has_more=has_more,
            page_number=int(count_so_far / max(page_size, 1)),
        )

    def _apply_client_side_filters(
        self, businesses: list[BusinessRecord], query: SearchQuery
    ) -> list[BusinessRecord]:
        # Google's Text Search doesn't support "must have a phone number"
        # or "must/must not have a website" as request parameters, so
        # these two filters (unlike minRating, sent to Google directly
        # above) are applied client-side against the real, already-
        # returned records - never by inventing or removing data.
        result = businesses
        if query.must_have_phone:
            result = [b for b in result if b.phone]
        if query.website_requirement == "required":
            result = [b for b in result if b.website]
        elif query.website_requirement == "missing":
            result = [b for b in result if not b.website]
        if query.min_reviews is not None:
            result = [b for b in result if (b.review_count or 0) >= query.min_reviews]
        return result

    async def get_place_details(self, place_id: str) -> BusinessRecord:
        """Real Place Details support (Milestone 3 scope). Not called for
        every Text Search result by default - Text Search's own response,
        with this connector's field mask, already carries every field
        `BusinessRecord` needs, so hydrating each result with a second,
        billed Place Details call per business would be pure quota waste.
        This method exists for future callers that need to refresh a
        single already-known place (e.g. a "refresh this lead" action)."""
        response = await self._request(
            "GET", f"/places/{place_id}", field_mask=PLACE_DETAILS_FIELD_MASK
        )
        return self._business_from_place(response)

    async def search_nearby(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_meters: float,
        included_type: str | None = None,
        page_size: int = 20,
        cursor: str | None = None,
    ) -> SearchPage:
        """Real Nearby Search support ("where justified" per the
        architecture). `SearchQuery` (and therefore `Campaign`/
        `CampaignFilter`) has no latitude/longitude fields yet - campaigns
        are defined by text location filters (country/region/city/area),
        which is what Text Search matches directly - so this is not the
        connector's primary `search()` path. It's a real, working
        capability for a future milestone that adds coordinate-based
        campaign filters, not the one exercised by the current task
        chain."""
        body: dict = {
            "maxResultCount": min(page_size, _MAX_PAGE_SIZE),
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": radius_meters,
                }
            },
        }
        if included_type:
            body["includedTypes"] = [included_type]
        if cursor:
            body["pageToken"] = cursor

        response = await self._request(
            "POST", "/places:searchNearby", field_mask=NEARBY_SEARCH_FIELD_MASK, json_body=body
        )
        places = response.get("places", [])
        businesses = [self._business_from_place(p) for p in places]
        next_token = response.get("nextPageToken")
        return SearchPage(
            businesses=businesses, next_cursor=next_token, has_more=bool(next_token), page_number=0
        )

    def _business_from_place(self, place: dict) -> BusinessRecord:
        place_id = place["id"]
        display_name = place.get("displayName", {}).get("text")
        # `name` is non-optional on BusinessRecord, but a real Google
        # result is never given a made-up name if Google's own response
        # is missing one for some reason - the source's own stable ID is
        # used as a fallback label instead of fabricating a plausible one.
        name = display_name or f"Google Place {place_id}"

        location = place.get("location", {})
        types = place.get("types") or []
        category = types[0] if types else None

        address_fields = self._parse_address_components(place.get("addressComponents", []))

        business_status = place.get("businessStatus")
        google_maps_url = place.get("googleMapsUri")

        return BusinessRecord(
            source="google_places",
            source_native_id=place_id,
            name=name,
            category=category,
            address=place.get("formattedAddress"),
            country=address_fields.get("country"),
            region=address_fields.get("region"),
            city=address_fields.get("city"),
            area=address_fields.get("area"),
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            phone=place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber"),
            website=place.get("websiteUri"),
            google_maps_url=google_maps_url,
            rating=place.get("rating"),
            review_count=place.get("userRatingCount"),
            business_status=business_status.lower() if business_status else None,
            source_url=google_maps_url,
            collected_at=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def _parse_address_components(components: list[dict]) -> dict[str, str]:
        result: dict[str, str] = {}
        for component in components:
            for raw_type in component.get("types", []):
                field = _ADDRESS_COMPONENT_TYPE_TO_FIELD.get(raw_type)
                if field and field not in result:
                    text = component.get("longText") or component.get("long_name")
                    if text:
                        result[field] = text
        return result
