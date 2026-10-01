"""Source-sensitive validation. These tests FAIL if provenance, licence status, sources or identifiers are missing,
so a release cannot silently ship unsourced religious content."""
import copy
import re
import subprocess
import sys
from pathlib import Path

import pytest

from app.services.data_validation import citation_problems, find_duplicates, grading_problems, manifest_problems, missing_metadata
from app.services.manifest import load_manifest, manifest_path, validate_manifest
from app.services.publication_policy import desired_visibility

ROOT = manifest_path().parents[1]
MANIFEST = load_manifest()


def entry(**over):
    base = copy.deepcopy(next(d for d in MANIFEST["datasets"] if d["id"] == "quran-arabic-uthmani-hafs"))
    base.update(over)
    return {"datasets": [base]}


# ---------------------------------------------------------------- the real manifest
def test_real_manifest_is_valid():
    assert manifest_problems(MANIFEST) == []


def test_every_dataset_declares_the_required_fields():
    for d in MANIFEST["datasets"]:
        for key in ("source", "license", "provenance", "validation_status", "publication_status", "readiness", "transformation", "import_method", "last_checked"):
            assert d.get(key) not in (None, "", {}), (d["id"], key)
        assert d["license"].get("status") and d["source"].get("name")


def test_dataset_identifiers_are_unique():
    assert find_duplicates(d["id"] for d in MANIFEST["datasets"]) == []


def test_no_unlicensed_or_unclear_dataset_is_public():
    for d in MANIFEST["datasets"]:
        if d["public"]:
            assert d["license"]["status"] in {"VERIFIED_OPEN", "PUBLIC_DOMAIN", "PD_WORK_OPEN_EDITION_DECLARED", "OWNER_PERMISSION_GRANTED"}, d["id"]
            assert d["validation_status"] == "VERIFIED", d["id"]
            assert d["publication_status"] == "published", d["id"]


def test_datasets_awaiting_rights_are_not_public():
    for d in MANIFEST["datasets"]:
        if d["readiness"] in {"LICENSE_REQUIRED", "PROVENANCE_UNCLEAR", "OWNER_UPLOAD_REQUIRED", "UNAVAILABLE"}:
            assert not d["public"] and d["publication_status"] == "staged", d["id"]


def test_quran_text_is_published_only_with_a_verified_open_source():
    quran = next(d for d in MANIFEST["datasets"] if d["id"] == "quran-arabic-uthmani-hafs")
    assert quran["public"] and quran["license"]["status"] == "VERIFIED_OPEN" and quran["validation_status"] == "VERIFIED"
    assert quran["source"]["url"] and quran["checksum_sha256"] and len(quran["checksum_sha256"]) == 64


def test_every_acquired_dataset_names_a_real_importer_with_a_version():
    for d in MANIFEST["datasets"]:
        if d.get("date_acquired"):
            for script in re.findall(r"scripts/([\w]+\.py)", d["importer"]):
                assert (ROOT / "apps" / "api" / "scripts" / script).is_file(), (d["id"], script)
            assert d["importer_version"]


def test_importers_without_data_point_at_existing_tooling():
    for d in MANIFEST["datasets"]:
        if not d.get("date_acquired") and "scripts/" in d["importer"]:
            script = re.search(r"scripts/([\w]+\.py)", d["importer"]).group(1)
            assert (ROOT / "apps" / "api" / "scripts" / script).is_file(), (d["id"], script)


def test_data_readiness_document_is_in_sync_with_the_manifest():
    result = subprocess.run([sys.executable, str(ROOT / "apps" / "api" / "scripts" / "generate_data_readiness.py"), "--check"], cwd=ROOT / "apps" / "api")
    assert result.returncode == 0, "docs/DATA_READINESS.md is stale: run scripts/generate_data_readiness.py"


def test_source_verification_document_is_in_sync():
    result = subprocess.run([sys.executable, str(ROOT / "apps" / "api" / "scripts" / "generate_source_verification.py"), "--check"], cwd=ROOT / "apps" / "api")
    assert result.returncode == 0, "docs/SOURCE_VERIFICATION.md is stale: run scripts/generate_source_verification.py"


def test_pending_data_audit_document_is_in_sync():
    result = subprocess.run([sys.executable, str(ROOT / "apps" / "api" / "scripts" / "generate_pending_data_audit.py"), "--check"], cwd=ROOT / "apps" / "api")
    assert result.returncode == 0, "docs/PENDING_DATA_AUDIT.md is stale: run scripts/generate_pending_data_audit.py"


