import pytest
from app.services.research import ResearchPolicyError, canonical_citation_key, provenance_fingerprint, render_woi_citation, require_workspace_role, validate_annotation, validate_research_item

def test_role_hierarchy():
    require_workspace_role('editor','contributor')
    with pytest.raises(ResearchPolicyError): require_workspace_role('viewer','contributor')

def test_internal_item_requires_identifier():
    with pytest.raises(ResearchPolicyError): validate_research_item(item_type='source_passage',item_id=None,external_url=None)
    validate_research_item(item_type='source_passage',item_id='abc',external_url=None)

def test_external_reference_requires_safe_https():
    with pytest.raises(ResearchPolicyError): validate_research_item(item_type='external_reference',item_id=None,external_url='http://example.com')
    with pytest.raises(ResearchPolicyError): validate_research_item(item_type='external_reference',item_id=None,external_url='https://user:pass@example.com/a')
    validate_research_item(item_type='external_reference',item_id=None,external_url='https://example.com/a')

def test_annotations_never_become_evidence():
    with pytest.raises(ResearchPolicyError): validate_annotation(body='note',visibility='private',eligible_as_evidence=True)
    validate_annotation(body='note',visibility='workspace',eligible_as_evidence=False)

def test_citation_is_deterministic():
    assert canonical_citation_key('Sahih al-Bukhari',2)=='sahih-al-bukhari-2'
    assert render_woi_citation(title='Actions are by intentions',source_label='Sahih al-Bukhari',locator='Hadith 1').startswith('Sahih al-Bukhari, Hadith 1')
    assert provenance_fingerprint({'b':2,'a':1})==provenance_fingerprint({'a':1,'b':2})

def test_migration_chain_and_models_are_registered():
    text=open('alembic/versions/20260725_0030_research_workspace_foundation.py').read()
    assert "down_revision='20260725_0029'" in text
    assert 'research_annotations' in text and 'eligible_as_evidence' in text
    init=open('app/models/__init__.py').read()
    assert 'ResearchWorkspace' in init and 'ResearchCitation' in init
