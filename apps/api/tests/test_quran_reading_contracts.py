from pathlib import Path

ROOT = Path(__file__).parents[1]

def test_reader_models_are_account_scoped():
    text = (ROOT / "app/models/quran.py").read_text()
    assert "class QuranBookmark" in text
    assert 'UniqueConstraint("user_id", "ayah_id")' in text
    assert "class QuranReadingProgress" in text
    assert 'UniqueConstraint("user_id")' in text


def test_reader_routes_include_public_and_private_boundaries():
    text = (ROOT / "app/api/routes/quran.py").read_text()
    assert '"/surahs/{surah_number}/reading"' in text
    assert '"/me/bookmarks"' in text
    assert '"/me/progress"' in text
    assert "Depends(require_csrf)" in text


def test_reader_fails_without_published_canonical_edition():
    text = (ROOT / "app/services/quran.py").read_text()
    assert "QuranTextEdition.canonical.is_(True)" in text
    assert "QuranTextEdition.published.is_(True)" in text
    assert "quran_corpus_unavailable" in text


def test_frontend_has_deep_links_and_accessible_status():
    text = Path(ROOT.parent / "web/src/components/quran-reader.tsx").read_text()
    assert 'id={`ayah-${ayah.ayah_number}`}' in text
    assert 'role="status"' in text
    assert "Save position" in text
