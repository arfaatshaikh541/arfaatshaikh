from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.tafsir import TafsirImportEntryCreate
from app.services.tafsir_imports import REQUIRED_REVIEW_DOMAINS


def test_required_review_domains_are_separated():
    assert REQUIRED_REVIEW_DOMAINS == {"tafsir_text", "source_provenance", "arabic_language"}


def test_import_rejects_latin_text():
    with pytest.raises(ValidationError):
        TafsirImportEntryCreate(surah_number=1, entry_type="surah", arabic_text="generated tafsir", source_passage_id=uuid4())


def test_ayah_commentary_requires_start_ayah():
    with pytest.raises(ValidationError):
        TafsirImportEntryCreate(surah_number=2, entry_type="ayah", arabic_text="تفسير", source_passage_id=uuid4())


def test_migration_has_append_only_events():
    text = Path("alembic/versions/20260725_0019_tafsir_import_pipeline.py").read_text()
    assert "tafsir_import_events_append_only" in text
    assert "prevent_tafsir_import_event_mutation" in text


def test_routes_expose_controlled_pipeline():
    text = Path("app/api/routes/tafsir.py").read_text()
    for route in ["/admin/imports", "/validate", "/review-assignments", "/publish", "/me/review-queue"]:
        assert route in text

def test_translation_pipeline_is_staged_and_governed():
    routes = Path("app/api/routes/tafsir.py").read_text()
    models = Path("app/models/tafsir.py").read_text()
    assert "/admin/translation-imports" in routes
    assert "TafsirTranslationImportBatch" in models
    assert "TafsirTranslationImportReview" in models
