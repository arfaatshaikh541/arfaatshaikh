from pathlib import Path
import pytest
from pydantic import ValidationError
from app.schemas.hadith import HadithCollectionCreate, HadithGradingCreate, HadithNarrationCreate
from uuid import uuid4


def test_hadith_models_are_provenance_linked_and_unpublished_by_default():
    text = Path("app/models/hadith.py").read_text()
    assert 'ForeignKey("source_editions.id"' in text
    assert text.count('ForeignKey("source_passages.id"') >= 6
    assert text.count('server_default="false"') >= 5


def test_narration_rejects_latin_matn():
    with pytest.raises(ValidationError):
        HadithNarrationCreate(book_id=uuid4(), collection_hadith_number=1, arabic_matn="not hadith", source_passage_id=uuid4())


def test_grading_requires_attribution_and_known_label():
    with pytest.raises(ValidationError):
        HadithGradingCreate(grader_name="", grading_label="certain", grading_text="x", source_passage_id=uuid4())


def test_collection_key_is_stable_slug():
    with pytest.raises(ValidationError):
        HadithCollectionCreate(source_edition_id=uuid4(), collection_key="Bad Key", arabic_title="عنوان", display_title="Title", compiler_name="Compiler")


def test_routes_are_registered():
    router = Path("app/api/router.py").read_text()
    routes = Path("app/api/routes/hadith.py").read_text()
    assert "router.include_router(hadith_router)" in router
    assert 'prefix="/hadith"' in routes
    assert '/admin/narrations/{narration_id}/gradings' in routes
