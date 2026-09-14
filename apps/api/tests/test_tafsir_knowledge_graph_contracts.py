from pathlib import Path
import re
from uuid import uuid4
import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]


def read(path): return (ROOT / path).read_text()


def test_migration_has_topic_and_cross_reference_tables():
    text = read("alembic/versions/20260725_0020_knowledge_graph.py")
    for table in ("knowledge_topics", "knowledge_topic_aliases", "knowledge_cross_references"):
        assert f'op.create_table("{table}"' in text


def test_cross_reference_is_fail_closed_and_evidence_linked():
    text = read("app/models/knowledge_graph.py")
    assert 'default="pending"' in text
    assert 'default=False' in text
    assert 'ForeignKey("source_passages.id"' in text
    assert "editorial_confidence BETWEEN 0 AND 100" in text


def test_public_routes_and_admin_review_exist():
    text = read("app/api/routes/tafsir.py")
    for route in ('/topics', '/references/{entity_type}/{entity_id}', '/ayahs/{surah_number}/{ayah_number}', '/search', '/admin/cross-references/{reference_id}/review'):
        assert route in text


def test_service_requires_published_entities_on_approval():
    text = read("app/services/knowledge_graph.py")
    assert 'await self._entity(row.source_type, row.source_entity_id, True)' in text
    assert 'await self._entity(row.target_type, row.target_entity_id, True)' in text
    assert 'edition.review_status != "approved"' in text


def test_cross_reference_schema_rejects_self_links():
    from app.schemas.tafsir import KnowledgeCrossReferenceCreate
    entity = uuid4()
    with pytest.raises(ValidationError):
        KnowledgeCrossReferenceCreate(source_type="topic", source_entity_id=entity, target_type="topic", target_entity_id=entity, relationship_type="editorial_link", rationale="Documented editorial relationship", evidence_passage_id=uuid4())


def test_no_bundled_religious_content_in_graph_migration():
    text = read("alembic/versions/20260725_0020_knowledge_graph.py")
    assert not re.search(r"INSERT\s+INTO", text, re.I)
