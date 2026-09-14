from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_translation_import_is_staged_and_provenance_linked():
    models = (ROOT / "app/models/quran.py").read_text()
    assert "class QuranTranslationImportBatch" in models
    assert "class QuranTranslationImportAyah" in models
    assert "source_passage_id" in models
    assert "class QuranTranslationImportReview" in models


def test_translation_publication_rechecks_source_approval():
    service = (ROOT / "app/services/quran_translation_imports.py").read_text()
    assert 'source.review_status != "approved"' in service
    assert "not source.approved_for_retrieval" in service
    assert "translation_source_revoked" in service
    assert "QuranAyahTranslation(" in service


def test_translation_manifest_is_deterministic():
    service = (ROOT / "app/services/quran_translation_imports.py").read_text()
    assert 'order_by(QuranTranslationImportAyah.ayah_id)' in service
    assert 'hashlib.sha256("\\n".join(lines).encode("utf-8")).hexdigest()' in service
    assert "translation_manifest_mismatch" in service


def test_reader_preferences_are_account_scoped():
    models = (ROOT / "app/models/quran.py").read_text()
    routes = (ROOT / "app/api/routes/quran.py").read_text()
    assert "class QuranReaderPreference" in models
    assert 'UniqueConstraint("user_id")' in models
    assert '"/me/preferences"' in routes
    assert "Depends(require_csrf)" in routes


def test_reader_has_copy_citation_preferences_and_bookmark_screen():
    reader = Path(ROOT.parent / "web/src/components/quran-reader.tsx").read_text()
    bookmarks = Path(ROOT.parent / "web/src/components/quran-bookmarks.tsx").read_text()
    assert "copyCitation" in reader
    assert "Qur’an ${ayah.canonical_reference}" in reader
    assert "savePreferences" in reader
    assert "My bookmarks" in bookmarks
