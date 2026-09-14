from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class ResearchWorkspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='research_workspaces'
    __table_args__=(UniqueConstraint('owner_user_id','slug',name='uq_research_workspace_owner_slug'),CheckConstraint("visibility IN ('private','shared')",name='research_workspace_visibility'))
    owner_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False)
    slug: Mapped[str]=mapped_column(String(120),nullable=False)
    title: Mapped[str]=mapped_column(String(240),nullable=False)
    description: Mapped[str]=mapped_column(Text,default='',server_default='')
    visibility: Mapped[str]=mapped_column(String(16),default='private',server_default='private')
    version: Mapped[int]=mapped_column(Integer,default=1,server_default='1')
    archived: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')

class ResearchWorkspaceMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='research_workspace_members'
    __table_args__=(UniqueConstraint('workspace_id','user_id',name='uq_research_workspace_member'),CheckConstraint("role IN ('viewer','contributor','editor')",name='research_workspace_member_role'))
    workspace_id: Mapped[UUID]=mapped_column(ForeignKey('research_workspaces.id',ondelete='CASCADE'),nullable=False)
    user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False)
    role: Mapped[str]=mapped_column(String(16),nullable=False)

class ResearchCollection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='research_collections'
    __table_args__=(UniqueConstraint('workspace_id','slug',name='uq_research_collection_workspace_slug'),)
    workspace_id: Mapped[UUID]=mapped_column(ForeignKey('research_workspaces.id',ondelete='CASCADE'),nullable=False)
    slug: Mapped[str]=mapped_column(String(120),nullable=False)
    title: Mapped[str]=mapped_column(String(240),nullable=False)
    description: Mapped[str]=mapped_column(Text,default='',server_default='')
    position: Mapped[int]=mapped_column(Integer,default=0,server_default='0')

class ResearchItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='research_items'
    __table_args__=(UniqueConstraint('collection_id','item_type','item_id',name='uq_research_collection_item'),CheckConstraint("item_type IN ('source_passage','quran_ayah','hadith_narration','tafsir_entry','lesson','external_reference')",name='research_item_type'))
    collection_id: Mapped[UUID]=mapped_column(ForeignKey('research_collections.id',ondelete='CASCADE'),nullable=False)
    item_type: Mapped[str]=mapped_column(String(32),nullable=False)
    item_id: Mapped[UUID|None]=mapped_column(nullable=True)
    external_url: Mapped[str|None]=mapped_column(String(1000))
    title: Mapped[str]=mapped_column(String(500),nullable=False)
    position: Mapped[int]=mapped_column(Integer,default=0,server_default='0')
    added_by_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)

class ResearchAnnotation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='research_annotations'
    __table_args__=(Index('ix_research_annotation_workspace_owner','workspace_id','owner_user_id'),CheckConstraint("visibility IN ('private','workspace')",name='research_annotation_visibility'))
    workspace_id: Mapped[UUID]=mapped_column(ForeignKey('research_workspaces.id',ondelete='CASCADE'),nullable=False)
    research_item_id: Mapped[UUID]=mapped_column(ForeignKey('research_items.id',ondelete='CASCADE'),nullable=False)
    owner_user_id: Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False)
    body: Mapped[str]=mapped_column(Text,nullable=False)
    visibility: Mapped[str]=mapped_column(String(16),default='private',server_default='private')
    eligible_as_evidence: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')

class ResearchCitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='research_citations'
    __table_args__=(UniqueConstraint('workspace_id','citation_key',name='uq_research_workspace_citation_key'),)
    workspace_id: Mapped[UUID]=mapped_column(ForeignKey('research_workspaces.id',ondelete='CASCADE'),nullable=False)
    research_item_id: Mapped[UUID]=mapped_column(ForeignKey('research_items.id',ondelete='RESTRICT'),nullable=False)
    citation_key: Mapped[str]=mapped_column(String(120),nullable=False)
    style: Mapped[str]=mapped_column(String(32),default='woi',server_default='woi')
    rendered_text: Mapped[str]=mapped_column(Text,nullable=False)
    provenance_json: Mapped[str]=mapped_column(Text,nullable=False)

class ReadingList(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='reading_lists'
    __table_args__=(UniqueConstraint('workspace_id','slug',name='uq_reading_list_workspace_slug'),)
    workspace_id: Mapped[UUID]=mapped_column(ForeignKey('research_workspaces.id',ondelete='CASCADE'),nullable=False)
    slug: Mapped[str]=mapped_column(String(120),nullable=False)
    title: Mapped[str]=mapped_column(String(240),nullable=False)
    description: Mapped[str]=mapped_column(Text,default='',server_default='')

class ReadingListEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__='reading_list_entries'
    __table_args__=(UniqueConstraint('reading_list_id','position',name='uq_reading_list_entry_position'),UniqueConstraint('reading_list_id','research_item_id',name='uq_reading_list_item'))
    reading_list_id: Mapped[UUID]=mapped_column(ForeignKey('reading_lists.id',ondelete='CASCADE'),nullable=False)
    research_item_id: Mapped[UUID]=mapped_column(ForeignKey('research_items.id',ondelete='RESTRICT'),nullable=False)
    position: Mapped[int]=mapped_column(Integer,nullable=False)
    required: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
