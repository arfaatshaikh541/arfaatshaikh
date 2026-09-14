from pathlib import Path
import pytest
from pydantic import ValidationError

from app.schemas.tafsir import TafsirEntryCreate


def test_tafsir_models_are_registered():
    text = Path("app/models/tafsir.py").read_text()
    for table in ["tafsir_authors", "tafsir_collections", "tafsir_editions", "tafsir_volumes", "tafsir_sections", "tafsir_entries", "tafsir_translation_editions", "tafsir_translations"]:
        assert table in text


def test_publication_is_fail_closed():
    text = Path("app/models/tafsir.py").read_text()
    assert text.count('server_default="false"') >= 8


def test_arabic_text_rejects_latin_letters():
    with pytest.raises(ValidationError):
        TafsirEntryCreate(surah_number=1, start_ayah_number=1, entry_type="ayah", arabic_text="not Arabic", source_passage_id="00000000-0000-0000-0000-000000000001")


def test_ayah_range_is_ordered():
    with pytest.raises(ValidationError):
        TafsirEntryCreate(surah_number=2, start_ayah_number=10, end_ayah_number=5, entry_type="ayah_range", arabic_text="تفسير", source_passage_id="00000000-0000-0000-0000-000000000001")


def test_tafsir_routes_are_registered():
    router = Path("app/api/router.py").read_text()
    routes = Path("app/api/routes/tafsir.py").read_text()
    assert "tafsir_router" in router
    assert 'prefix="/tafsir"' in routes
    assert '"/entries/{reference}"' in routes


def test_source_gate_is_fail_closed():
    service = Path("app/services/tafsir.py").read_text()
    assert 'review_status != "approved"' in service
    assert 'ingestion_status != "ready"' in service
    assert "approved_for_retrieval" in service
    assert "is_current" in service
