from pathlib import Path
from uuid import uuid4
import pytest
from pydantic import ValidationError

from app.schemas.hadith import HadithTranslationEditionCreate, HadithGradingImportItemCreate, HadithGovernedReviewCreate

ROOT = Path(__file__).resolve().parents[1]


def test_translation_key_is_stable_slug():
    payload = HadithTranslationEditionCreate(source_edition_id=uuid4(), translation_key="english-reviewed", language="en", translator_name="Attributed Translator", attribution_text="Licensed and attributed translation edition")
    assert payload.translation_key == "english-reviewed"
    with pytest.raises(ValidationError):
        HadithTranslationEditionCreate(source_edition_id=uuid4(), translation_key="Bad Key", language="en", translator_name="Translator", attribution_text="Valid attribution text")


def test_grading_labels_are_constrained_but_opinions_remain_attributed():
    payload = HadithGradingImportItemCreate(narration_id=uuid4(), grader_name="Named Scholar", grading_label="mixed", grading_text="Attributed wording", source_passage_id=uuid4())
    assert payload.grader_name == "Named Scholar"
    assert payload.grading_label == "mixed"


def test_governed_review_requires_rationale():
    with pytest.raises(ValidationError):
        HadithGovernedReviewCreate(decision="approved", rationale="too short")


def test_routes_expose_reading_and_governed_imports():
    text = (ROOT / "app/api/routes/hadith.py").read_text()
    for route in ["translation-imports", "grading-imports", "chapters/{chapter_number}"]:
        assert route in text


def test_reading_payload_does_not_create_consensus_grade():
    text = (ROOT / "app/services/hadith_governance.py").read_text()
    assert '"gradings":' in text
    assert "consensus" not in text.lower()
    assert "final_grade" not in text


def test_migration_contains_governance_tables():
    text = (ROOT / "alembic/versions/20260725_0016_hadith_translation_and_reading.py").read_text()
    for table in ["hadith_translation_editions", "hadith_translations", "hadith_translation_import_batches", "hadith_grading_import_batches", "hadith_grading_import_items"]:
        assert table in text
