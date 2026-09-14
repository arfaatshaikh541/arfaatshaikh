from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.models import CanonicalKnowledgeEntity, KnowledgeEntityAlias, KnowledgeRelationship, KnowledgeTraversalAudit
from app.schemas.knowledge_network import CanonicalEntityInput, RelationshipInput, SearchRequest, TraversalRequest
from app.services.knowledge_network import GraphEdge, KnowledgeNetworkPolicy


def test_models_registered():
    names = {CanonicalKnowledgeEntity.__tablename__, KnowledgeEntityAlias.__tablename__, KnowledgeRelationship.__tablename__, KnowledgeTraversalAudit.__tablename__}
    assert names <= set(CanonicalKnowledgeEntity.metadata.tables)


def test_published_entity_requires_evidence():
    with pytest.raises(ValidationError):
        CanonicalEntityInput(canonical_key='topic:sabr',entity_type='topic',source_entity_id=uuid4(),english_label='Patience',canonical_url='https://example.com/topics/sabr',publication_status='published')


def test_relationship_rejects_self_link():
    entity=uuid4()
    with pytest.raises(ValidationError):
        RelationshipInput(source_entity_id=entity,target_entity_id=entity,relationship_type='supports',evidence_passage_id=uuid4(),rationale='Evidence based relationship.',confidence=100)


def test_relationship_publication_fails_closed():
    p=RelationshipInput(source_entity_id=uuid4(),target_entity_id=uuid4(),relationship_type='authenticates',evidence_passage_id=uuid4(),rationale='Reviewed authentication evidence.',confidence=80)
    result=KnowledgeNetworkPolicy.validate_relationship(p,source_published=True,target_published=True,evidence_current_and_approved=True)
    assert not result['allowed']


def test_arabic_normalization_and_search_excludes_user_content():
    req=SearchRequest(query='  الصَّبْرُ  ')
    plan=KnowledgeNetworkPolicy.build_search_plan(req)
    assert plan['normalized_query']=='الصبر'
    assert plan['user_generated_content_excluded'] is True


def test_traversal_honours_depth_and_approval():
    a,b,c,d=uuid4(),uuid4(),uuid4(),uuid4(); evidence=uuid4()
    edges=[GraphEdge(a,b,'supports',evidence),GraphEdge(b,c,'explains',evidence),GraphEdge(c,d,'references',evidence,approved=False)]
    result=KnowledgeNetworkPolicy.traverse(TraversalRequest(root_entity_id=a,max_depth=2,max_nodes=10),edges)
    assert result['result_count']==2
    assert {x['entity_id'] for x in result['nodes']}=={str(b),str(c)}
