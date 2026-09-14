from uuid import UUID
from sqlalchemy import Boolean,ForeignKey,Integer,JSON,String,Text,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.db.base import Base,TimestampMixin,UUIDPrimaryKeyMixin
class ScholarlyLineage(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='scholarly_lineages';__table_args__=(UniqueConstraint('organisation_id','slug','version',name='uq_scholarly_lineage_version'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));slug:Mapped[str]=mapped_column(String(120));version:Mapped[str]=mapped_column(String(40));manifest_sha256:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class ScholarlyLineageLink(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='scholarly_lineage_links';__table_args__=(UniqueConstraint('lineage_id','teacher_profile_id','student_profile_id',name='uq_scholarly_lineage_link'),)
 lineage_id:Mapped[UUID]=mapped_column(ForeignKey('scholarly_lineages.id',ondelete='CASCADE'));teacher_profile_id:Mapped[UUID]=mapped_column(ForeignKey('scholar_profiles.id',ondelete='CASCADE'));student_profile_id:Mapped[UUID]=mapped_column(ForeignKey('scholar_profiles.id',ondelete='CASCADE'));evidence_sha256:Mapped[str]=mapped_column(String(64));verified:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
class TranslationGovernanceRelease(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='translation_governance_releases';__table_args__=(UniqueConstraint('organisation_id','release_slug','version',name='uq_translation_governance_release'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));release_slug:Mapped[str]=mapped_column(String(120));version:Mapped[str]=mapped_column(String(40));source_language:Mapped[str]=mapped_column(String(16));target_language:Mapped[str]=mapped_column(String(16));semantic_alignment_percent:Mapped[int]=mapped_column(Integer);status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class TranslationTermDecision(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='translation_term_decisions';__table_args__=(UniqueConstraint('release_id','source_term','target_term',name='uq_translation_term_decision'),)
 release_id:Mapped[UUID]=mapped_column(ForeignKey('translation_governance_releases.id',ondelete='CASCADE'));source_term:Mapped[str]=mapped_column(String(180));target_term:Mapped[str]=mapped_column(String(180));rationale:Mapped[str]=mapped_column(Text);disputed:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false');evidence_sha256:Mapped[str]=mapped_column(String(64))
class VerifiableCredentialSchema(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='verifiable_credential_schemas';__table_args__=(UniqueConstraint('organisation_id','schema_slug','version',name='uq_verifiable_credential_schema'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));schema_slug:Mapped[str]=mapped_column(String(120));version:Mapped[str]=mapped_column(String(40));schema_sha256:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class VerifiableCredentialRecord(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='verifiable_credential_records';__table_args__=(UniqueConstraint('schema_id','credential_reference',name='uq_verifiable_credential_reference'),)
 schema_id:Mapped[UUID]=mapped_column(ForeignKey('verifiable_credential_schemas.id',ondelete='CASCADE'));credential_reference:Mapped[str]=mapped_column(String(180));issuer_institution_id:Mapped[UUID]=mapped_column(ForeignKey('institutions.id',ondelete='CASCADE'));subject_reference:Mapped[str]=mapped_column(String(180));signature_sha256:Mapped[str]=mapped_column(String(64));revoked:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
class CivilizationalEvent(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='civilizational_events';__table_args__=(UniqueConstraint('organisation_id','event_slug',name='uq_civilizational_event_slug'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));event_slug:Mapped[str]=mapped_column(String(120));title:Mapped[str]=mapped_column(String(240));jurisdiction_code:Mapped[str]=mapped_column(String(2));programme_sha256:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class CivilizationalEventHost(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='civilizational_event_hosts';__table_args__=(UniqueConstraint('event_id','institution_id',name='uq_civilizational_event_host'),)
 event_id:Mapped[UUID]=mapped_column(ForeignKey('civilizational_events.id',ondelete='CASCADE'));institution_id:Mapped[UUID]=mapped_column(ForeignKey('institutions.id',ondelete='CASCADE'));role:Mapped[str]=mapped_column(String(60));verified:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
class StrategicPolicy(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='strategic_policies';__table_args__=(UniqueConstraint('organisation_id','policy_slug','version',name='uq_strategic_policy_version'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));policy_slug:Mapped[str]=mapped_column(String(120));version:Mapped[str]=mapped_column(String(40));policy_sha256:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class PolicyLifecycleReview(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='policy_lifecycle_reviews'
 policy_id:Mapped[UUID]=mapped_column(ForeignKey('strategic_policies.id',ondelete='CASCADE'));review_type:Mapped[str]=mapped_column(String(40));reviewer_reference:Mapped[str]=mapped_column(String(180));evidence_sha256:Mapped[str]=mapped_column(String(64));outcome:Mapped[str]=mapped_column(String(20))
class OperationalIntelligenceProfile(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='operational_intelligence_profiles';__table_args__=(UniqueConstraint('organisation_id','profile_slug','version',name='uq_operational_intelligence_profile'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));profile_slug:Mapped[str]=mapped_column(String(120));version:Mapped[str]=mapped_column(String(40));metrics_coverage_percent:Mapped[int]=mapped_column(Integer);trace_coverage_percent:Mapped[int]=mapped_column(Integer);forecast_accuracy_percent:Mapped[int]=mapped_column(Integer);status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class OperationalIntelligenceDecision(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='operational_intelligence_decisions'
 profile_id:Mapped[UUID]=mapped_column(ForeignKey('operational_intelligence_profiles.id',ondelete='CASCADE'));decision_type:Mapped[str]=mapped_column(String(80));inputs_json:Mapped[dict]=mapped_column(JSON,default=dict,server_default='{}');human_override_used:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false');evidence_sha256:Mapped[str]=mapped_column(String(64))
class ContinuitySuccessionPlan(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='continuity_succession_plans';__table_args__=(UniqueConstraint('organisation_id','plan_slug','version',name='uq_continuity_succession_plan'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));plan_slug:Mapped[str]=mapped_column(String(120));version:Mapped[str]=mapped_column(String(40));rpo_minutes:Mapped[int]=mapped_column(Integer);rto_hours:Mapped[int]=mapped_column(Integer);evidence_sha256:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class ContinuitySuccessorSteward(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='continuity_successor_stewards';__table_args__=(UniqueConstraint('plan_id','institution_id',name='uq_continuity_successor_steward'),)
 plan_id:Mapped[UUID]=mapped_column(ForeignKey('continuity_succession_plans.id',ondelete='CASCADE'));institution_id:Mapped[UUID]=mapped_column(ForeignKey('institutions.id',ondelete='CASCADE'));priority:Mapped[int]=mapped_column(Integer);accepted:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
class ContinuityExercise(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='continuity_exercises'
 plan_id:Mapped[UUID]=mapped_column(ForeignKey('continuity_succession_plans.id',ondelete='CASCADE'));scenario:Mapped[str]=mapped_column(String(180));restore_minutes:Mapped[int]=mapped_column(Integer);data_loss_detected:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false');evidence_sha256:Mapped[str]=mapped_column(String(64));outcome:Mapped[str]=mapped_column(String(20))
class IslamicCivilizationOSAcceptance(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='islamic_civilization_os_acceptance';__table_args__=(UniqueConstraint('organisation_id','milestone_version',name='uq_icos_acceptance_version'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));milestone_version:Mapped[str]=mapped_column(String(40));outcome:Mapped[str]=mapped_column(String(20));portable_ready:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false');production_ready:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false');evidence_sha256:Mapped[str]=mapped_column(String(64));notes:Mapped[str|None]=mapped_column(Text)
