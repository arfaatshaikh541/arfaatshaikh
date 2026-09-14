from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class ScholarProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='scholar_profiles'
    __table_args__=(UniqueConstraint('user_id',name='uq_scholar_profile_user'),CheckConstraint("verification_status IN ('unverified','pending','verified','rejected','suspended')",name='scholar_profile_verification_status'))
    user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False)
    display_name: Mapped[str]=mapped_column(String(240),nullable=False)
    biography: Mapped[str]=mapped_column(Text,default='',server_default='')
    credentials_summary: Mapped[str]=mapped_column(Text,default='',server_default='')
    verification_status: Mapped[str]=mapped_column(String(16),default='unverified',server_default='unverified')
    verification_notes: Mapped[str]=mapped_column(Text,default='',server_default='')
    may_issue_platform_rulings: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')

class ScholarlyProject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='scholarly_projects'
    __table_args__=(CheckConstraint("status IN ('draft','in_review','approved','published','archived')",name='scholarly_project_status'),Index('ix_scholarly_project_status','status','updated_at'))
    title: Mapped[str]=mapped_column(String(300),nullable=False)
    description: Mapped[str]=mapped_column(Text,default='',server_default='')
    owner_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    status: Mapped[str]=mapped_column(String(16),default='draft',server_default='draft')
    required_islamic_reviews: Mapped[int]=mapped_column(Integer,default=2,server_default='2')
    required_editorial_reviews: Mapped[int]=mapped_column(Integer,default=1,server_default='1')

class CollaborativeDraft(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='collaborative_drafts'
    __table_args__=(UniqueConstraint('project_id','slug',name='uq_collaborative_draft_project_slug'),CheckConstraint("content_type IN ('commentary','research_note','translation_note','curriculum_note')",name='collaborative_draft_content_type'))
    project_id: Mapped[UUID]=mapped_column(ForeignKey('scholarly_projects.id',ondelete='CASCADE'),nullable=False)
    slug: Mapped[str]=mapped_column(String(160),nullable=False)
    title: Mapped[str]=mapped_column(String(300),nullable=False)
    content_type: Mapped[str]=mapped_column(String(32),nullable=False)
    current_version_number: Mapped[int]=mapped_column(Integer,default=0,server_default='0')
    locked_for_review: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')

class CollaborativeDraftVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='collaborative_draft_versions'
    __table_args__=(UniqueConstraint('draft_id','version_number',name='uq_collaborative_draft_version'),CheckConstraint("status IN ('working','submitted','superseded','accepted')",name='collaborative_draft_version_status'))
    draft_id: Mapped[UUID]=mapped_column(ForeignKey('collaborative_drafts.id',ondelete='CASCADE'),nullable=False)
    version_number: Mapped[int]=mapped_column(Integer,nullable=False)
    author_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    body: Mapped[str]=mapped_column(Text,nullable=False)
    change_summary: Mapped[str]=mapped_column(Text,default='',server_default='')
    content_fingerprint: Mapped[str]=mapped_column(String(64),nullable=False)
    evidence_fingerprint: Mapped[str]=mapped_column(String(64),nullable=False)
    status: Mapped[str]=mapped_column(String(16),default='working',server_default='working')

class DraftEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='draft_evidence'
    __table_args__=(UniqueConstraint('draft_version_id','source_passage_id',name='uq_draft_version_evidence'),)
    draft_version_id: Mapped[UUID]=mapped_column(ForeignKey('collaborative_draft_versions.id',ondelete='CASCADE'),nullable=False)
    source_passage_id: Mapped[UUID]=mapped_column(ForeignKey('source_passages.id',ondelete='RESTRICT'),nullable=False)
    locator: Mapped[str]=mapped_column(String(300),nullable=False)
    quotation: Mapped[str]=mapped_column(Text,default='',server_default='')

class ScholarlyReviewAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='scholarly_review_assignments'
    __table_args__=(UniqueConstraint('draft_version_id','reviewer_user_id','review_type',name='uq_scholarly_review_assignment'),CheckConstraint("review_type IN ('islamic','editorial','source_integrity','translation')",name='scholarly_review_type'),CheckConstraint("status IN ('assigned','in_progress','completed','cancelled')",name='scholarly_review_assignment_status'))
    draft_version_id: Mapped[UUID]=mapped_column(ForeignKey('collaborative_draft_versions.id',ondelete='CASCADE'),nullable=False)
    reviewer_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    assigned_by_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    review_type: Mapped[str]=mapped_column(String(24),nullable=False)
    status: Mapped[str]=mapped_column(String(16),default='assigned',server_default='assigned')

class ScholarlyReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='scholarly_reviews'
    __table_args__=(UniqueConstraint('assignment_id',name='uq_scholarly_review_assignment_result'),CheckConstraint("decision IN ('approve','changes_requested','reject','abstain')",name='scholarly_review_decision'))
    assignment_id: Mapped[UUID]=mapped_column(ForeignKey('scholarly_review_assignments.id',ondelete='CASCADE'),nullable=False)
    reviewer_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    decision: Mapped[str]=mapped_column(String(24),nullable=False)
    comments: Mapped[str]=mapped_column(Text,nullable=False)
    evidence_checked: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
    independent: Mapped[bool]=mapped_column(Boolean,default=True,server_default='true')

class ScholarlyApproval(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='scholarly_approvals'
    __table_args__=(UniqueConstraint('draft_version_id',name='uq_scholarly_approval_version'),CheckConstraint("decision IN ('approved','rejected','withdrawn')",name='scholarly_approval_decision'))
    draft_version_id: Mapped[UUID]=mapped_column(ForeignKey('collaborative_draft_versions.id',ondelete='CASCADE'),nullable=False)
    approved_by_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    decision: Mapped[str]=mapped_column(String(16),nullable=False)
    rationale: Mapped[str]=mapped_column(Text,nullable=False)
    policy_version: Mapped[str]=mapped_column(String(40),nullable=False)
    review_snapshot_fingerprint: Mapped[str]=mapped_column(String(64),nullable=False)
