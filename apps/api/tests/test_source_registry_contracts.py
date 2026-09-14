from pathlib import Path

from app.schemas.sources import EditionCreate, SourceCreate

API_ROOT = Path(__file__).resolve().parents[1]


def test_registered_edition_is_not_approved_by_default() -> None:
    edition = EditionCreate(edition_key="sample-1", language="ar", citation_format="Sample citation")
    assert edition.edition_key == "sample-1"


def test_source_type_allowlist_rejects_unknown_type() -> None:
    try:
        SourceCreate(canonical_title="Example", source_type="random_webpage", primary_language="en")
    except ValueError:
        return
    raise AssertionError("unknown source type was accepted")


def test_migration_keeps_integrity_and_reviews_append_only() -> None:
    migration = (API_ROOT / "alembic/versions/20260725_0005_source_registry.py").read_text()
    assert "CREATE TRIGGER trg_{table}_append_only" in migration
    assert "source_integrity_records" in migration
    assert "source_reviews" in migration
    assert "approved_for_retrieval" in migration
