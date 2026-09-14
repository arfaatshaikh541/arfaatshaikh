from uuid import UUID
from sqlalchemy import Boolean,ForeignKey,Integer,JSON,String,Text,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.db.base import Base,TimestampMixin,UUIDPrimaryKeyMixin
class ScholarlyCouncil(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='scholarly_councils'; __table_args__=(UniqueConstraint('organisation_id','slug',name='uq_scholarly_council_slug'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); slug:Mapped[str]=mapped_column(String(100)); name:Mapped[str]=mapped_column(String(200)); quorum_percent:Mapped[int]=mapped_column(Integer); evidence_sha256:Mapped[str]=mapped_column(String(64)); status:Mapped[str]=mapped_column(String(16),default='draft',server_default='draft')
class ScholarlyCouncilMember(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='scholarly_council_members'; __table_args__=(UniqueConstraint('council_id','scholar_profile_id',name='uq_scholarly_council_member'),)
 council_id:Mapped[UUID]=mapped_column(ForeignKey('scholarly_councils.id',ondelete='CASCADE')); scholar_profile_id:Mapped[UUID]=mapped_column(ForeignKey('scholar_profiles.id',ondelete='CASCADE')); institution_id:Mapped[UUID|None]=mapped_column(ForeignKey('institutions.id',ondelete='SET NULL')); role:Mapped[str]=mapped_column(String(40)); active:Mapped[bool]=mapped_column(Boolean,default=True,server_default='true')
class ScholarlyCouncilDecision(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='scholarly_council_decisions'; __table_args__=(UniqueConstraint('council_id','decision_key','version',name='uq_scholarly_decision_version'),)
 council_id:Mapped[UUID]=mapped_column(ForeignKey('scholarly_councils.id',ondelete='CASCADE')); decision_key:Mapped[str]=mapped_column(String(160)); version:Mapped[str]=mapped_column(String(40)); content_type:Mapped[str]=mapped_column(String(40)); decision_sha256:Mapped[str]=mapped_column(String(64)); outcome:Mapped[str]=mapped_column(String(20)); dissent_json:Mapped[dict]=mapped_column(JSON,default=dict,server_default='{}')
class ProvenanceLineage(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='provenance_lineages'; __table_args__=(UniqueConstraint('organisation_id','canonical_id','version',name='uq_provenance_lineage_version'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); canonical_id:Mapped[str]=mapped_column(String(200)); version:Mapped[str]=mapped_column(String(40)); payload_sha256:Mapped[str]=mapped_column(String(64)); lineage_sha256:Mapped[str]=mapped_column(String(64)); status:Mapped[str]=mapped_column(String(16),default='draft',server_default='draft')
class ProvenanceLink(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='provenance_links'; __table_args__=(UniqueConstraint('lineage_id','link_type','linked_fingerprint',name='uq_provenance_link'),)
 lineage_id:Mapped[UUID]=mapped_column(ForeignKey('provenance_lineages.id',ondelete='CASCADE')); link_type:Mapped[str]=mapped_column(String(24)); linked_fingerprint:Mapped[str]=mapped_column(String(64)); metadata_json:Mapped[dict]=mapped_column(JSON,default=dict,server_default='{}')
class CrossInstitutionResearchProject(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='cross_institution_research_projects'; __table_args__=(UniqueConstraint('organisation_id','project_slug',name='uq_cross_institution_project_slug'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); project_slug:Mapped[str]=mapped_column(String(100)); title:Mapped[str]=mapped_column(String(240)); lead_scholar_id:Mapped[UUID]=mapped_column(ForeignKey('scholar_profiles.id')); methodology_sha256:Mapped[str]=mapped_column(String(64)); status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class ResearchInstitutionParticipant(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='research_institution_participants'; __table_args__=(UniqueConstraint('project_id','institution_id',name='uq_research_institution_participant'),)
 project_id:Mapped[UUID]=mapped_column(ForeignKey('cross_institution_research_projects.id',ondelete='CASCADE')); institution_id:Mapped[UUID]=mapped_column(ForeignKey('institutions.id',ondelete='CASCADE')); role:Mapped[str]=mapped_column(String(60)); data_access_scope:Mapped[str]=mapped_column(String(120))
class GovernedCurriculum(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='governed_curricula'; __table_args__=(UniqueConstraint('organisation_id','curriculum_slug','version',name='uq_governed_curriculum_version'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); curriculum_slug:Mapped[str]=mapped_column(String(100)); version:Mapped[str]=mapped_column(String(40)); title:Mapped[str]=mapped_column(String(240)); evidence_coverage_percent:Mapped[int]=mapped_column(Integer); status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class GovernedCertificationAward(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='governed_certification_awards'; __table_args__=(UniqueConstraint('curriculum_id','learner_id','certificate_fingerprint',name='uq_governed_certificate_award'),)
 curriculum_id:Mapped[UUID]=mapped_column(ForeignKey('governed_curricula.id',ondelete='CASCADE')); learner_id:Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='CASCADE')); assessment_score:Mapped[int]=mapped_column(Integer); certificate_fingerprint:Mapped[str]=mapped_column(String(64)); status:Mapped[str]=mapped_column(String(20),default='issued',server_default='issued')
class GovernedCommunityContribution(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='governed_community_contributions'; __table_args__=(UniqueConstraint('organisation_id','contribution_key','version',name='uq_governed_contribution_version'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); contribution_key:Mapped[str]=mapped_column(String(160)); version:Mapped[str]=mapped_column(String(40)); author_id:Mapped[UUID]=mapped_column(ForeignKey('users.id')); content_type:Mapped[str]=mapped_column(String(40)); status:Mapped[str]=mapped_column(String(20),default='review',server_default='review'); evidence_json:Mapped[dict]=mapped_column(JSON,default=dict,server_default='{}')
class StewardshipTransfer(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='stewardship_transfers'
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); from_institution_id:Mapped[UUID]=mapped_column(ForeignKey('institutions.id')); to_institution_id:Mapped[UUID]=mapped_column(ForeignKey('institutions.id')); asset_inventory_sha256:Mapped[str]=mapped_column(String(64)); audit_handover_sha256:Mapped[str]=mapped_column(String(64)); status:Mapped[str]=mapped_column(String(20),default='planned',server_default='planned')
class PrivacySafeAnalyticsRelease(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='privacy_safe_analytics_releases'; __table_args__=(UniqueConstraint('organisation_id','release_slug','version',name='uq_analytics_release_version'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); release_slug:Mapped[str]=mapped_column(String(100)); version:Mapped[str]=mapped_column(String(40)); k_anonymity:Mapped[int]=mapped_column(Integer); minimum_group_size:Mapped[int]=mapped_column(Integer); export_sha256:Mapped[str]=mapped_column(String(64)); status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class PlatformMaturityReview(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='platform_maturity_reviews'; __table_args__=(UniqueConstraint('organisation_id','milestone_version',name='uq_platform_maturity_review_version'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); milestone_version:Mapped[str]=mapped_column(String(40)); outcome:Mapped[str]=mapped_column(String(16)); portable_ready:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false'); production_ready:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false'); evidence_sha256:Mapped[str]=mapped_column(String(64)); notes:Mapped[str|None]=mapped_column(Text)
