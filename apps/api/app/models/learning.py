from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

CONTENT_STATES = "('draft','author_review','islamic_review','editorial_review','approved','published','archived','superseded')"

class LearningPath(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='learning_paths'; __table_args__=(UniqueConstraint('slug', name='uq_learning_paths_slug'), CheckConstraint(f"status IN {CONTENT_STATES}", name='learning_path_status'))
    slug: Mapped[str]=mapped_column(String(120),nullable=False); title: Mapped[str]=mapped_column(String(240),nullable=False); description: Mapped[str]=mapped_column(Text,nullable=False); canonical_language: Mapped[str]=mapped_column(String(8),default='en',server_default='en'); audience: Mapped[str]=mapped_column(String(80),nullable=False); status: Mapped[str]=mapped_column(String(32),default='draft',server_default='draft')

class Course(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='courses'; __table_args__=(UniqueConstraint('slug', name='uq_courses_slug'), CheckConstraint(f"status IN {CONTENT_STATES}", name='course_status'))
    learning_path_id: Mapped[UUID]=mapped_column(ForeignKey('learning_paths.id',ondelete='RESTRICT'),nullable=False); slug: Mapped[str]=mapped_column(String(120),nullable=False); title: Mapped[str]=mapped_column(String(240),nullable=False); summary: Mapped[str]=mapped_column(Text,nullable=False); intended_audience: Mapped[str]=mapped_column(String(120),nullable=False); estimated_minutes: Mapped[int]=mapped_column(Integer,nullable=False); status: Mapped[str]=mapped_column(String(32),default='draft',server_default='draft'); current_version: Mapped[int]=mapped_column(Integer,default=1,server_default='1')

class CourseVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='course_versions'; __table_args__=(UniqueConstraint('course_id','version',name='uq_course_version'),)
    course_id: Mapped[UUID]=mapped_column(ForeignKey('courses.id',ondelete='CASCADE'),nullable=False); version: Mapped[int]=mapped_column(Integer,nullable=False); title: Mapped[str]=mapped_column(String(240),nullable=False); summary: Mapped[str]=mapped_column(Text,nullable=False); immutable: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')

class CourseModule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='course_modules'; __table_args__=(UniqueConstraint('course_version_id','position',name='uq_course_module_position'),)
    course_version_id: Mapped[UUID]=mapped_column(ForeignKey('course_versions.id',ondelete='CASCADE'),nullable=False); title: Mapped[str]=mapped_column(String(240),nullable=False); position: Mapped[int]=mapped_column(Integer,nullable=False); required: Mapped[bool]=mapped_column(Boolean,default=True,server_default='true')

class Lesson(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='lessons'; __table_args__=(UniqueConstraint('module_id','position',name='uq_lesson_position'), CheckConstraint(f"status IN {CONTENT_STATES}", name='lesson_status'))
    module_id: Mapped[UUID]=mapped_column(ForeignKey('course_modules.id',ondelete='CASCADE'),nullable=False); title: Mapped[str]=mapped_column(String(240),nullable=False); position: Mapped[int]=mapped_column(Integer,nullable=False); status: Mapped[str]=mapped_column(String(32),default='draft',server_default='draft'); version: Mapped[int]=mapped_column(Integer,default=1,server_default='1'); estimated_minutes: Mapped[int]=mapped_column(Integer,nullable=False)

class LessonSection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='lesson_sections'; __table_args__=(UniqueConstraint('lesson_id','position',name='uq_lesson_section_position'),)
    lesson_id: Mapped[UUID]=mapped_column(ForeignKey('lessons.id',ondelete='CASCADE'),nullable=False); section_type: Mapped[str]=mapped_column(String(32),nullable=False); heading: Mapped[str|None]=mapped_column(String(240)); body: Mapped[str]=mapped_column(Text,nullable=False); position: Mapped[int]=mapped_column(Integer,nullable=False)

class LessonEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='lesson_evidence'; __table_args__=(UniqueConstraint('lesson_section_id','source_passage_id',name='uq_lesson_evidence_passage'),)
    lesson_section_id: Mapped[UUID]=mapped_column(ForeignKey('lesson_sections.id',ondelete='CASCADE'),nullable=False); source_passage_id: Mapped[UUID]=mapped_column(ForeignKey('source_passages.id',ondelete='RESTRICT'),nullable=False); claim_label: Mapped[str]=mapped_column(String(160),nullable=False); required: Mapped[bool]=mapped_column(Boolean,default=True,server_default='true')

class LearningObjective(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='learning_objectives'; __table_args__=(UniqueConstraint('lesson_id','position',name='uq_learning_objective_position'),)
    lesson_id: Mapped[UUID]=mapped_column(ForeignKey('lessons.id',ondelete='CASCADE'),nullable=False); text: Mapped[str]=mapped_column(String(500),nullable=False); position: Mapped[int]=mapped_column(Integer,nullable=False)

class VocabularyTerm(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='vocabulary_terms'; __table_args__=(UniqueConstraint('lesson_id','term','language',name='uq_vocabulary_term_language'),)
    lesson_id: Mapped[UUID]=mapped_column(ForeignKey('lessons.id',ondelete='CASCADE'),nullable=False); term: Mapped[str]=mapped_column(String(160),nullable=False); arabic: Mapped[str|None]=mapped_column(String(160)); transliteration: Mapped[str|None]=mapped_column(String(160)); definition: Mapped[str]=mapped_column(Text,nullable=False); language: Mapped[str]=mapped_column(String(8),nullable=False)

class ContentReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='content_reviews'; __table_args__=(CheckConstraint("review_type IN ('editorial','islamic','language','publisher')",name='content_review_type'), CheckConstraint("decision IN ('pending','approved','changes_requested','rejected')",name='content_review_decision'))
    content_type: Mapped[str]=mapped_column(String(32),nullable=False); content_id: Mapped[UUID]=mapped_column(nullable=False); review_type: Mapped[str]=mapped_column(String(24),nullable=False); reviewer_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False); author_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False); decision: Mapped[str]=mapped_column(String(24),default='pending',server_default='pending'); rationale: Mapped[str|None]=mapped_column(Text)

class LessonTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='lesson_translations'; __table_args__=(UniqueConstraint('lesson_id','language','version',name='uq_lesson_translation_version'),)
    lesson_id: Mapped[UUID]=mapped_column(ForeignKey('lessons.id',ondelete='CASCADE'),nullable=False); language: Mapped[str]=mapped_column(String(8),nullable=False); version: Mapped[int]=mapped_column(Integer,nullable=False); title: Mapped[str]=mapped_column(String(240),nullable=False); structure_sha256: Mapped[str]=mapped_column(String(64),nullable=False); evidence_sha256: Mapped[str]=mapped_column(String(64),nullable=False); status: Mapped[str]=mapped_column(String(32),default='draft',server_default='draft')

class Assessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='assessments'; __table_args__=(CheckConstraint("scope_type IN ('lesson','module','course')",name='assessment_scope'),)
    scope_type: Mapped[str]=mapped_column(String(16),nullable=False); scope_id: Mapped[UUID]=mapped_column(nullable=False); title: Mapped[str]=mapped_column(String(240),nullable=False); passing_score: Mapped[int]=mapped_column(Integer,nullable=False); max_attempts: Mapped[int|None]=mapped_column(Integer); scoring_policy: Mapped[str]=mapped_column(String(24),default='highest',server_default='highest'); published: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')

class AssessmentQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='assessment_questions'; __table_args__=(UniqueConstraint('assessment_id','position',name='uq_assessment_question_position'),)
    assessment_id: Mapped[UUID]=mapped_column(ForeignKey('assessments.id',ondelete='CASCADE'),nullable=False); question_type: Mapped[str]=mapped_column(String(32),nullable=False); prompt: Mapped[str]=mapped_column(Text,nullable=False); explanation: Mapped[str]=mapped_column(Text,nullable=False); position: Mapped[int]=mapped_column(Integer,nullable=False); points: Mapped[int]=mapped_column(Integer,default=1,server_default='1'); required: Mapped[bool]=mapped_column(Boolean,default=True,server_default='true')

class QuestionOption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='question_options'; __table_args__=(UniqueConstraint('question_id','position',name='uq_question_option_position'),)
    question_id: Mapped[UUID]=mapped_column(ForeignKey('assessment_questions.id',ondelete='CASCADE'),nullable=False); text: Mapped[str]=mapped_column(Text,nullable=False); position: Mapped[int]=mapped_column(Integer,nullable=False); correct: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')

class QuestionEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='question_evidence'; __table_args__=(UniqueConstraint('question_id','source_passage_id',name='uq_question_evidence_passage'),)
    question_id: Mapped[UUID]=mapped_column(ForeignKey('assessment_questions.id',ondelete='CASCADE'),nullable=False); source_passage_id: Mapped[UUID]=mapped_column(ForeignKey('source_passages.id',ondelete='RESTRICT'),nullable=False)

class CourseEnrollment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='course_enrollments'; __table_args__=(UniqueConstraint('user_id','course_id',name='uq_course_enrollment_user_course'), Index('ix_course_enrollment_user_status','user_id','status'))
    user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False); course_id: Mapped[UUID]=mapped_column(ForeignKey('courses.id',ondelete='RESTRICT'),nullable=False); course_version: Mapped[int]=mapped_column(Integer,nullable=False); status: Mapped[str]=mapped_column(String(24),default='enrolled',server_default='enrolled'); completion_percent: Mapped[int]=mapped_column(Integer,default=0,server_default='0')

class LessonProgress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='lesson_progress'; __table_args__=(UniqueConstraint('user_id','lesson_id',name='uq_lesson_progress_user_lesson'),)
    user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False); lesson_id: Mapped[UUID]=mapped_column(ForeignKey('lessons.id',ondelete='RESTRICT'),nullable=False); completed: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false'); resume_section: Mapped[int]=mapped_column(Integer,default=0,server_default='0'); seconds_spent: Mapped[int]=mapped_column(Integer,default=0,server_default='0')

class AssessmentAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='assessment_attempts'; __table_args__=(Index('ix_assessment_attempt_user','user_id','assessment_id'),)
    user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False); assessment_id: Mapped[UUID]=mapped_column(ForeignKey('assessments.id',ondelete='RESTRICT'),nullable=False); attempt_number: Mapped[int]=mapped_column(Integer,nullable=False); status: Mapped[str]=mapped_column(String(20),default='in_progress',server_default='in_progress'); answers_json: Mapped[str]=mapped_column(Text,default='{}',server_default='{}'); score: Mapped[int|None]=mapped_column(Integer); passed: Mapped[bool|None]=mapped_column(Boolean)

class LearnerNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='learner_notes'; __table_args__=(Index('ix_learner_notes_user_lesson','user_id','lesson_id'),)
    user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False); lesson_id: Mapped[UUID]=mapped_column(ForeignKey('lessons.id',ondelete='CASCADE'),nullable=False); body: Mapped[str]=mapped_column(Text,nullable=False); private: Mapped[bool]=mapped_column(Boolean,default=True,server_default='true'); eligible_as_evidence: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')

class Certificate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='learning_certificates'; __table_args__=(UniqueConstraint('verification_code',name='uq_learning_certificate_code'),)
    user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False); course_id: Mapped[UUID]=mapped_column(ForeignKey('courses.id',ondelete='RESTRICT'),nullable=False); course_version: Mapped[int]=mapped_column(Integer,nullable=False); verification_code: Mapped[str]=mapped_column(String(64),nullable=False); learner_name: Mapped[str]=mapped_column(String(240),nullable=False); disclaimer: Mapped[str]=mapped_column(Text,nullable=False); revoked: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')

class GuardianRelationship(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='guardian_relationships'; __table_args__=(UniqueConstraint('guardian_user_id','child_user_id',name='uq_guardian_child'), CheckConstraint('guardian_user_id <> child_user_id',name='guardian_not_child'))
    guardian_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False); child_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False); status: Mapped[str]=mapped_column(String(20),default='pending',server_default='pending')

class RecommendationEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='learning_recommendation_events'
    user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False); course_id: Mapped[UUID]=mapped_column(ForeignKey('courses.id',ondelete='CASCADE'),nullable=False); reason_code: Mapped[str]=mapped_column(String(48),nullable=False); algorithm_version: Mapped[str]=mapped_column(String(32),nullable=False); score: Mapped[int]=mapped_column(Integer,nullable=False)
