"""Source probes, recitation rights, geographic coverage, review decisions, the Arabic seed and the rights ledger."""
import json
import urllib.error
from types import SimpleNamespace

import pytest

from app.services import source_probe
from app.services.coverage import build_coverage, country_label, status_token
from app.services.data_contracts import SEERAH_RELIABILITY
from app.services.manifest import manifest_path
from app.services.recitation_rights import HOSTED_WITH_PERMISSION, NOT_PLAYABLE, OFFLINE_WITH_PERMISSION, STREAMED_EXTERNALLY, delivery_class, rights_problems

DATA = manifest_path().parent


# ---------------------------------------------------------------- probes
class _Resp:
    status = 200
    headers = {"Content-Type": "text/plain"}

    def __init__(self, body=b"ok"):
        self._body = body

    def read(self, n=-1):
        return self._body

    def geturl(self):
        return "https://example.org/"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_probe_records_a_proxy_refusal_as_unreachable_not_as_licence_evidence(monkeypatch):
    def refuse(*a, **k):
        raise urllib.error.URLError("Tunnel connection failed: 403 Forbidden")
    monkeypatch.setattr(source_probe.urllib.request, "urlopen", refuse)
    r = source_probe.http_check("https://blocked.example/")
    assert r["reachable"] is False and r["error"].startswith("proxy_or_policy_refusal")
    record = source_probe.probe_target({"source_id": "x", "urls": {"main": "https://blocked.example/", "licence": "https://blocked.example/l"}})
    assert record["accessible"] is False and record["licence_page_accessible"] is False and "not permission" in record["rights_note"]


def test_probe_success_does_not_imply_rights(monkeypatch):
    monkeypatch.setattr(source_probe.urllib.request, "urlopen", lambda *a, **k: _Resp())
    record = source_probe.probe_target({"source_id": "x", "urls": {"main": "https://a.example/", "data": "https://a.example/d.json"}})
    assert record["accessible"] and record["data_accessible"] and "Reachability is not permission" in record["rights_note"]
    assert source_probe.summarise([record])["accessible"] == 1


def test_probe_http_error_status_counts_as_reachable_but_not_accessible(monkeypatch):
    def forbidden(*a, **k):
        raise urllib.error.HTTPError("https://a.example/", 403, "Forbidden", {}, None)
    monkeypatch.setattr(source_probe.urllib.request, "urlopen", forbidden)
    r = source_probe.http_check("https://a.example/")
    assert r["reachable"] is True and r["status"] == 403
    assert source_probe.probe_target({"source_id": "x", "urls": {"main": "https://a.example/"}})["accessible"] is False


def test_probe_targets_file_is_well_formed():
    targets = json.loads((DATA / "probe-targets.json").read_text(encoding="utf-8"))["targets"]
    ids = [t["source_id"] for t in targets]
    assert len(ids) == len(set(ids)) and len(ids) >= 40
    for t in targets:
        assert t["urls"].get("main", "").startswith("https://"), t["source_id"]
        assert all(u.startswith("https://") for u in t["urls"].values()), t["source_id"]


def test_recorded_probe_results_never_claim_rights():
    path = DATA / "source-probes.json"
    if not path.exists():
        pytest.skip("no probe results recorded yet")
    for record in json.loads(path.read_text(encoding="utf-8"))["records"]:
        assert "Reachability is not permission" in record["rights_note"], record["source_id"]


# ---------------------------------------------------------------- recitation rights
def rights(**over):
    base = dict(delivery_mode="external_link", license_status="UNKNOWN", rights_authorization=None, source_url="https://holder.example/r", recording_owner="Holder",
                streaming_allowed=True, download_allowed=False, redistribution_allowed=False, caching_allowed=False, offline_allowed=False)
    base.update(over)
    return SimpleNamespace(**base)


