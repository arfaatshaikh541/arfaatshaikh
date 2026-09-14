from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_migration_has_append_only_provenance_records() -> None:
    migration = (ROOT / "alembic/versions/20260725_0006_source_lifecycle.py").read_text()
    assert "source_passages" in migration
    assert "source_lifecycle_events" in migration
    assert "prevent_event_mutation" in migration


def test_retrieval_flag_is_computed_not_accepted_from_request() -> None:
    schemas = (ROOT / "app/schemas/sources.py").read_text()
    routes = (ROOT / "app/api/routes/sources.py").read_text()
    assert "approved_for_retrieval" not in schemas.split("class EditionCreate", 1)[1].split("class AcquisitionCreate", 1)[0]
    assert "evaluate-retrieval" in routes


def test_public_passages_require_retrieval_eligibility() -> None:
    service = (ROOT / "app/services/sources.py").read_text()
    assert "SourceEdition.approved_for_retrieval.is_(True)" in service
    assert "SourcePassage.is_current.is_(True)" in service
