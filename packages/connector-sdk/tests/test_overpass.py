"""Mocked-adapter tests for OverpassConnector (Milestone 20's own
explicit requirement, distinct from a live-API smoke test - this
sandbox's egress proxy rejects every Overpass/OpenStreetMap host tried,
so a live smoke test isn't possible here; see the module docstring in
connector_sdk/overpass.py and docs/adr/0028).

Every test injects an `httpx.MockTransport` shaped exactly like
Overpass's real documented JSON output, so these exercise this
connector's own query construction, response parsing, and error mapping
without a real network call.
"""

import httpx
import pytest
from connector_sdk.errors import (
    ConnectorPermanentError,
    ConnectorRateLimitError,
    ConnectorTransientError,
)
from connector_sdk.overpass import OverpassConnector
from connector_sdk.types import SearchQuery


def _connector(handler) -> OverpassConnector:
    return OverpassConnector(transport=httpx.MockTransport(handler))


def _element(
    element_id: int,
    *,
    element_type: str = "node",
    name: str | None = "Golden Cafe Corner",
    lat: float | None = 25.2,
    lon: float | None = 55.27,
    phone: str | None = "+971-4-1234567",
    website: str | None = "https://example.com",
    housenumber: str | None = "12",
    street: str | None = "Sheikh Zayed Road",
    extra_tags: dict | None = None,
) -> dict:
    tags: dict = {}
    if name is not None:
        tags["name"] = name
    if phone is not None:
        tags["phone"] = phone
    if website is not None:
        tags["website"] = website
    if housenumber is not None:
        tags["addr:housenumber"] = housenumber
    if street is not None:
        tags["addr:street"] = street
    if extra_tags:
        tags.update(extra_tags)

    element: dict = {"type": element_type, "id": element_id, "tags": tags}
    if element_type == "node":
        if lat is not None:
            element["lat"] = lat
        if lon is not None:
            element["lon"] = lon
    else:
        center = {}
        if lat is not None:
            center["lat"] = lat
        if lon is not None:
            center["lon"] = lon
        element["center"] = center
    return element


def _query(**overrides: object) -> SearchQuery:
    query = SearchQuery(
        industry="Restaurants",
        country="United Arab Emirates",
        city="Dubai",
        result_limit=40,
        page_size=20,
    )
    for key, value in overrides.items():
        setattr(query, key, value)
    return query


@pytest.mark.asyncio
async def test_search_success_maps_to_business_records():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(
            200,
            json={"elements": [_element(1, name="Golden Cafe"), _element(2, name="Blue Diner")]},
        )

    connector = _connector(handler)
    page = await connector.search(_query())

    assert len(page.businesses) == 2
    first = page.businesses[0]
    assert first.source == "osm"
    assert first.source_native_id == "node/1"
    assert first.name == "Golden Cafe"
    assert first.category == "restaurant"
    assert first.address == "12 Sheikh Zayed Road"
    assert first.phone == "+971-4-1234567"
    assert first.website == "https://example.com"
    assert first.latitude == 25.2
    assert first.longitude == 55.27
    assert first.google_maps_url == "https://www.openstreetmap.org/node/1"
    assert first.source_url == "https://www.openstreetmap.org/node/1"
    # OSM has no rating/review schema - never fabricated.
    assert first.rating is None
    assert first.review_count is None


@pytest.mark.asyncio
async def test_missing_optional_fields_never_fabricated():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "elements": [
                    _element(3, name=None, phone=None, website=None, housenumber=None, street=None)
                ]
            },
        )

    connector = _connector(handler)
    page = await connector.search(_query())

    business = page.businesses[0]
    # No fabricated name - the source's own stable id is the fallback label.
    assert business.name == "OSM node 3"
    assert business.phone is None
    assert business.website is None
    assert business.address is None


@pytest.mark.asyncio
async def test_way_element_uses_center_for_coordinates():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"elements": [_element(4, element_type="way", lat=25.05, lon=55.17)]},
        )

    connector = _connector(handler)
    page = await connector.search(_query())

    business = page.businesses[0]
    assert business.source_native_id == "way/4"
    assert business.latitude == 25.05
    assert business.longitude == 55.17


@pytest.mark.asyncio
async def test_disused_tag_marks_business_closed_permanently():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "elements": [
                    _element(5, extra_tags={"disused:amenity": "restaurant"}),
                ]
            },
        )

    connector = _connector(handler)
    page = await connector.search(_query())

    assert page.businesses[0].business_status == "closed_permanently"


@pytest.mark.asyncio
async def test_no_lifecycle_tag_leaves_business_status_unknown():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"elements": [_element(6)]})

    connector = _connector(handler)
    page = await connector.search(_query())

    # OSM doesn't reliably track operating status - never assumed
    # "operational" the way business_status might imply for other sources.
    assert page.businesses[0].business_status is None


@pytest.mark.asyncio
async def test_unmapped_industry_raises_without_any_network_call():
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"elements": []})

    connector = _connector(handler)
    with pytest.raises(ConnectorPermanentError):
        await connector.search(_query(industry="Submarine Repair"))

    assert not called


