"""Readiness registry, authority classes, source adapters and conflict detection."""
import copy
import random

import pytest

from app.importers import ADAPTERS
from app.importers.geoalgeria import build_rows as build_mosques
from app.importers.hadith_grades import GRADER_BOOKS, build_rows as build_grades, parse_references
from app.importers.osm_overpass import OsmOverpassMosques, parse_bbox
from app.services.data_contracts import DirectoryListingInput, validate_record_batch
from app.services.data_quality import find_listing_conflicts, load_source_quality_notes
from app.services.knowledge_retrieval import authority_of, authority_summary, verification_state
from app.services.manifest import load_manifest
from app.services.readiness import GATES, STATUSES, evaluate_domain, load_registry, summarise, validate_registry

MANIFEST = load_manifest()
REGISTRY = load_registry()


# ---------------------------------------------------------------- registry
def test_registry_is_consistent_with_the_manifest():
    assert validate_registry(REGISTRY, MANIFEST) == []


def test_all_requested_domains_are_present_with_all_fields():
    names = {d["domain"] for d in REGISTRY["domains"]}
    assert names >= {"quran", "hadith", "tafsir", "fiqh", "aqeedah", "seerah", "scholars", "terminology", "history", "civilization", "libraries", "mosques", "organisations", "events",
                     "charities", "volunteering", "businesses", "professionals", "health", "jobs", "recitation_audio", "hadith_gradings"}
    assert REGISTRY["statuses"] == list(STATUSES) and [g["id"] for g in REGISTRY["gates"]] == list(GATES)
    for d in REGISTRY["domains"]:
        assert d["verified_by"] and "no human" in d["verified_by"].lower()  # nothing claims a human review that did not happen


def test_nothing_is_ready_unless_every_gate_passes_and_no_blockers_remain():
    for d in REGISTRY["domains"]:
        if d["status"] == "READY":
            assert all(g["passed"] for g in d["gates"].values()) and not d["blockers"] and d["coverage"] == "FULL", d["domain"]
        else:
            assert d["blockers"] or any(not g["passed"] for g in d["gates"].values()), d["domain"]


def test_hidden_and_unverified_domains_have_the_honest_status():
    by = {d["domain"]: d for d in REGISTRY["domains"]}
    assert by["hadith_gradings"]["status"] == "RIGHTS_UNVERIFIED" and by["hadith_gradings"]["records"]["published"] == 0
    assert by["tafsir"]["status"] == "RIGHTS_UNVERIFIED" and by["tafsir"]["records"]["published"] == 0
    assert by["mosques"]["coverage"] == "PARTIAL" and "Algeria" in by["mosques"]["coverage_note"]
    for empty in ("fiqh", "aqeedah", "seerah", "terminology", "history", "civilization", "organisations", "events", "volunteering", "businesses", "professionals", "health"):
        assert by[empty]["status"] == "EMPTY" and by[empty]["records"]["total"] == 0
    for blocked in ("scholars", "libraries", "charities", "jobs", "recitation_audio"):
        assert by[blocked]["status"] == "SOURCE_BLOCKED" and by[blocked]["blockers"]


def mutated(domain, **changes):
    reg = copy.deepcopy(REGISTRY)
    d = next(x for x in reg["domains"] if x["domain"] == domain)
    for key, value in changes.items():
        if key == "gate_fail":
            d["gates"][value]["passed"] = False
        elif key == "records":
            d["records"] = value
        else:
            d[key] = value
    return reg


@pytest.mark.parametrize("domain,changes,fragment", [
    ("quran", {"gate_fail": "rights_established"}, "READY but gates fail"),
    ("quran", {"blockers": ["something"]}, "READY must have no blockers"),
    ("quran", {"coverage": "PARTIAL"}, "FULL coverage"),
    ("fiqh", {"records": {"unit": "r", "total": 5, "published": 0, "hidden": 5, "live_key": "kr:fiqh"}}, "cannot have records"),
    ("mosques", {"records": {"unit": "r", "total": 10, "published": 3, "hidden": 3, "live_key": "dl:mosque"}}, "total != published + hidden"),
    ("hadith_gradings", {"status": "PUBLISHED"}, "needs published records"),
    ("tafsir", {"datasets": ["not-in-the-manifest"]}, "not in the manifest"),
    ("mosques", {"status": "READY"}, "READY but gates fail"),
    ("scholars", {"blockers": [], "status": "SOURCE_BLOCKED"}, "must state its blockers"),
])
def test_validator_rejects_overclaiming(domain, changes, fragment):
    problems = validate_registry(mutated(domain, **changes), MANIFEST)
    assert any(fragment in p for p in problems), problems


