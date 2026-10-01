from app.services.data_contracts import DirectoryListingInput
from app.services.osm_import import OSM_LICENCE, overpass_query, parse_overpass

# Synthetic structure-only fixture (the Overpass JSON shape). These are NOT real listings.
PAYLOAD = {"elements": [
    {"type": "node", "id": 1, "lat": 10.0, "lon": 20.0, "tags": {"name": "Fixture Masjid One", "amenity": "place_of_worship", "religion": "muslim", "addr:city": "Testville",
                                                                 "addr:country": "GB", "website": "example.org", "email": "info@example.org"}},
    {"type": "way", "id": 2, "center": {"lat": 11.5, "lon": 21.5}, "tags": {"name": "Fixture Centre Two", "amenity": "place_of_worship"}},
    {"type": "node", "id": 3, "lat": 1.0, "lon": 1.0, "tags": {"amenity": "place_of_worship"}},
    {"type": "relation", "id": 4, "tags": {"name": "No Coordinates"}},
]}


def test_parse_keeps_provenance_and_skips_incomplete_objects():
    rows, skipped = parse_overpass(PAYLOAD)
    assert [r["external_key"] for r in rows] == ["node/1", "way/2"]
    assert {s["reason"] for s in skipped} == {"no name tag", "no coordinates"}
    assert rows[0]["license"] == OSM_LICENCE and rows[0]["source_url"] == "https://www.openstreetmap.org/node/1" and "OpenStreetMap node/1" in rows[0]["provenance"]
    assert rows[0]["website"] == "https://example.org" and rows[1]["latitude"] == 11.5


def test_parsed_rows_satisfy_the_directory_contract():
    rows, _ = parse_overpass(PAYLOAD)
    for row in rows:
        DirectoryListingInput.model_validate(row)


def test_query_targets_muslim_places_of_worship_in_the_box():
    q = overpass_query(1, 2, 3, 4)
    assert q.count('"religion"="muslim"') == 3 and "(1,2,3,4)" in q
