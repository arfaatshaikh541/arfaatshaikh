from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_claim_links_use_exact_spans_and_immutable_passages():
    models = (ROOT / "app/models/sources.py").read_text()
    service = (ROOT / "app/services/source_provenance.py").read_text()
    assert "citation_start" in models and "citation_end" in models
    assert "citation_end > citation_start" in models
    assert "payload.citation_end > len(passage.content)" in service


def test_supersession_fails_closed():
    service = (ROOT / "app/services/source_provenance.py").read_text()
    assert 'old.ingestion_status = "retired"' in service
    assert "old.approved_for_retrieval = False" in service
    assert "old.source_id != new.source_id" in service


def test_corrections_require_replacement_when_accepted():
    service = (ROOT / "app/services/source_provenance.py").read_text()
    assert 'payload.status == "accepted" and payload.replacement_passage_id is None' in service


def test_only_one_active_policy_is_preserved_by_service():
    service = (ROOT / "app/services/source_provenance.py").read_text()
    assert 'ApprovalPolicy.status == "active"' in service
    assert 'current.status = "retired"' in service
    assert 'policy.status = "active"' in service


def test_migration_contains_provenance_governance_tables():
    migration = (ROOT / "alembic/versions/20260725_0007_claim_provenance.py").read_text()
    for table in ("source_claims", "claim_passage_links", "passage_corrections", "source_supersessions", "approval_policies"):
        assert f'"{table}"' in migration
