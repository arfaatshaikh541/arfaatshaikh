"""Mocked-adapter tests for GooglePlacesConnector (Milestone 3's own
explicit requirement, distinct from a live-API smoke test).

Every test injects an `httpx.MockTransport` shaped exactly like Google's
documented Places API (New) request/response contract, so these exercise
this connector's own request construction, response parsing, and error
mapping - without a real API key and without a real network call. This is
not the same thing as verifying against the live Google API; see the
module docstring in `connector_sdk/google_places.py` and
`docs/adr/0010-google-places-connector.md` for that gap.
"""

import httpx
import pytest
from connector_sdk.errors import (
    ConnectorAuthError,
    ConnectorPermanentError,
    ConnectorQuotaError,
    ConnectorRateLimitError,
    ConnectorTransientError,
)
from connector_sdk.google_places import GooglePlacesConnector
from connector_sdk.types import SearchQuery

pytestmark = pytest.mark.asyncio


def _connector(handler) -> GooglePlacesConnector:
    return GooglePlacesConnector(api_key="test-key", transport=httpx.MockTransport(handler))


def _place(
    place_id: str,
    name: str,
    *,
    rating: float | None = 4.5,
    review_count: int | None = 120,
    phone: str | None = "+1-206-555-0100",
    website: str | None = "https://example.com",
    business_status: str | None = "OPERATIONAL",
    address_components: list[dict] | None = None,
) -> dict:
    place: dict = {
        "id": place_id,
        "displayName": {"text": name, "languageCode": "en"},
        "formattedAddress": "123 Main St, Seattle, WA, USA",
        "location": {"latitude": 47.6, "longitude": -122.3},
        "types": ["cafe", "food"],
    }
    if rating is not None:
        place["rating"] = rating
    if review_count is not None:
        place["userRatingCount"] = review_count
    if phone is not None:
        place["nationalPhoneNumber"] = phone
    if website is not None:
        place["websiteUri"] = website
    if business_status is not None:
        place["businessStatus"] = business_status
    place["googleMapsUri"] = f"https://maps.google.com/?cid={place_id}"
    if address_components is not None:
        place["addressComponents"] = address_components
    return place


def _query(**overrides: object) -> SearchQuery:
    query = SearchQuery(
        industry="cafe", country="United States", city="Seattle", result_limit=40, page_size=20
    )
    for key, value in overrides.items():
        setattr(query, key, value)
    return query


async def test_text_search_success_maps_to_business_records():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/places:searchText"
        assert request.headers["X-Goog-Api-Key"] == "test-key"
        assert "places.displayName" in request.headers["X-Goog-FieldMask"]
        return httpx.Response(
            200,
            json={"places": [_place("place-1", "Golden Cafe"), _place("place-2", "Blue Diner")]},
        )

    connector = _connector(handler)
    page = await connector.search(_query())

    assert len(page.businesses) == 2
    first = page.businesses[0]
    assert first.source == "google_places"
    assert first.source_native_id == "place-1"
    assert first.name == "Golden Cafe"
    assert first.rating == 4.5
    assert first.review_count == 120
    assert first.phone == "+1-206-555-0100"
    assert first.website == "https://example.com"
    assert first.business_status == "operational"
    assert first.latitude == 47.6
    assert first.longitude == -122.3
    assert first.category == "cafe"
    assert connector.api_calls_made == 1


async def test_missing_optional_fields_are_none_not_fabricated():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "places": [
                    _place(
                        "place-3",
                        "No Frills Bakery",
                        rating=None,
                        review_count=None,
                        phone=None,
                        website=None,
                        business_status=None,
                    )
                ]
            },
        )

    connector = _connector(handler)
    page = await connector.search(_query())

    business = page.businesses[0]
    assert business.rating is None
    assert business.review_count is None
    assert business.phone is None
    assert business.website is None
    assert business.business_status is None
    # region/city/area are unresolvable without addressComponents in this
    # response - must be None, never guessed from the query's own filters.
    assert business.region is None
    assert business.city is None
    assert business.area is None


async def test_address_components_are_parsed_into_region_city_area():
    components = [
        {"longText": "United States", "types": ["country"]},
        {"longText": "Washington", "types": ["administrative_area_level_1"]},
        {"longText": "Seattle", "types": ["locality"]},
        {"longText": "Ballard", "types": ["neighborhood"]},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"places": [_place("place-4", "Ballard Coffee", address_components=components)]},
        )

    connector = _connector(handler)
    page = await connector.search(_query())
    business = page.businesses[0]
    assert business.country == "United States"
    assert business.region == "Washington"
    assert business.city == "Seattle"
    assert business.area == "Ballard"


async def test_pagination_cursor_encodes_running_count_and_google_token():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        body = request.content
        import json as _json

        payload = _json.loads(body)
        if call_count == 1:
            assert "pageToken" not in payload
            return httpx.Response(
                200,
                json={
                    "places": [_place(f"p{i}", f"Place {i}") for i in range(20)],
                    "nextPageToken": "google-token-abc",
                },
            )
        assert payload["pageToken"] == "google-token-abc"
        return httpx.Response(
            200, json={"places": [_place(f"p{i}", f"Place {i}") for i in range(20, 30)]}
        )

    connector = _connector(handler)
    query = _query(result_limit=25, page_size=20)
    first_page = await connector.search(query)

    assert len(first_page.businesses) == 20
    assert first_page.has_more is True
    assert first_page.next_cursor == "20:google-token-abc"

    second_query = _query(result_limit=25, page_size=20, cursor=first_page.next_cursor)
    second_page = await connector.search(second_query)

    # Only 5 more needed to reach result_limit=25, even though Google
    # returned 10 - truncated client-side, not requested from Google as a
    # smaller page (Google's own pageSize cap already governs the request).
    assert len(second_page.businesses) == 5
    assert second_page.has_more is False
    assert second_page.next_cursor is None


