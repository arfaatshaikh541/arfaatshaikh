"""Contract rules for the data-completion work: religious records are traceable and never merged, listings need what
their type needs, imports are all-or-nothing, expired jobs and events never show, and the shipped importers behave."""
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.services.data_contracts import (
    DirectoryListingInput, check_listing_structure, validate_record_batch,
)
from app.services.data_validation import quran_ref_problems, same_place_duplicates, url_problems

BASE = dict(source="Named work", license="Terms stated by the owner", provenance="Supplied with the work's citation", language="en", source_work="A named classical work")
FIQH = dict(BASE, id="f1", entity_type="fiqh", title="Topic (Hanafi)", description="Position stated by the work.", chapter="Book of Purification",
            provenance_status="source_cited", attributes={"madhhab": "Hanafi", "topic": "wudu", "question": "q", "ruling": "r"})
GRADING = dict(BASE, id="g1", entity_type="hadith_grading", title="Grades", description="d",
               attributes={"collection": "abudawud", "hadith_number": 1, "grades": [
                   {"grader": "A", "grade": "Sahih", "grading_source": "work A"}, {"grader": "B", "grade": "Daif", "grading_source": "work B"}]})


def bad(row):
    return validate_record_batch([row]).failures


def test_fiqh_needs_madhhab_question_ruling_and_a_traceable_source():
    assert validate_record_batch([FIQH]).valid
    for key in ("madhhab", "topic", "question", "ruling"):
        assert bad({**FIQH, "attributes": {k: v for k, v in FIQH["attributes"].items() if k != key}})
    assert bad({k: v for k, v in FIQH.items() if k != "source_work"})          # no named work
    assert bad({k: v for k, v in FIQH.items() if k != "chapter"})              # no page or chapter
    assert bad({k: v for k, v in FIQH.items() if k != "language"})


def test_opposing_madhhab_positions_are_separate_records():
    shafii = {**FIQH, "id": "f2", "attributes": {**FIQH["attributes"], "madhhab": "Shafi'i", "ruling": "a different ruling"}}
    result = validate_record_batch([FIQH, shafii], expected_type="fiqh")
    assert len(result.valid) == 2 and not result.failures


def test_aqeedah_needs_school_and_statement():
    row = dict(BASE, id="a1", entity_type="aqeedah", title="t", description="d", page="12", attributes={"school": "Ash'ari", "topic": "x", "statement": "s"})
    assert validate_record_batch([row]).valid
    assert bad({**row, "attributes": {"topic": "x", "statement": "s"}})


def test_seerah_must_state_reliability_category():
    row = dict(BASE, id="s1", entity_type="seerah", title="t", description="d", attributes={"reliability": "weak_reports"})
    assert validate_record_batch([row]).valid
    assert bad({**row, "attributes": {}}) and bad({**row, "attributes": {"reliability": "authentic"}})


def test_hadith_grading_keeps_each_grader_and_never_infers():
    assert validate_record_batch([GRADING]).valid
    assert bad({**GRADING, "attributes": {**GRADING["attributes"], "grades": []}})
    no_source = [{"grader": "A", "grade": "Sahih"}]
    assert bad({**GRADING, "attributes": {**GRADING["attributes"], "grades": no_source}})
    twice = [{"grader": "A", "grade": "Sahih", "grading_source": "s"}, {"grader": "A", "grade": "Daif", "grading_source": "s"}]
    assert bad({**GRADING, "attributes": {**GRADING["attributes"], "grades": twice}})


def test_library_work_cannot_carry_a_file_without_redistribution_rights():
    row = dict(BASE, id="l1", entity_type="library_work", title="t", description="d", attributes={"availability": "metadata_only", "isbn": "978-3-16-148410-0"})
    assert validate_record_batch([row]).valid
    assert bad({**row, "attributes": {"availability": "owner_file"}})                                   # licence status UNKNOWN
    assert bad({**row, "attributes": {"availability": "external_link"}})                                # no URL
    assert bad({**row, "attributes": {"availability": "metadata_only", "isbn": "12"}})


@pytest.mark.parametrize("ref,ok", [("2:255", True), ("2:255-257", True), ("114:6", True), ("115:1", False), ("0:1", False), ("2:0", False), ("2:257-255", False), ("x", False)])
def test_quran_reference_format(ref, ok):
    row = {**FIQH, "attributes": {**FIQH["attributes"], "quran_refs": [ref]}}
    assert bool(validate_record_batch([row]).valid) is ok