def test_domain_dashboard_in_the_readiness_document_matches_the_registry():
    import json
    registry = json.loads((ROOT / "data" / "domain-readiness.json").read_text(encoding="utf-8"))
    text = (ROOT / "docs" / "DATA_READINESS.md").read_text(encoding="utf-8")
    for d in registry["domains"]:
        assert f"| **{d['label']}** | **{d['status']}** |" in text, d["domain"]
    assert not any(d["status"] == "READY" and d["blockers"] for d in registry["domains"])


# ---------------------------------------------------------------- the checks themselves catch violations
def test_manifest_without_provenance_fails():
    assert any("provenance" in p for p in validate_manifest(entry(provenance="")))


def test_public_dataset_without_licence_status_fails():
    bad = entry()
    bad["datasets"][0]["license"] = {"name": "x"}
    assert any("license.status" in p for p in validate_manifest(bad))


@pytest.mark.parametrize("status", ["LICENSE_REQUIRED", "PROVENANCE_UNCLEAR", "UNKNOWN"])
def test_publishing_with_an_uncleared_licence_fails(status):
    bad = entry()
    bad["datasets"][0]["license"] = {"name": "x", "status": status}
    assert any("not publishable" in p or "cannot be published" in p for p in validate_manifest(bad))


def test_duplicate_dataset_ids_fail():
    bad = entry()
    bad["datasets"].append(copy.deepcopy(bad["datasets"][0]))
    assert any("duplicate id" in p for p in validate_manifest(bad))


def test_published_dataset_without_verified_validation_fails():
    assert any("not publishable" in p for p in validate_manifest(entry(validation_status="NEEDS_REVIEW")))


def test_acquired_dataset_without_version_or_importer_fails():
    bad = entry(importer_version="")
    assert any("importer_version" in p for p in validate_manifest(bad))


def test_unknown_target_kind_fails():
    assert any("unknown target kind" in p for p in validate_manifest(entry(targets=[{"kind": "made_up"}])))


def test_hadith_grade_without_source_or_grader_fails():
    problems = grading_problems([{"id": 1, "grader_name": "", "grading_label": "sahih", "source_passage_id": None}, {"id": 2, "grader_name": "X", "grading_label": "hasan", "source_passage_id": "p"}])
    assert len(problems) == 2 and all("grading 1" in p for p in problems)


def test_ai_citation_to_nonexistent_source_fails():
    assert citation_problems(["[1]", "[7]"], ["[1]", "[2]"]) == ["citation [7] points to a nonexistent source"]
    assert citation_problems(["[1]"], ["[1]"]) == []


def test_published_record_missing_metadata_fails():
    problems = missing_metadata([{"id": "a", "source": "s", "license": "", "provenance": "p"}], ("source", "license", "provenance"), "record")
    assert problems == ["record a: missing license"]


def test_duplicate_identifiers_are_found():
    assert find_duplicates(["a", "b", "a", "c", "b"]) == ["a", "b"]


class _Dataset:
    def __init__(self, **kw):
        self.__dict__.update(dict(publication_status="published", enabled=True, license_status="VERIFIED_OPEN", validation_status="VERIFIED", rights_confirmation=None) | kw)


@pytest.mark.parametrize("kw,expected", [({}, True), ({"enabled": False}, False), ({"publication_status": "staged"}, False), ({"license_status": "LICENSE_REQUIRED"}, False),
                                          ({"validation_status": "NEEDS_REVIEW"}, False)])
def test_visibility_requires_enabled_published_licensed_and_verified(kw, expected):
    assert desired_visibility(_Dataset(**kw)) is expected
    assert desired_visibility(None) is False


def test_published_json_schemas_match_the_models():
    result = subprocess.run([sys.executable, str(ROOT / "apps" / "api" / "scripts" / "export_schemas.py"), "--check"], cwd=ROOT / "apps" / "api")
    assert result.returncode == 0, "data/contracts/*.json is stale: run scripts/export_schemas.py"


def test_manifest_path_works_in_the_container_layout(monkeypatch, tmp_path):
    """In the production image the module lives at /app/app/services/manifest.py (too shallow for parents[4]); the data dir is found via WOI_MANIFEST_PATH."""
    import app.services.manifest as manifest_module
    (tmp_path / "source-manifest.json").write_text("{}")

    class Shallow:
        def resolve(self):
            return self

        @property
        def parents(self):
            return [Path("/app/app/services"), Path("/app/app"), Path("/app")]
    monkeypatch.setattr(manifest_module, "Path", lambda *a, **k: Shallow() if a == (manifest_module.__file__,) else Path(*a, **k))
    monkeypatch.setenv("WOI_MANIFEST_PATH", str(tmp_path / "source-manifest.json"))
    assert manifest_module.manifest_path() == tmp_path / "source-manifest.json"
