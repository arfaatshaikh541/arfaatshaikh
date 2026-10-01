import pytest

from app.services.data_contracts import (
    DirectoryListingInput, KnowledgeRecordInput, can_publish, dedupe_key, haversine_km, validate_record_batch,
)

GOOD = dict(id="seerah-0001", entity_type="seerah", title="Example", description="Described.", source="Owner-supplied dataset X",
            license="Owner permission", provenance="Supplied by the owner on 2026-10-01", scholarly_status="unreviewed")


def test_valid_record_round_trips():
    record = KnowledgeRecordInput.model_validate(GOOD)
    assert record.tags == [] and len(record.content_hash()) == 64


@pytest.mark.parametrize("missing", ["source", "license", "provenance", "description", "title"])
def test_record_without_required_metadata_is_rejected(missing):
    row = {k: v for k, v in GOOD.items() if k != missing}
    result = validate_record_batch([row])
    assert not result.valid and result.failures[0]["errors"]


def test_unknown_type_status_and_bad_url_are_rejected():
    assert validate_record_batch([{**GOOD, "entity_type": "made_up"}]).failures
    assert validate_record_batch([{**GOOD, "scholarly_status": "authentic"}]).failures
    assert validate_record_batch([{**GOOD, "source_url": "javascript:alert(1)"}]).failures


def test_reviewed_record_needs_last_verified():
    assert validate_record_batch([{**GOOD, "scholarly_status": "reviewed"}]).failures
    assert validate_record_batch([{**GOOD, "scholarly_status": "reviewed", "last_verified": "2026-10-01"}]).valid


def test_duplicates_and_type_mismatch_are_reported_not_hidden():
    result = validate_record_batch([GOOD, GOOD, {**GOOD, "id": "x2", "entity_type": "fiqh"}], expected_type="seerah")
    assert len(result.valid) == 1
    assert {f["errors"][0] for f in result.failures} == {"duplicate id in file", "entity_type fiqh does not match dataset type seerah"}


def test_non_object_rows_fail_cleanly():
    assert validate_record_batch(["text", 5]).failures[0]["errors"] == ["record must be a JSON object"]


def test_relationship_requires_source():
    row = {**GOOD, "relationships": [{"relation_type": "authored", "target_id": "b1"}]}
    assert validate_record_batch([row]).failures


@pytest.mark.parametrize("licence,validation,confirm,ok", [
    ("VERIFIED_OPEN", "VERIFIED", None, True),
    ("PUBLIC_DOMAIN", "VERIFIED", None, True),
    ("VERIFIED_OPEN", "NEEDS_REVIEW", None, False),
    ("LICENSE_REQUIRED", "VERIFIED", None, False),
    ("PROVENANCE_UNCLEAR", "VERIFIED", None, False),
    ("UNKNOWN", "VERIFIED", None, False),
    ("OWNER_PERMISSION_GRANTED", "VERIFIED", None, False),
    ("OWNER_PERMISSION_GRANTED", "VERIFIED", {"confirmed_by": "Owner", "confirmed_on": "2026-10-01", "basis": "written permission"}, True),
])
def test_publication_gate(licence, validation, confirm, ok):
    assert can_publish(license_status=licence, validation_status=validation, rights_confirmation=confirm)[0] is ok


def test_directory_listing_contract():
    listing = DirectoryListingInput(listing_type="mosque", name="Masjid al-Noor", city="Leeds", country="gb", latitude=53.8, longitude=-1.55,
                                    source="Owner", license="ODbL", provenance="OpenStreetMap export")
    assert listing.country == "GB"
    with pytest.raises(ValueError):
        DirectoryListingInput(listing_type="mosque", name="X Y", latitude=1.0, source="s", license="l", provenance="prov")
    with pytest.raises(ValueError):
        DirectoryListingInput(listing_type="shop", name="X Y", source="s", license="l", provenance="prov")


def test_dedupe_key_ignores_case_diacritics_and_filler_words():
    assert dedupe_key("The Al-Noor Mosque", "Leeds", "GB") == dedupe_key("al noor masjid", "leeds", "gb")
    assert dedupe_key("Noor", "Leeds", "GB") != dedupe_key("Noor", "Bradford", "GB")


def test_haversine_known_distance():
    assert abs(haversine_km(51.5074, -0.1278, 48.8566, 2.3522) - 343.5) < 2