def test_nothing_is_playable_until_rights_are_recorded():
    assert delivery_class(rights(recording_owner=None)) == NOT_PLAYABLE
    assert delivery_class(rights(streaming_allowed=False)) == NOT_PLAYABLE
    assert any("recording_owner" in p for p in rights_problems(rights(recording_owner=" ")))


def test_external_playback_is_the_fallback_and_cannot_be_cached_or_offline():
    assert delivery_class(rights()) == STREAMED_EXTERNALLY
    assert delivery_class(rights(source_url=None)) == NOT_PLAYABLE
    assert delivery_class(rights(caching_allowed=True)) == NOT_PLAYABLE
    assert delivery_class(rights(offline_allowed=True, caching_allowed=True, download_allowed=True)) == NOT_PLAYABLE


def test_hosting_needs_licence_authorisation_and_redistribution():
    hosted = dict(delivery_mode="hosted", license_status="OWNER_PERMISSION_GRANTED", rights_authorization="Written permission from the holder, 2026-01-01", redistribution_allowed=True)
    assert delivery_class(rights(**hosted)) == HOSTED_WITH_PERMISSION
    assert delivery_class(rights(**{**hosted, "license_status": "UNKNOWN"})) == NOT_PLAYABLE
    assert delivery_class(rights(**{**hosted, "rights_authorization": ""})) == NOT_PLAYABLE
    assert delivery_class(rights(**{**hosted, "redistribution_allowed": False})) == NOT_PLAYABLE


def test_offline_needs_download_and_caching_rights_too():
    hosted = dict(delivery_mode="hosted", license_status="OWNER_PERMISSION_GRANTED", rights_authorization="Written permission", redistribution_allowed=True, offline_allowed=True)
    assert delivery_class(rights(**hosted)) == NOT_PLAYABLE
    assert delivery_class(rights(**hosted, download_allowed=True, caching_allowed=True)) == OFFLINE_WITH_PERMISSION


# ---------------------------------------------------------------- coverage
def dom(domain, published=0, hidden=0, coverage="NONE"):
    return {"domain": domain, "label": domain, "status": "EMPTY", "scope": "scope text", "coverage": coverage, "records": {"published": published, "hidden": hidden, "total": published + hidden}}


def test_coverage_never_implies_worldwide():
    result = build_coverage([dom("quran", 6236, 0, "FULL"), dom("mosques", 5), dom("jobs"), dom("tafsir", 0, 100), dom("charities", 0, 3), dom("health", 2)],
                            [{"type": "mosque", "country": "DZ", "published": 5, "city_known": 4, "regions": 2},
                             {"type": "health", "country": "DZ", "published": 1, "city_known": 1, "regions": 1}, {"type": "health", "country": "GB", "published": 1, "city_known": 0, "regions": 0}])
    by = {d["domain"]: d for d in result["domains"]}
    assert by["quran"]["coverage_status"] == "GLOBAL" and by["quran"]["content_scope"] == "FULL"
    assert by["mosques"]["coverage_status"] == "ALGERIA_ONLY" and by["mosques"]["countries"][0]["listings_without_city"] == 1
    assert by["jobs"]["coverage_status"] == "NO_VERIFIED_DATA"
    assert by["tafsir"]["coverage_status"] == "HIDDEN_PENDING_RIGHTS"
    assert by["charities"]["coverage_status"] == "HIDDEN_PENDING_RIGHTS"
    assert by["health"]["coverage_status"] == "REGIONAL"
    assert "worldwide" in result["statement"]


def test_unknown_country_codes_are_shown_as_codes_not_guessed():
    assert country_label("DZ") == "Algeria" and country_label("ZZ") == "ZZ"
    assert status_token("BA") == "BOSNIA_AND_HERZEGOVINA_ONLY" and status_token("ZZ") == "ZZ_ONLY"


# ---------------------------------------------------------------- contracts and seeds
def test_seerah_reliability_can_say_unknown():
    assert {"established", "well_known_disputed", "weak_reports", "unknown"} == set(SEERAH_RELIABILITY)


