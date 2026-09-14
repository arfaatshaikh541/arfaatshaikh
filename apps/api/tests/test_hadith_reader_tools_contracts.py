from pathlib import Path

ROOT = Path(__file__).parents[1]

def read(path): return (ROOT / path).read_text()

def test_reader_state_tables_and_constraints_exist():
    text = read("app/models/hadith.py")
    for name in ("HadithBookmark", "HadithReadingHistory", "HadithCitationExport"):
        assert f"class {name}" in text
    assert 'UniqueConstraint("user_id", "narration_id")' in text
    assert "payload_sha256" in text

def test_search_is_published_only_and_filterable():
    text = read("app/services/hadith_reader_tools.py")
    assert "HadithNarration.published.is_(True)" in text
    assert "HadithCollection.published.is_(True)" in text
    assert "HadithGrading.grader_name.ilike" in text
    assert "HadithIsnadNode.transmitted_name.ilike" in text

def test_narrator_profile_preserves_provenance():
    text = read("app/schemas/hadith.py")
    assert "class HadithNarratorProfileView" in text
    assert "source_passage_id: UUID | None" in text
    assert "aliases: list[str]" in text

def test_private_mutations_require_auth_and_csrf():
    text = read("app/api/routes/hadith.py")
    for marker in ('@router.post("/me/bookmarks"', '@router.post("/me/history"', '@router.post("/me/citation-exports"'):
        assert marker in text
    assert text.count("Depends(require_csrf)") >= 15

def test_isnad_and_search_routes_exist():
    text = read("app/api/routes/hadith.py")
    assert '@router.get("/search"' in text
    assert '@router.get("/narrations/{narration_id}/isnad"' in text
    assert '@router.get("/narrators/{narrator_id}"' in text

def test_citation_exports_are_deterministically_hashed():
    text = read("app/services/hadith_reader_tools.py")
    assert "sort_keys=True" in text
    assert "hashlib.sha256(payload.encode(\"utf-8\"))" in text
