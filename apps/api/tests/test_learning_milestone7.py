import pytest
from app.services.learning import (
 CERTIFICATE_DISCLAIMER, LearningPolicyError, calculate_score, completion_percent,
 deterministic_recommendations, grade_objective, select_recorded_score, transition_content,
 validate_certificate_eligibility, validate_child_defaults, validate_publication,
)

def approvals(): return {'islamic':'approved','editorial':'approved','publisher':'approved'}
def reviewers(): return {'islamic':'r1','editorial':'r2','publisher':'r3'}

def test_happy_publication_contract():
 validate_publication(evidence_ids=['p1'],reviews=approvals(),author_id='author',reviewer_ids=reviewers())

def test_publication_fails_without_evidence():
 with pytest.raises(LearningPolicyError): validate_publication(evidence_ids=[],reviews=approvals(),author_id='author',reviewer_ids=reviewers())

def test_author_cannot_self_approve():
 r=reviewers(); r['islamic']='author'
 with pytest.raises(LearningPolicyError): validate_publication(evidence_ids=['p1'],reviews=approvals(),author_id='author',reviewer_ids=r)

def test_translation_cannot_change_structure_or_evidence():
 with pytest.raises(LearningPolicyError): validate_publication(evidence_ids=['p1'],reviews=approvals(),author_id='a',reviewer_ids=reviewers(),translation_structure_hash='x',canonical_structure_hash='y')
 with pytest.raises(LearningPolicyError): validate_publication(evidence_ids=['p1'],reviews=approvals(),author_id='a',reviewer_ids=reviewers(),translation_evidence_hash='x',canonical_evidence_hash='y')

def test_governed_transition():
 assert transition_content('draft','author_review')=='author_review'
 assert transition_content('published','archived')=='archived'
 with pytest.raises(LearningPolicyError): transition_content('draft','published')

def test_exact_objective_grading():
 assert grade_objective(correct_option_ids={'a','b'},selected_option_ids={'a','b'},points=3)==3
 assert grade_objective(correct_option_ids={'a','b'},selected_option_ids={'a'},points=3)==0

def test_scoring_policies_are_deterministic():
 assert calculate_score(7,10)==70
 assert select_recorded_score([60,90,70],'highest')==90
 assert select_recorded_score([60,90,70],'latest')==70
 assert select_recorded_score([60,90,70],'first')==60
 assert select_recorded_score([60,90,70],'average')==73

def test_completion_is_bounded():
 assert completion_percent(3,4)==75
 assert completion_percent(8,4)==100
 assert completion_percent(0,0)==0

def test_certificate_boundary():
 assert 'not an ijazah' in CERTIFICATE_DISCLAIMER
 validate_certificate_eligibility(course_complete=True,assessment_passed=True)
 with pytest.raises(LearningPolicyError): validate_certificate_eligibility(course_complete=True,assessment_passed=False)

def test_recommendations_do_not_use_piety_or_sect():
 items=deterministic_recommendations([
  {'id':'b','title':'B','languages':['ar'],'prerequisite_match':10,'piety':999,'sect':'x'},
  {'id':'a','title':'A','languages':['en'],'prerequisite_match':5,'piety':0,'sect':'y'},
 ],'en',set())
 assert items[0]['id']=='a'
 assert items[0]['reason_code']=='language_and_prerequisite_fit'

def test_child_defaults_fail_closed():
 validate_child_defaults(public_profile=False,discussion_enabled=False,certificate_public=False)
 with pytest.raises(LearningPolicyError): validate_child_defaults(public_profile=True,discussion_enabled=False,certificate_public=False)

def test_learning_tables_registered():
 import app.models.learning
 from app.db.base import Base
 required={'learning_paths','courses','course_versions','course_modules','lessons','lesson_sections','lesson_evidence','content_reviews','lesson_translations','assessments','assessment_questions','question_options','question_evidence','course_enrollments','lesson_progress','assessment_attempts','learner_notes','learning_certificates','guardian_relationships','learning_recommendation_events'}
 assert required <= set(Base.metadata.tables)

def test_learner_notes_never_evidence_by_default():
 from app.models.learning import LearnerNote
 assert LearnerNote.__table__.c.private.default.arg is True
 assert LearnerNote.__table__.c.eligible_as_evidence.default.arg is False