def test_arabic_seed_has_every_string_awaiting_native_review():
    seed = json.loads((DATA / "arabic-strings.json").read_text(encoding="utf-8"))
    groups = {"GENERAL_UI", "QURAN", "HADITH", "FIQH", "AQEEDAH", "TAFSIR", "SCHOLARSHIP", "DIRECTORY"}
    keys = [s["key"] for s in seed["strings"]]
    assert len(keys) == len(set(keys)) >= 137
    assert all(s["group"] in groups and s["arabic"] for s in seed["strings"])
    assert "no reviewer has approved" in seed["note"]
    assert not any("approved" in str(s.get("state", "")).lower() for s in seed["strings"])


# ---------------------------------------------------------------- rights ledger
def test_the_real_ledger_agrees_with_the_manifest():
    from app.services.manifest import load_manifest
    from app.services.rights_ledger import load_ledger, validate_ledger
    assert validate_ledger(load_ledger(), load_manifest()) == []


def test_ledger_rules_catch_unsupported_publication():
    import copy

    from app.services.manifest import load_manifest
    from app.services.rights_ledger import load_ledger, validate_ledger
    manifest, ledger = load_manifest(), load_ledger()
    bad = copy.deepcopy(ledger)
    bad["datasets"]["hadith-bukhari-arabic"]["decision"] = "PUBLISH"
    assert any("PUBLISH needs redistribution_allowed ESTABLISHED" in p for p in validate_ledger(bad, manifest))
    bad = copy.deepcopy(ledger)
    del bad["datasets"]["directory-mosques"]
    assert any("directory-mosques: public without" in p for p in validate_ledger(bad, manifest))
    bad = copy.deepcopy(ledger)
    bad["datasets"]["quran-arabic-uthmani-hafs"]["evidence"] = [{"claim": "x", "url": "http://insecure", "retrieved": "today"}]
    assert any("evidence entry" in p for p in validate_ledger(bad, manifest))
    bad = copy.deepcopy(ledger)
    bad["datasets"]["tafsir-english"]["decision"] = "KEEP_HIDDEN"
    mutated_manifest = copy.deepcopy(manifest)
    next(d for d in mutated_manifest["datasets"] if d["id"] == "tafsir-english")["public"] = True
    assert any("KEEP_HIDDEN but the manifest publishes it" in p for p in validate_ledger(bad, mutated_manifest))


def test_unresolved_rights_are_hidden_and_never_published():
    from app.services.manifest import load_manifest
    from app.services.rights_ledger import load_ledger
    manifest, ledger = load_manifest(), load_ledger()
    for ident in ("hadith-bukhari-arabic", "hadith-muslim-arabic", "hadith-nawawi40-arabic", "hadith-bukhari-english", "hadith-muslim-english", "hadith-grading",
                  "tafsir-arabic-classical", "tafsir-arabic-modern", "tafsir-english"):
        d = next(x for x in manifest["datasets"] if x["id"] == ident)
        assert not d["public"] and d["publication_status"] != "published", ident
        assert ledger["datasets"][ident]["decision"] == "KEEP_HIDDEN", ident


def test_companion_ledgers_record_every_row_as_not_established():
    tafsir = json.loads((DATA / "rights-ledger-tafsir.json").read_text(encoding="utf-8"))
    grades = json.loads((DATA / "rights-ledger-hadith-gradings.json").read_text(encoding="utf-8"))
    assert tafsir["counts"]["editions"] == len(tafsir["editions"]) >= 100
    assert all(r["licence"] == "NOT_DOCUMENTED" and r["publisher"] == "NOT_DOCUMENTED" for r in tafsir["editions"])
    assert grades["totals"]["grades"] > 60000 and all(r["grading_rights"] == "NOT_ESTABLISHED" and r["page"] == "NOT_DOCUMENTED" for r in grades["graders"])
    assert "cannot grant rights" in grades["finding"] or "not the graders' published gradings" in grades["finding"]