def test_quran_reference_must_exist_in_the_loaded_text():
    counts = {1: 7, 2: 286}
    assert not quran_ref_problems(["2:286", "1:1-7"], counts)
    assert quran_ref_problems(["1:8"], counts) and quran_ref_problems(["3:1"], counts)


NOW = datetime.now(UTC)
JOB = dict(listing_type="job", name="Data analyst", source="Employer feed", license="Employer terms", provenance="Posted by the employer",
           expires_at=(NOW + timedelta(days=30)).isoformat(), attributes={"employer": "Example Ltd", "application_url": "https://example.org/apply", "employment_type": "full_time"})


def listing_errors(row):
    try:
        DirectoryListingInput.model_validate(row)
        return []
    except Exception as exc:  # pydantic.ValidationError
        return [str(exc)]


def test_job_needs_employer_application_url_and_expiry():
    assert not listing_errors(JOB)
    assert listing_errors({**JOB, "expires_at": None})
    assert listing_errors({**JOB, "attributes": {"application_url": "https://example.org"}})
    assert listing_errors({**JOB, "attributes": {"employer": "X", "application_url": "ftp://x"}})
    assert listing_errors({**JOB, "attributes": {**JOB["attributes"], "employment_type": "slave"}})
    assert listing_errors({**JOB, "attributes": {**JOB["attributes"], "rating": 5}})                  # unknown attributes are refused


def test_event_and_volunteering_rules():
    event = dict(listing_type="event", name="Open day", source="Organiser", license="Organiser terms", provenance="Posted by the organiser", starts_at="2030-01-01T10:00:00Z")
    assert not listing_errors(event)
    assert listing_errors({k: v for k, v in event.items() if k != "starts_at"})
    assert listing_errors({**event, "ends_at": "2029-12-31T10:00:00Z"})
    assert listing_errors({**event, "listing_type": "volunteering"})                                   # needs organization


def test_naive_times_are_read_as_utc():
    item = DirectoryListingInput.model_validate({**JOB, "expires_at": "2099-01-01T00:00:00"})
    assert item.expires_at.tzinfo is not None


def test_no_donation_links_and_no_unsourced_denomination():
    charity = dict(listing_type="charity", name="Example Trust", source="Register", license="OGL", provenance="From the register", attributes={"donation_url": "https://x.org/donate"})
    assert listing_errors(charity)
    mosque = dict(listing_type="mosque", name="Mosque", source="OSM", license="ODbL", provenance="Mapped", attributes={"denomination": "sunni"})
    assert listing_errors(mosque)
    assert not listing_errors({**mosque, "attributes": {"denomination": "sunni", "denomination_source": "OpenStreetMap tag"}})


def test_url_and_duplicate_helpers():
    assert url_problems("x", "1", {"website": "javascript:alert(1)"}) and not url_problems("x", "1", {"website": "https://example.org", "u": None})
    items = [("a", "k", 36.0, 3.0), ("b", "k", 36.0001, 3.0001), ("c", "k", 40.0, 3.0), ("d", "other", 36.0, 3.0)]
    assert same_place_duplicates(items, 0.05) == ["possible duplicate: b and a (k)"]


# ---------------------------------------------------------------- shipped importer adapters
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name):
    import importlib
    return importlib.import_module({"build_hadith_grading_records": "app.importers.hadith_grades", "build_geoalgeria_mosques": "app.importers.geoalgeria"}[name])


def test_hadith_grade_adapter_copies_grades_verbatim_and_drops_placeholders():
    module = _load("build_hadith_grading_records")
    info = {"abudawud": {"metadata": {"sections": {"1": "Purification"}}, "hadiths": [
        {"hadithnumber": 1, "arabicnumber": 1, "reference": {"book": 1, "hadith": 1}, "grades": [
            {"name": "Al-Albani", "grade": "Hasan Sahih"}, {"name": "Zubair Ali Zai", "grade": "Daif"}, {"name": "Shuaib Al Arnaut", "grade": "-"}]},
        {"hadithnumber": 2, "arabicnumber": 2, "reference": {"book": 1, "hadith": 2}, "grades": []}]},
        **{k: {"metadata": {"sections": {}}, "hadiths": []} for k in ("ibnmajah", "malik", "nasai", "tirmidhi")}}
    rows, stats = module.build_rows(info, {})
    assert len(rows) == 1 and stats["placeholder_grades_skipped"] == 1
    grades = rows[0]["attributes"]["grades"]
    assert [(g["grader"], g["grade"]) for g in grades] == [("Al-Albani", "Hasan Sahih"), ("Zubair Ali Zai", "Daif")]
    assert rows[0]["license_status"] == "LICENSE_REQUIRED" and validate_record_batch(rows).valid


