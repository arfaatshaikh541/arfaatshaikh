from pathlib import Path

from app.schemas.quran import QuranImportAyahCreate, QuranImportManifestCreate


def test_import_manifest_requires_sha256() -> None:
    payload = QuranImportManifestCreate(
        text_edition_id="11111111-1111-4111-8111-111111111111",
        manifest_version="1",
        expected_ayah_count=6236,
        manifest_sha256="a" * 64,
    )
    assert payload.expected_surah_count == 114
    assert len(payload.manifest_sha256) == 64


def test_import_ayah_preserves_arabic_diacritics() -> None:
    text = "بِسْمِ"
    payload = QuranImportAyahCreate(
        surah_number=1,
        ayah_number=1,
        arabic_text=text,
        source_passage_id="22222222-2222-4222-8222-222222222222",
    )
    assert payload.arabic_text == text


def test_import_pipeline_is_fail_closed() -> None:
    root = Path(__file__).resolve().parents[1]
    service = (root / "app/services/quran_imports.py").read_text()
    assert 'batch.status != "approved"' in service
    assert "source.approved_for_retrieval" in service
    assert "manifest checksum mismatch" in service
    assert "quran_edition_already_populated" in service


def test_import_events_are_append_only() -> None:
    root = Path(__file__).resolve().parents[1]
    migration = (root / "alembic/versions/20260725_0010_quran_import_pipeline.py").read_text()
    assert "trg_quran_import_events_immutable" in migration
    assert "append-only" in migration
