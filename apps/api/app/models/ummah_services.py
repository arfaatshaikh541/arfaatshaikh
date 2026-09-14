from uuid import UUID
from sqlalchemy import Boolean,ForeignKey,Integer,JSON,String,Text,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.db.base import Base,TimestampMixin,UUIDPrimaryKeyMixin
class ZakatFund(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='zakat_funds'; __table_args__=(UniqueConstraint('organisation_id','slug',name='uq_zakat_fund_slug'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); slug:Mapped[str]=mapped_column(String(100)); name:Mapped[str]=mapped_column(String(200)); evidence_sha256:Mapped[str]=mapped_column(String(64)); status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class ZakatDistribution(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='zakat_distributions'; __table_args__=(UniqueConstraint('fund_id','distribution_key',name='uq_zakat_distribution_key'),)
 fund_id:Mapped[UUID]=mapped_column(ForeignKey('zakat_funds.id',ondelete='CASCADE')); distribution_key:Mapped[str]=mapped_column(String(160)); beneficiary_case_id:Mapped[UUID|None]=mapped_column(ForeignKey('beneficiary_cases.id',ondelete='SET NULL')); amount_minor:Mapped[int]=mapped_column(Integer); currency:Mapped[str]=mapped_column(String(3)); status:Mapped[str]=mapped_column(String(20),default='planned',server_default='planned')
class WaqfAsset(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='waqf_assets'; __table_args__=(UniqueConstraint('organisation_id','asset_key',name='uq_waqf_asset_key'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); asset_key:Mapped[str]=mapped_column(String(160)); asset_type:Mapped[str]=mapped_column(String(40)); asset_sha256:Mapped[str]=mapped_column(String(64)); status:Mapped[str]=mapped_column(String(20),default='review',server_default='review')
class FiduciaryAudit(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='fiduciary_audits'
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); subject_type:Mapped[str]=mapped_column(String(40)); subject_id:Mapped[UUID]=mapped_column(); evidence_sha256:Mapped[str]=mapped_column(String(64)); outcome:Mapped[str]=mapped_column(String(20)); notes:Mapped[str|None]=mapped_column(Text)
class BeneficiaryCase(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='beneficiary_cases'; __table_args__=(UniqueConstraint('organisation_id','case_reference',name='uq_beneficiary_case_reference'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); case_reference:Mapped[str]=mapped_column(String(160)); case_fingerprint:Mapped[str]=mapped_column(String(64)); region_code:Mapped[str]=mapped_column(String(2)); status:Mapped[str]=mapped_column(String(20),default='review',server_default='review'); need_json:Mapped[dict]=mapped_column(JSON,default=dict,server_default='{}')
class HumanitarianProgramme(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='humanitarian_programmes'; __table_args__=(UniqueConstraint('organisation_id','programme_slug',name='uq_humanitarian_programme_slug'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); programme_slug:Mapped[str]=mapped_column(String(100)); title:Mapped[str]=mapped_column(String(240)); evidence_sha256:Mapped[str]=mapped_column(String(64)); status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class AidDeliveryPartner(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='aid_delivery_partners'; __table_args__=(UniqueConstraint('programme_id','institution_id',name='uq_aid_delivery_partner'),)
 programme_id:Mapped[UUID]=mapped_column(ForeignKey('humanitarian_programmes.id',ondelete='CASCADE')); institution_id:Mapped[UUID]=mapped_column(ForeignKey('institutions.id',ondelete='CASCADE')); role:Mapped[str]=mapped_column(String(60)); verified:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
class AidSafeguardingReview(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='aid_safeguarding_reviews'
 programme_id:Mapped[UUID]=mapped_column(ForeignKey('humanitarian_programmes.id',ondelete='CASCADE')); reviewer_id:Mapped[UUID|None]=mapped_column(ForeignKey('users.id',ondelete='SET NULL')); evidence_sha256:Mapped[str]=mapped_column(String(64)); open_critical_findings:Mapped[int]=mapped_column(Integer,default=0,server_default='0'); outcome:Mapped[str]=mapped_column(String(20))
class MosqueService(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='mosque_services'; __table_args__=(UniqueConstraint('institution_id','service_slug',name='uq_mosque_service_slug'),)
 institution_id:Mapped[UUID]=mapped_column(ForeignKey('institutions.id',ondelete='CASCADE')); service_slug:Mapped[str]=mapped_column(String(100)); service_type:Mapped[str]=mapped_column(String(40)); title:Mapped[str]=mapped_column(String(200)); status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class VolunteerProfile(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='volunteer_profiles'; __table_args__=(UniqueConstraint('organisation_id','user_id',name='uq_volunteer_profile_user'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); user_id:Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='CASCADE')); identity_verified:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false'); safeguarding_accepted:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
class VolunteerAssignment(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='volunteer_assignments'; __table_args__=(UniqueConstraint('service_id','volunteer_profile_id',name='uq_volunteer_assignment'),)
 service_id:Mapped[UUID]=mapped_column(ForeignKey('mosque_services.id',ondelete='CASCADE')); volunteer_profile_id:Mapped[UUID]=mapped_column(ForeignKey('volunteer_profiles.id',ondelete='CASCADE')); role:Mapped[str]=mapped_column(String(80)); maximum_weekly_hours:Mapped[int]=mapped_column(Integer); status:Mapped[str]=mapped_column(String(20),default='planned',server_default='planned')
class ServiceReferral(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='service_referrals'; __table_args__=(UniqueConstraint('organisation_id','referral_key',name='uq_service_referral_key'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); referral_key:Mapped[str]=mapped_column(String(160)); source_service_id:Mapped[UUID|None]=mapped_column(ForeignKey('mosque_services.id',ondelete='SET NULL')); receiving_institution_id:Mapped[UUID]=mapped_column(ForeignKey('institutions.id')); evidence_sha256:Mapped[str]=mapped_column(String(64)); status:Mapped[str]=mapped_column(String(20),default='pending',server_default='pending')
class CrisisResponsePlan(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='crisis_response_plans'; __table_args__=(UniqueConstraint('organisation_id','plan_slug','version',name='uq_crisis_response_plan_version'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); plan_slug:Mapped[str]=mapped_column(String(100)); version:Mapped[str]=mapped_column(String(40)); incident_type:Mapped[str]=mapped_column(String(60)); evidence_sha256:Mapped[str]=mapped_column(String(64)); status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class CrisisExercise(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='crisis_exercises'
 plan_id:Mapped[UUID]=mapped_column(ForeignKey('crisis_response_plans.id',ondelete='CASCADE')); scenario:Mapped[str]=mapped_column(String(120)); evidence_sha256:Mapped[str]=mapped_column(String(64)); data_loss_or_harm_detected:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false'); outcome:Mapped[str]=mapped_column(String(20))
class PublicServiceAnalyticsRelease(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='public_service_analytics_releases'; __table_args__=(UniqueConstraint('organisation_id','release_slug','version',name='uq_public_service_analytics_version'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); release_slug:Mapped[str]=mapped_column(String(100)); version:Mapped[str]=mapped_column(String(40)); k_anonymity:Mapped[int]=mapped_column(Integer); minimum_group_size:Mapped[int]=mapped_column(Integer); publication_sha256:Mapped[str]=mapped_column(String(64)); status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class UmmahServicesAcceptance(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='ummah_services_acceptance'; __table_args__=(UniqueConstraint('organisation_id','milestone_version',name='uq_ummah_services_acceptance_version'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); milestone_version:Mapped[str]=mapped_column(String(40)); outcome:Mapped[str]=mapped_column(String(20)); portable_ready:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false'); production_ready:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false'); evidence_sha256:Mapped[str]=mapped_column(String(64)); notes:Mapped[str|None]=mapped_column(Text)