def test_a_domain_cannot_claim_ready_if_its_published_dataset_is_withdrawn():
    quran = next(d for d in REGISTRY["domains"] if d["domain"] == "quran")
    live = {"datasets": {ds: {"publication_status": "published", "enabled": True, "validation_status": "VERIFIED", "license_status": "VERIFIED_OPEN"} for ds in quran["published_datasets"]}}
    assert evaluate_domain(quran, live)["status"] == "READY"
    live["datasets"]["quran-arabic-uthmani-hafs"]["publication_status"] = "staged"
    result = evaluate_domain(quran, live)
    assert result["status"] == "IMPORTED" and any("no longer published" in r for r in result["downgrade_reasons"])
    live["datasets"]["quran-arabic-uthmani-hafs"].update(publication_status="published", validation_status="NEEDS_REVIEW")
    assert evaluate_domain(quran, live)["status"] == "IMPORTED"


def test_a_domain_with_no_published_records_in_the_database_is_never_shown_as_ready():
    quran = next(d for d in REGISTRY["domains"] if d["domain"] == "quran")
    live = {"datasets": {ds: {"publication_status": "published", "enabled": True, "validation_status": "VERIFIED", "license_status": "VERIFIED_OPEN"} for ds in quran["published_datasets"]},
            "counts": {"quran_ayahs": {"total": 0, "published": 0, "hidden": 0}}}
    result = evaluate_domain(quran, live)
    assert result["status"] == "EMPTY" and result["why_not_ready"]
    live["counts"]["quran_ayahs"] = {"total": 6236, "published": 0, "hidden": 6236}
    assert evaluate_domain(quran, live)["status"] == "IMPORTED"


def test_live_counts_that_disagree_with_the_registry_are_flagged():
    mosques = next(d for d in REGISTRY["domains"] if d["domain"] == "mosques")
    result = evaluate_domain(mosques, {"counts": {"dl:mosque": {"total": 5, "published": 5, "hidden": 0}}, "datasets": {}})
    assert result["registry_out_of_date"] and result["counts"]["total"] == 5


def test_summary_lists_why_each_domain_is_not_ready():
    summary = summarise(REGISTRY)
    assert sum(summary["summary"].values()) == len(REGISTRY["domains"])
    for row in summary["domains"]:
        if row["status"] != "READY":
            assert row["why_not_ready"], row["domain"]


def test_manifest_record_counts_match_the_registry_for_imported_datasets():
    by = {d["id"]: d for d in MANIFEST["datasets"]}
    assert by["directory-mosques"]["records"] == 19781 and by["hadith-grading"]["records"] == 21185


# ---------------------------------------------------------------- authority classes
@pytest.mark.parametrize("kind,sch,val,pub,attrs,expected", [
    ("fiqh", "reviewed", "VERIFIED", "published_edition", {}, "secondary_source"),
    ("history", "scholar_verified", "VERIFIED", "published_edition", {"source_class": "primary"}, "primary_source"),
    ("fiqh", "unreviewed", "VERIFIED", "published_edition", {}, "unverified"),
    ("fiqh", "reviewed", "NEEDS_REVIEW", "published_edition", {}, "unverified"),
    ("fiqh", "disputed", "VERIFIED", "published_edition", {}, "disputed"),
    ("hadith_grading", "reviewed", "VERIFIED", "dataset", {}, "community_dataset"),
    ("hadith_grading", "reviewed", "VERIFIED", "unspecified", {}, "community_dataset"),
    ("history", "reviewed", "VERIFIED", "published_edition", {"inferred": True}, "inferred"),
])
def test_authority_class_is_never_raised_by_guesswork(kind, sch, val, pub, attrs, expected):
    assert authority_of(kind, sch, val, pub, attrs) == expected


