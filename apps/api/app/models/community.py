from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class CommunitySpace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='community_spaces'
    __table_args__=(UniqueConstraint('slug',name='uq_community_space_slug'),CheckConstraint("visibility IN ('private','members','public')",name='community_space_visibility'))
    slug: Mapped[str]=mapped_column(String(120),nullable=False)
    title: Mapped[str]=mapped_column(String(240),nullable=False)
    description: Mapped[str]=mapped_column(Text,default='',server_default='')
    visibility: Mapped[str]=mapped_column(String(16),default='members',server_default='members')
    requires_evidence: Mapped[bool]=mapped_column(Boolean,default=True,server_default='true')
    child_access_allowed: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')

class CommunityThread(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='community_threads'
    __table_args__=(CheckConstraint("status IN ('open','locked','hidden','archived')",name='community_thread_status'),Index('ix_community_thread_space_status','space_id','status'))
    space_id: Mapped[UUID]=mapped_column(ForeignKey('community_spaces.id',ondelete='CASCADE'),nullable=False)
    author_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    title: Mapped[str]=mapped_column(String(300),nullable=False)
    body: Mapped[str]=mapped_column(Text,nullable=False)
    status: Mapped[str]=mapped_column(String(16),default='open',server_default='open')
    evidence_required: Mapped[bool]=mapped_column(Boolean,default=True,server_default='true')
    is_religious_claim: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')

class CommunityPost(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='community_posts'
    __table_args__=(CheckConstraint("status IN ('visible','pending','hidden','removed')",name='community_post_status'),Index('ix_community_post_thread_status','thread_id','status'))
    thread_id: Mapped[UUID]=mapped_column(ForeignKey('community_threads.id',ondelete='CASCADE'),nullable=False)
    parent_post_id: Mapped[UUID|None]=mapped_column(ForeignKey('community_posts.id',ondelete='CASCADE'))
    author_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    body: Mapped[str]=mapped_column(Text,nullable=False)
    status: Mapped[str]=mapped_column(String(16),default='pending',server_default='pending')
    is_religious_claim: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
    authoritative_claim: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')

class CommunityPostEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='community_post_evidence'
    __table_args__=(UniqueConstraint('post_id','source_passage_id',name='uq_community_post_evidence'),)
    post_id: Mapped[UUID]=mapped_column(ForeignKey('community_posts.id',ondelete='CASCADE'),nullable=False)
    source_passage_id: Mapped[UUID]=mapped_column(ForeignKey('source_passages.id',ondelete='RESTRICT'),nullable=False)
    quotation: Mapped[str]=mapped_column(Text,default='',server_default='')
    locator: Mapped[str]=mapped_column(String(300),nullable=False)

class CommunityReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='community_reports'
    __table_args__=(CheckConstraint("target_type IN ('thread','post','profile')",name='community_report_target_type'),CheckConstraint("status IN ('open','triaged','resolved','dismissed')",name='community_report_status'),Index('ix_community_report_status','status','created_at'))
    reporter_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    target_type: Mapped[str]=mapped_column(String(16),nullable=False)
    target_id: Mapped[UUID]=mapped_column(nullable=False)
    category: Mapped[str]=mapped_column(String(40),nullable=False)
    details: Mapped[str]=mapped_column(Text,default='',server_default='')
    status: Mapped[str]=mapped_column(String(16),default='open',server_default='open')
    risk_score: Mapped[int]=mapped_column(Integer,default=0,server_default='0')

class ModerationDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='moderation_decisions'
    __table_args__=(CheckConstraint("action IN ('approve','hide','remove','lock','warn','escalate','dismiss')",name='moderation_decision_action'),)
    report_id: Mapped[UUID|None]=mapped_column(ForeignKey('community_reports.id',ondelete='SET NULL'))
    moderator_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    target_type: Mapped[str]=mapped_column(String(16),nullable=False)
    target_id: Mapped[UUID]=mapped_column(nullable=False)
    action: Mapped[str]=mapped_column(String(16),nullable=False)
    reason: Mapped[str]=mapped_column(Text,nullable=False)
    policy_code: Mapped[str]=mapped_column(String(80),nullable=False)
    reversible: Mapped[bool]=mapped_column(Boolean,default=True,server_default='true')

class CommunityReputationEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='community_reputation_events'
    user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False)
    event_type: Mapped[str]=mapped_column(String(40),nullable=False)
    points: Mapped[int]=mapped_column(Integer,nullable=False)
    reason: Mapped[str]=mapped_column(String(300),nullable=False)
    grants_religious_authority: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
