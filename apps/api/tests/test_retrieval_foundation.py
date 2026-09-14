import pytest

from app.services.retrieval import EvidenceContract, chunk_exact_text, filter_active_candidates, sha256_text, validate_evidence_contract, validate_projection_eligibility


def test_projection_is_fail_closed():
    eligible, failures = validate_projection_eligibility(published=True, source_approved=True, ingestion_ready=True, retrieval_approved=False, passage_current=True, attribution_present=True, redistribution_allowed=True)
    assert not eligible
    assert failures == ('retrieval_not_approved',)


def test_projection_requires_every_gate():
    eligible, failures = validate_projection_eligibility(published=True, source_approved=True, ingestion_ready=True, retrieval_approved=True, passage_current=True, attribution_present=True, redistribution_allowed=True)
    assert eligible and failures == ()


def test_chunking_preserves_exact_text_and_offsets():
    text = ('A' * 500) + '\n\n' + ('B' * 500)
    chunks = chunk_exact_text(text, max_chars=600)
    assert ''.join(c.text for c in chunks) == text
    assert chunks[0].start_offset == 0
    assert chunks[-1].end_offset == len(text)
    assert all(sha256_text(c.text) == c.text_sha256 for c in chunks)


def test_evidence_checksum_is_mandatory():
    evidence = EvidenceContract('c','d','quran','2:255','e','p','exact','0'*64,'attr','lic')
    with pytest.raises(ValueError, match='checksum'):
        validate_evidence_contract(evidence)


def test_active_candidate_filter_rechecks_source_state():
    candidates = [
        {'id': 1, 'document_active': True, 'chunk_active': True, 'source_approved': True, 'passage_current': True, 'retrieval_approved': True},
        {'id': 2, 'document_active': True, 'chunk_active': True, 'source_approved': False, 'passage_current': True, 'retrieval_approved': True},
    ]
    assert [c['id'] for c in filter_active_candidates(candidates)] == [1]