def test_authority_summary_and_abstention():
    assert authority_summary({"primary_source": [], "scholarly_explanation": [], "secondary_source": []}, []) == {"unavailable": 1}
    counted = authority_summary({"primary_source": [{"authority_class": "primary_source"}], "scholarly_explanation": [{"authority_class": "secondary_source"}], "secondary_source": []},
                                [{"authority_class": "disputed"}])
    assert counted == {"primary_source": 1, "secondary_source": 1, "disputed": 1}
    assert "NEEDS_REVIEW" in verification_state("reviewed", "NEEDS_REVIEW", "source_cited")


# ---------------------------------------------------------------- adapters
def test_every_adapter_targets_a_declared_dataset_and_states_its_licence():
    ids = {d["id"] for d in MANIFEST["datasets"]}
    for adapter in ADAPTERS.values():
        assert adapter.dataset_key in ids and adapter.licence_summary and adapter.probe_urls and adapter.kind in {"listings", "records"}


def test_hadith_grade_adapter_keeps_the_repositorys_own_reference_text_and_marks_rights_unverified():
    refs = parse_references("https://al-maktaba.org/book/1755  abu dawed, albani<br>\nhttps://fawazahmed0.github.io/maktaba-grades-backup/1755 abu dawed, albani (backup link)\n"
                            "https://zubairalizai.com/ zubair ali zai\nhttps://archive.org/details/noor-book.com-3_20211020 Malik, Salim Al Hilali")
    assert refs["1755"] == "https://al-maktaba.org/book/1755 abu dawed, albani" and "zubairalizai.com" in refs and "noor-book.com-3_20211020" in refs
    info = {"abudawud": {"metadata": {"sections": {"1": "Purification"}}, "hadiths": [{"hadithnumber": 1, "arabicnumber": 1, "reference": {"book": 1, "hadith": 1},
            "grades": [{"name": "Al-Albani", "grade": "Hasan Sahih"}, {"name": "Zubair Ali Zai", "grade": "Daif"}]}]},
            **{k: {"metadata": {"sections": {}}, "hadiths": []} for k in ("ibnmajah", "malik", "nasai", "tirmidhi")}}
    rows, _ = build_grades(info, refs)
    grades = rows[0]["attributes"]["grades"]
    assert grades[0]["source_reference_text"].endswith("abu dawed, albani") and grades[0]["rights_status"] == "unverified" and grades[0]["verification_status"] == "unverified"
    assert "grading_work" not in grades[0] and "page_reference" not in grades[0]    # absent from the source, so absent here
    assert validate_record_batch(rows).valid and ("malik", "Salim al-Hilali") in GRADER_BOOKS


def test_grade_entries_accept_work_edition_page_but_reject_unknown_fields_and_values():
    base = {"id": "g", "entity_type": "hadith_grading", "title": "t", "description": "d", "source": "s", "license": "l", "provenance": "provenance", "source_work": "w", "language": "en",
            "attributes": {"collection": "c", "hadith_number": 1, "grades": [{"grader": "A", "grade": "Sahih", "grading_source": "s", "grading_work": "W", "grading_edition": "E", "page_reference": "p. 3",
                                                                                "rights_status": "permission_granted", "verification_status": "checked_against_source"}]}}
    assert validate_record_batch([base]).valid
    for bad in ({"rating": 5}, {"rights_status": "free"}, {"verification_status": "true"}):
        row = copy.deepcopy(base)
        row["attributes"]["grades"][0].update(bad)
        assert validate_record_batch([row]).failures, bad


def test_mosque_adapter_preserves_every_source_identifier():
    rows, _ = build_mosques([{"id": "16-0001", "name": "Test", "name_ar": None, "lat": 36.7, "lng": 3.0, "source": "wikidata+osm", "refs": {"wikidata": "Q1", "osm": "node/5"}, "denomination": None}])
    a = rows[0]["attributes"]
    assert (a["geoalgeria_id"], a["wikidata"], a["osm"]) == ("16-0001", "Q1", "node/5") and rows[0]["external_key"] == "geoalgeria:16-0001"
    DirectoryListingInput.model_validate(rows[0])