def test_mosque_adapter_invents_nothing():
    module = _load("build_geoalgeria_mosques")
    records = [
        {"id": "16-0001", "name": "Mosquée A", "name_ar": None, "name_fr": "Mosquée A", "wilaya_code": "16", "commune_code": "1607", "commune": "Casbah", "lat": 36.78, "lng": 3.06,
         "geo_precision": "exact", "geo_method": "osm_node", "source": "wikidata+osm", "refs": {"wikidata": "Q1", "osm": "node/5"}, "denomination": "sunni"},
        {"id": "16-0002", "name": None, "name_ar": None, "name_fr": None, "lat": 36.7, "lng": 3.0, "source": "osm", "refs": {"osm": "node/6"}, "denomination": None},
        {"id": "16-0003", "name": "مسجد", "name_ar": "مسجد", "wilaya_code": "16", "lat": 36.7, "lng": 3.1, "source": "wikidata", "refs": {"wikidata": "Q3"}, "denomination": "sunni"},
    ]
    rows, skipped = module.build_rows(records)
    assert skipped["no_name"] == 1 and len(rows) == 2
    assert rows[0]["attributes"]["denomination"] == "sunni" and "ODbL" in rows[0]["license"]
    assert "denomination" not in rows[1]["attributes"] and rows[1]["license"].startswith("CC0")   # Wikidata-only: denomination not from an explicit OSM tag
    assert all(not check_listing_structure(DirectoryListingInput.model_validate(r)) for r in rows)


def test_source_candidates_are_complete_and_never_silently_verified():
    path = Path(__file__).resolve().parents[3] / "data" / "source-candidates.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    manifest = json.loads((path.parent / "source-manifest.json").read_text(encoding="utf-8"))
    published = {d["id"] for d in manifest["datasets"] if d["publication_status"] == "published"}
    required = ("SOURCE_NAME", "SOURCE_URL", "OWNER", "TYPE", "DATA_DOMAIN", "LICENSE", "LICENSE_URL", "PROVENANCE", "ACCESS_METHOD", "REDISTRIBUTION_ALLOWED",
                "COMMERCIAL_USE_ALLOWED", "ATTRIBUTION_REQUIRED", "MODIFICATION_ALLOWED", "UNDERLYING_RIGHTS", "DATABASE_RIGHTS", "METADATA_ONLY_SAFE", "LAST_VERIFIED", "VERIFICATION_STATUS")
    for source in data["sources"]:
        assert source["VERIFICATION_STATUS"] in data["statuses"]
        assert all(str(source.get(k) or "").strip() for k in required), source["SOURCE_ID"]
        assert source["EVIDENCE"] and source["OPEN_QUESTIONS"], source["SOURCE_ID"]
        if source["VERIFICATION_STATUS"] == "VERIFIED":
            assert source["LICENSE_URL"].startswith("http") and source["MANIFEST_DATASET"] in {d["id"] for d in manifest["datasets"]}
        if source["MANIFEST_DATASET"] in published and source["VERIFICATION_STATUS"] != "VERIFIED":
            pytest.fail(f"{source['SOURCE_ID']} backs a published dataset but is {source['VERIFICATION_STATUS']}")


# ---------------------------------------------------------------- assistant: sourced records
def test_knowledge_hits_keep_positions_apart_and_flag_uncertainty():
    from app.services.knowledge_retrieval import coverage, uncertainty_of
    assert coverage(["wudu", "water"], "Wudu with water") == 1.0 and coverage([], "x") == 0.0
    assert any("differ" in n for n in uncertainty_of("hadith_grading", "reviewed", {"grades": [{"grade": "Sahih"}, {"grade": "Daif"}]}))
    assert not any("differ" in n for n in uncertainty_of("hadith_grading", "reviewed", {"grades": [{"grade": "Sahih"}, {"grade": "Sahih"}]}))
    assert any("not the only one" in n for n in uncertainty_of("fiqh", "scholar_verified", {}))
    assert any("weak reports" in n for n in uncertainty_of("seerah", "reviewed", {"reliability": "weak_reports"}))
    assert not uncertainty_of("seerah", "reviewed", {"reliability": "established"})
    assert any("unreviewed" in n for n in uncertainty_of("history", "unreviewed", {}))
