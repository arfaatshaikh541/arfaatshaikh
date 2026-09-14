import pytest
from app.services.scholarly import ScholarlyPolicyError,validate_scholar_profile,validate_review_assignment,validate_review,publication_decision,compare_versions

def test_profile_verification_never_grants_platform_ruling_authority():
    assert validate_scholar_profile(verification_status='verified',may_issue_platform_rulings=False)['religious_authority_granted'] is False
    with pytest.raises(ScholarlyPolicyError,match='does not grant authority'):
        validate_scholar_profile(verification_status='verified',may_issue_platform_rulings=True)

def test_reviews_are_independent_and_islamic_reviewers_cannot_self_assign():
    with pytest.raises(ScholarlyPolicyError,match='own work'):
        validate_review_assignment(review_type='editorial',author_user_id='u1',reviewer_user_id='u1',assigned_by_user_id='u2')
    with pytest.raises(ScholarlyPolicyError,match='self-assign'):
        validate_review_assignment(review_type='islamic',author_user_id='u1',reviewer_user_id='u2',assigned_by_user_id='u2')

def test_islamic_review_requires_evidence_check():
    with pytest.raises(ScholarlyPolicyError,match='must check evidence'):
        validate_review(decision='approve',comments='Looks correct',evidence_checked=False,independent=True,review_type='islamic')
    validate_review(decision='approve',comments='Sources checked',evidence_checked=True,independent=True,review_type='islamic')

def test_publication_fails_closed_until_all_governance_requirements_pass():
    blocked=publication_decision(evidence_count=0,islamic_approvals=1,editorial_approvals=0,source_integrity_approvals=0,rejections=0)
    assert blocked['publishable'] is False and len(blocked['blockers'])==4
    approved=publication_decision(evidence_count=2,islamic_approvals=2,editorial_approvals=1,source_integrity_approvals=1,rejections=0)
    assert approved=={'publishable':True,'blockers':[]}

def test_version_comparison_exposes_content_and_evidence_changes():
    result=compare_versions(old_body='First line',new_body='First revised line',old_evidence_ids=['a','b'],new_evidence_ids=['b','c'])
    assert result['content_changed'] and result['evidence_changed']
    assert result['evidence_added']==['c'] and result['evidence_removed']==['a'] and result['diff']

def test_models_registered_and_migration_present():
    import app.models
    from app.db.base import Base
    assert {'scholar_profiles','scholarly_projects','collaborative_drafts','collaborative_draft_versions','draft_evidence','scholarly_review_assignments','scholarly_reviews','scholarly_approvals'} <= set(Base.metadata.tables)
