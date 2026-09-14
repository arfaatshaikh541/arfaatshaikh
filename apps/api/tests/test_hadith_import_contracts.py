from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.hadith import HadithImportManifestCreate, HadithImportNarrationCreate, HadithImportReviewCreate
from app.services.hadith_imports import calculate_hadith_manifest_sha256


def staged(number: int, digest: str):
    return SimpleNamespace(
        book_number=1,
        chapter_number=1,
        collection_hadith_number=number,
        matn_sha256=digest,
        source_passage_id=uuid4(),
    )


def test_manifest_hash_is_deterministic_by_hierarchy_order():
    first = staged(1, "a" * 64)
    second = staged(2, "b" * 64)
    assert calculate_hadith_manifest_sha256([second, first]) == calculate_hadith_manifest_sha256([first, second])


def test_import_manifest_requires_sha256_and_positive_counts():
    with pytest.raises(ValidationError):
        HadithImportManifestCreate(
            collection_id=uuid4(), manifest_version="1", manifest_sha256="bad",
            expected_book_count=1, expected_chapter_count=0, expected_narration_count=0,
        )


def test_staged_matn_rejects_latin_letters():
    with pytest.raises(ValidationError):
        HadithImportNarrationCreate(
            book_number=1, book_arabic_title="كتاب", book_display_title="Book", book_source_passage_id=uuid4(),
            collection_hadith_number=1, arabic_matn="fabricated text", source_passage_id=uuid4(),
        )


def test_review_requires_reasoned_decision():
    with pytest.raises(ValidationError):
        HadithImportReviewCreate(decision="approved", rationale="short")


def test_models_include_staging_duplicates_reviews_and_events():
    text = Path("app/models/hadith.py").read_text()
    for table in (
        "hadith_import_batches", "hadith_import_narrations", "hadith_import_isnad_nodes",
        "hadith_duplicate_candidates", "hadith_import_review_assignments", "hadith_import_reviews", "hadith_import_events",
    ):
        assert f'__tablename__ = "{table}"' in text
    assert "require_complete_isnad" in text
    assert "source_provenance" in text


def test_publication_requires_all_review_domains_and_rechecks_source():
    text = Path("app/services/hadith_imports.py").read_text()
    assert 'REQUIRED_REVIEW_DOMAINS = {"hadith_text", "isnad", "source_provenance"}' in text
    assert "issubset(approved_domains)" in text
    assert "await self._approved_source(collection.source_edition_id)" in text
    assert "calculate_hadith_manifest_sha256(items) != batch.manifest_sha256" in text


def test_routes_cover_controlled_import_lifecycle():
    text = Path("app/api/routes/hadith.py").read_text()
    for route in (
        '/admin/imports',
        '/admin/imports/{batch_id}/narrations',
        '/admin/imports/{batch_id}/validate',
        '/admin/imports/{batch_id}/review-assignments',
        '/me/review-assignments/{assignment_id}/decision',
        '/admin/imports/{batch_id}/publish',
    ):
        assert route in text


def test_migration_protects_event_log_as_append_only():
    text = Path("alembic/versions/20260725_0015_hadith_import_pipeline.py").read_text()
    assert "hadith_import_events_append_only" in text
    assert "prevent_hadith_import_event_mutation" in text