def test_geoalgeria_adapter_refuses_a_changed_upstream_licence(monkeypatch):
    from app.importers import geoalgeria
    monkeypatch.setattr(geoalgeria, "npm_package", lambda name, version: ({"license": "MIT"}, {}, "x"))
    with pytest.raises(SystemExit):
        geoalgeria.GeoAlgeriaMosques().fetch({})


def test_overpass_adapter_needs_a_valid_small_bbox_and_a_country():
    assert parse_bbox("36.7,3.0,36.8,3.1") == (36.7, 3.0, 36.8, 3.1)
    for bad in ("1,2,3", "10,0,5,5", "0,0,5,5", "x"):
        with pytest.raises(ValueError):
            parse_bbox(bad)
    payload = {"elements": [{"type": "node", "id": 1, "lat": 10.0, "lon": 20.0, "tags": {"name": "Fixture Masjid"}}, {"type": "node", "id": 2, "lat": 1.0, "lon": 1.0, "tags": {}}]}
    from app.importers.base import FetchResult
    adapter = OsmOverpassMosques()
    fetched = FetchResult(version="v", checksum="c", payload=payload, source_url="u")
    with pytest.raises(ValueError):
        adapter.build(fetched, {})
    built = adapter.build(fetched, {"country": "gb"})
    assert [r["country"] for r in built.rows] == ["GB"] and built.skipped["no_name_or_coordinates"] == 1 and "ODbL" in built.rows[0]["license"]


# ---------------------------------------------------------------- conflicts
def row(i, name, lat, lon, **kw):
    return {"id": f"id-{i}", "key": f"k{i}", "name": name, "arabic_name": kw.get("arabic"), "lat": lat, "lon": lon, "duplicate_of": kw.get("dup"), "denomination": kw.get("denom"), "type": "mosque"}


FIXTURE = [row(1, "Fixture Mosque Alpha", 10.0000, 20.0000, denom="sunni"), row(2, "Fixture Mosque Alpha", 10.0002, 20.0002, denom="ibadi"),
           row(3, "Fixture Central Mosque Annex", 11.0, 21.0), row(4, "Fixture Central Mosque Annexe", 11.0004, 21.0004),
           row(5, "Totally Unrelated Name", 12.0, 22.0), row(6, "Different Words Here", 12.00005, 22.00005),
           row(7, "Fixture Old Synagogue", 13.0, 23.0), row(8, "Far Away", 50.0, 50.0), row(9, "Fixture Mosque Alpha", 10.0001, 20.0001, dup="x")]


def test_conflict_detection_reports_without_changing_anything():
    original = copy.deepcopy(FIXTURE)
    found = find_listing_conflicts(FIXTURE)
    assert FIXTURE == original
    assert any({d["a"], d["b"]} == {"id-1", "id-2"} for d in found["duplicate_candidates"])
    assert not any("id-9" in (d["a"], d["b"]) for d in found["duplicate_candidates"])         # already linked as a duplicate
    assert any({d["a"], d["b"]} == {"id-3", "id-4"} for d in found["similar_names"])
    assert any({d["a"], d["b"]} == {"id-5", "id-6"} for d in found["co_located_different"])
    assert any({d["a"], d["b"]} == {"id-1", "id-2"} for d in found["denomination_conflicts"])
    assert [d["id"] for d in found["non_mosque_names"]] == ["id-7"]


def test_conflict_detection_is_deterministic_regardless_of_input_order():
    expected = find_listing_conflicts(FIXTURE)
    for seed in range(5):
        shuffled = FIXTURE[:]
        random.Random(seed).shuffle(shuffled)
        assert find_listing_conflicts(shuffled) == expected


def test_source_quality_notes_keep_the_synagogue_anomaly_unchanged():
    notes = load_source_quality_notes()
    note = next(n for n in notes if n["record_key"] == "geoalgeria:16-0918")
    assert note["status"] == "open" and "retained unchanged" in note["action"] and "unknown" in note
    assert all(n["dataset"] == "directory-mosques" and n["unknown"] for n in notes)