@pytest.mark.asyncio
async def test_pagination_slices_a_single_fetch_across_calls():
    elements = [_element(i) for i in range(1, 6)]  # 5 total matches

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"elements": elements})

    connector = _connector(handler)
    query = _query(result_limit=40, page_size=2)

    page1 = await connector.search(query)
    assert len(page1.businesses) == 2
    assert page1.has_more is True
    assert page1.next_cursor == "2"

    query.cursor = page1.next_cursor
    page2 = await connector.search(query)
    assert len(page2.businesses) == 2
    assert page2.has_more is True
    assert page2.next_cursor == "4"

    query.cursor = page2.next_cursor
    page3 = await connector.search(query)
    assert len(page3.businesses) == 1
    assert page3.has_more is False
    assert page3.next_cursor is None


@pytest.mark.asyncio
async def test_result_limit_caps_pagination_even_with_more_real_matches():
    elements = [_element(i) for i in range(1, 11)]  # 10 real matches available

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"elements": elements})

    connector = _connector(handler)
    query = _query(result_limit=3, page_size=20)

    page = await connector.search(query)
    assert len(page.businesses) == 3
    assert page.has_more is False


@pytest.mark.asyncio
async def test_must_have_phone_filters_client_side():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "elements": [
                    _element(7, phone="+971-4-1111111"),
                    _element(8, phone=None),
                ]
            },
        )

    connector = _connector(handler)
    page = await connector.search(_query(must_have_phone=True))

    assert len(page.businesses) == 1
    assert page.businesses[0].phone == "+971-4-1111111"


@pytest.mark.asyncio
async def test_website_requirement_required_and_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "elements": [
                    _element(9, website="https://a.example.com"),
                    _element(10, website=None),
                ]
            },
        )

    connector = _connector(handler)

    required_page = await connector.search(_query(website_requirement="required"))
    assert len(required_page.businesses) == 1
    assert required_page.businesses[0].website == "https://a.example.com"

    missing_page = await connector.search(_query(website_requirement="missing"))
    assert len(missing_page.businesses) == 1
    assert missing_page.businesses[0].website is None


@pytest.mark.asyncio
async def test_min_rating_and_min_reviews_are_never_applied():
    # supports_rating_filter=False means campaign creation rejects these
    # filters outright (see test_campaign_engine.py) - but the connector
    # itself must never silently drop real matches if somehow called with
    # them set, since it has no rating data to filter against honestly.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"elements": [_element(11), _element(12)]})

    connector = _connector(handler)
    page = await connector.search(_query(min_rating=4.5, min_reviews=100))

    assert len(page.businesses) == 2


@pytest.mark.asyncio
async def test_supports_rating_filter_is_false():
    assert OverpassConnector.supports_rating_filter is False


@pytest.mark.asyncio
async def test_rate_limit_error_maps_to_connector_rate_limit_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    connector = _connector(handler)
    with pytest.raises(ConnectorRateLimitError):
        await connector.search(_query())


@pytest.mark.asyncio
async def test_server_error_maps_to_connector_transient_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(504, text="gateway timeout")

    connector = _connector(handler)
    with pytest.raises(ConnectorTransientError):
        await connector.search(_query())


@pytest.mark.asyncio
async def test_client_error_maps_to_connector_permanent_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request")

    connector = _connector(handler)
    with pytest.raises(ConnectorPermanentError):
        await connector.search(_query())


@pytest.mark.asyncio
async def test_non_json_response_maps_to_connector_transient_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>Overpass had trouble</html>")

    connector = _connector(handler)
    with pytest.raises(ConnectorTransientError):
        await connector.search(_query())


@pytest.mark.asyncio
async def test_network_timeout_maps_to_connector_transient_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    connector = _connector(handler)
    with pytest.raises(ConnectorTransientError):
        await connector.search(_query())


@pytest.mark.asyncio
async def test_estimate_cost_is_result_limit_with_no_network_call():
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"elements": []})

    connector = _connector(handler)
    cost = await connector.estimate_cost(_query(result_limit=17))

    assert cost == 17.0
    assert not called


@pytest.mark.asyncio
async def test_health_check_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"elements": []})

    connector = _connector(handler)
    assert await connector.health_check() is True


@pytest.mark.asyncio
async def test_health_check_failure_on_server_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="down")

    connector = _connector(handler)
    assert await connector.health_check() is False


@pytest.mark.asyncio
async def test_health_check_failure_on_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    connector = _connector(handler)
    assert await connector.health_check() is False


def test_build_query_chains_country_then_city_area():
    query = _query(country="United Arab Emirates", city="Dubai")
    ql = OverpassConnector._build_query(query, "amenity", "restaurant", limit=90)

    assert 'area["name"="United Arab Emirates"]["admin_level"="2"]->.country;' in ql
    assert 'area["name"="Dubai"](area.country)->.searchArea;' in ql
    assert 'node["amenity"="restaurant"](area.searchArea);' in ql
    assert 'way["amenity"="restaurant"](area.searchArea);' in ql
    assert "out center 90;" in ql


def test_resolve_tag_prefers_category_over_industry():
    query = _query(industry="Restaurants", category="cafes")
    assert OverpassConnector._resolve_tag(query) == ("amenity", "cafe")