async def test_result_limit_reached_stops_paging_even_if_google_has_more():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "places": [_place(f"p{i}", f"Place {i}") for i in range(20)],
                "nextPageToken": "still-more-available",
            },
        )

    connector = _connector(handler)
    page = await connector.search(_query(result_limit=20, page_size=20))
    assert len(page.businesses) == 20
    assert page.has_more is False
    assert page.next_cursor is None


@pytest.mark.parametrize(
    "must_have_phone,website_requirement,expected_names",
    [
        (True, "any", ["Has Phone"]),
        (False, "required", ["Has Website"]),
        (False, "missing", ["Has Phone", "No Phone No Website"]),
    ],
)
async def test_client_side_filters_apply_to_real_returned_records(
    must_have_phone, website_requirement, expected_names
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "places": [
                    _place("p1", "Has Phone", phone="+1-555-0100", website=None),
                    _place("p2", "Has Website", phone=None, website="https://example.com"),
                    _place("p3", "No Phone No Website", phone=None, website=None),
                ]
            },
        )

    connector = _connector(handler)
    query = _query(must_have_phone=must_have_phone, website_requirement=website_requirement)
    page = await connector.search(query)
    assert [b.name for b in page.businesses] == expected_names


async def test_estimate_cost_returns_result_limit_without_a_network_call():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("estimate_cost must not make a network call")

    connector = _connector(handler)
    cost = await connector.estimate_cost(_query(result_limit=77))
    assert cost == 77.0
    assert connector.api_calls_made == 0


async def test_missing_api_key_only_raises_when_the_connector_is_invoked():
    # Constructing with no key configured must not raise - only calling
    # into the connector should.
    connector = GooglePlacesConnector(api_key=None)
    with pytest.raises(ConnectorAuthError):
        await connector.search(_query())


@pytest.mark.parametrize(
    "status_code,google_status,message,expected_error",
    [
        (401, "UNAUTHENTICATED", "API key not valid", ConnectorAuthError),
        (403, "PERMISSION_DENIED", "Places API (New) has not been enabled", ConnectorAuthError),
        (
            429,
            "RESOURCE_EXHAUSTED",
            "Too many requests, try again shortly",
            ConnectorRateLimitError,
        ),
        (429, "RESOURCE_EXHAUSTED", "Daily quota exceeded for this project", ConnectorQuotaError),
        (500, "INTERNAL", "Something went wrong server-side", ConnectorTransientError),
        (503, "UNAVAILABLE", "Service temporarily unavailable", ConnectorTransientError),
    ],
)
async def test_error_status_codes_map_to_the_right_connector_error(
    status_code, google_status, message, expected_error
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={"error": {"code": status_code, "status": google_status, "message": message}},
        )

    connector = _connector(handler)
    with pytest.raises(expected_error):
        await connector.search(_query())


async def test_invalid_argument_without_page_token_is_permanent():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": 400,
                    "status": "INVALID_ARGUMENT",
                    "message": "textQuery is required",
                }
            },
        )

    connector = _connector(handler)
    with pytest.raises(ConnectorPermanentError):
        await connector.search(_query(cursor=None))


async def test_invalid_argument_with_page_token_is_transient_not_permanent():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": 400,
                    "status": "INVALID_ARGUMENT",
                    "message": "The provided page token is invalid or expired",
                }
            },
        )

    connector = _connector(handler)
    with pytest.raises(ConnectorTransientError):
        await connector.search(_query(cursor="20:some-token"))


async def test_health_check_true_on_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"places": []})

    connector = _connector(handler)
    assert await connector.health_check() is True


async def test_health_check_false_on_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403, json={"error": {"code": 403, "status": "PERMISSION_DENIED", "message": "denied"}}
        )

    connector = _connector(handler)
    assert await connector.health_check() is False


async def test_get_place_details_uses_the_correct_endpoint_and_field_mask():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/places/place-99"
        assert "places." not in request.headers["X-Goog-FieldMask"]
        return httpx.Response(200, json=_place("place-99", "Detail Fetched Place"))

    connector = _connector(handler)
    business = await connector.get_place_details("place-99")
    assert business.source_native_id == "place-99"
    assert business.name == "Detail Fetched Place"


async def test_search_nearby_builds_the_correct_request_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/places:searchNearby"
        import json as _json

        payload = _json.loads(request.content)
        assert payload["locationRestriction"]["circle"]["center"] == {
            "latitude": 47.6,
            "longitude": -122.3,
        }
        assert payload["locationRestriction"]["circle"]["radius"] == 1500.0
        assert payload["includedTypes"] == ["cafe"]
        return httpx.Response(200, json={"places": [_place("near-1", "Nearby Cafe")]})

    connector = _connector(handler)
    page = await connector.search_nearby(
        latitude=47.6, longitude=-122.3, radius_meters=1500.0, included_type="cafe"
    )
    assert len(page.businesses) == 1
    assert page.businesses[0].name == "Nearby Cafe"
