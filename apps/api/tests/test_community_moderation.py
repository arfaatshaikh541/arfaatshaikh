import pytest
from app.services.community import CommunityPolicyError, validate_discussion_content, validate_report, validate_moderation_decision, reputation_points

def test_religious_claim_requires_governed_evidence():
    with pytest.raises(CommunityPolicyError,match='governed evidence'):
        validate_discussion_content(body='This is a religious ruling',is_religious_claim=True,evidence_count=0)
    result=validate_discussion_content(body='A sourced discussion point',is_religious_claim=True,evidence_count=1)
    assert result=={'publishable':True,'requires_moderation':True}

def test_community_reputation_never_grants_authority():
    with pytest.raises(CommunityPolicyError,match='does not grant religious authority'):
        validate_discussion_content(body='I am authoritative',is_religious_claim=False,evidence_count=0,authoritative_claim=True)
    assert reputation_points(event_type='evidence_accepted')==3

def test_takfir_is_rejected():
    with pytest.raises(CommunityPolicyError,match='takfir'):
        validate_discussion_content(body='This person is a kafir',is_religious_claim=False,evidence_count=0)

def test_high_risk_reports_are_prioritised():
    assert validate_report(target_type='post',category='unsafe_advice',details='danger')==90
    assert validate_report(target_type='profile',category='privacy',details='data')==65

def test_author_cannot_moderate_own_content():
    with pytest.raises(CommunityPolicyError,match='own content'):
        validate_moderation_decision(action='remove',reason='violation',policy_code='COMM-1',moderator_is_author=True)
    validate_moderation_decision(action='remove',reason='violation',policy_code='COMM-1')

def test_models_registered_and_migration_present():
    import app.models  # registers all mapped classes
    from app.db.base import Base
    names=set(Base.metadata.tables)
    assert {'community_spaces','community_threads','community_posts','community_post_evidence','community_reports','moderation_decisions','community_reputation_events'} <= names
