from uuid import UUID
from sqlalchemy import Boolean,ForeignKey,Integer,JSON,String,Text,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.db.base import Base,TimestampMixin,UUIDPrimaryKeyMixin
class PrayerTimeAuthority(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='prayer_time_authorities';__table_args__=(UniqueConstraint('organisation_id','authority_slug',name='uq_prayer_time_authority'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));authority_slug:Mapped[str]=mapped_column(String(120));jurisdiction_code:Mapped[str]=mapped_column(String(8));verified:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
class PrayerCalculationProfile(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='prayer_calculation_profiles';__table_args__=(UniqueConstraint('organisation_id','profile_slug','version',name='uq_prayer_calculation_profile'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));profile_slug:Mapped[str]=mapped_column(String(120));version:Mapped[str]=mapped_column(String(40));method_code:Mapped[str]=mapped_column(String(80));manifest_sha256:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class PrayerTimeVerification(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='prayer_time_verifications';profile_id:Mapped[UUID]=mapped_column(ForeignKey('prayer_calculation_profiles.id',ondelete='CASCADE'));validation_percent:Mapped[int]=mapped_column(Integer);evidence_sha256:Mapped[str]=mapped_column(String(64));outcome:Mapped[str]=mapped_column(String(20))
class HijriCalendarAuthority(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='hijri_calendar_authorities';__table_args__=(UniqueConstraint('organisation_id','authority_slug','jurisdiction_code',name='uq_hijri_calendar_authority'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));authority_slug:Mapped[str]=mapped_column(String(120));jurisdiction_code:Mapped[str]=mapped_column(String(8));methodology_sha256:Mapped[str]=mapped_column(String(64));verified:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
class HalalStandard(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='halal_standards';__table_args__=(UniqueConstraint('organisation_id','standard_slug','version',name='uq_halal_standard'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));standard_slug:Mapped[str]=mapped_column(String(120));version:Mapped[str]=mapped_column(String(40));standard_sha256:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class HalalCertificationRecord(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='halal_certification_records';__table_args__=(UniqueConstraint('standard_id','certificate_reference',name='uq_halal_certificate_reference'),)
 standard_id:Mapped[UUID]=mapped_column(ForeignKey('halal_standards.id',ondelete='CASCADE'));certificate_reference:Mapped[str]=mapped_column(String(180));certifier_reference:Mapped[str]=mapped_column(String(180));certificate_sha256:Mapped[str]=mapped_column(String(64));revoked:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
class ProductTraceabilityRecord(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='product_traceability_records';certification_id:Mapped[UUID]=mapped_column(ForeignKey('halal_certification_records.id',ondelete='CASCADE'));product_reference:Mapped[str]=mapped_column(String(180));traceability_percent:Mapped[int]=mapped_column(Integer);supply_chain_json:Mapped[dict]=mapped_column(JSON,default=dict,server_default='{}');evidence_sha256:Mapped[str]=mapped_column(String(64))
class EthicalCommerceReview(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='ethical_commerce_reviews';organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));merchant_reference:Mapped[str]=mapped_column(String(180));traceability_percent:Mapped[int]=mapped_column(Integer);evidence_sha256:Mapped[str]=mapped_column(String(64));outcome:Mapped[str]=mapped_column(String(20))
class IslamicFinanceProduct(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='islamic_finance_products';__table_args__=(UniqueConstraint('organisation_id','product_slug','version',name='uq_islamic_finance_product'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));product_slug:Mapped[str]=mapped_column(String(120));version:Mapped[str]=mapped_column(String(40));contract_type:Mapped[str]=mapped_column(String(80));disclosure_sha256:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class ShariahBoardReview(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='shariah_board_reviews';product_id:Mapped[UUID]=mapped_column(ForeignKey('islamic_finance_products.id',ondelete='CASCADE'));reviewer_count:Mapped[int]=mapped_column(Integer);critical_findings:Mapped[int]=mapped_column(Integer);evidence_sha256:Mapped[str]=mapped_column(String(64));outcome:Mapped[str]=mapped_column(String(20))
class ContractDisclosure(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='contract_disclosures';product_id:Mapped[UUID]=mapped_column(ForeignKey('islamic_finance_products.id',ondelete='CASCADE'));language_code:Mapped[str]=mapped_column(String(16));fees_disclosed:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false');late_payment_treatment_disclosed:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false');document_sha256:Mapped[str]=mapped_column(String(64))
class CharityFinanceReconciliation(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='charity_finance_reconciliations';organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));period_reference:Mapped[str]=mapped_column(String(40));ledger_sha256:Mapped[str]=mapped_column(String(64));unreconciled_items:Mapped[int]=mapped_column(Integer);outcome:Mapped[str]=mapped_column(String(20))
class FamilyServiceProgramme(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='family_service_programmes';__table_args__=(UniqueConstraint('organisation_id','programme_slug','version',name='uq_family_service_programme'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));programme_slug:Mapped[str]=mapped_column(String(120));version:Mapped[str]=mapped_column(String(40));safeguarding_sha256:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class FamilyCaseSafeguard(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='family_case_safeguards';programme_id:Mapped[UUID]=mapped_column(ForeignKey('family_service_programmes.id',ondelete='CASCADE'));case_reference:Mapped[str]=mapped_column(String(180));risk_level:Mapped[str]=mapped_column(String(20));escalation_active:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false');evidence_sha256:Mapped[str]=mapped_column(String(64))
class HeritageSiteRecord(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='heritage_site_records';__table_args__=(UniqueConstraint('organisation_id','site_slug',name='uq_heritage_site_record'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));site_slug:Mapped[str]=mapped_column(String(120));jurisdiction_code:Mapped[str]=mapped_column(String(8));significance_sha256:Mapped[str]=mapped_column(String(64));conservation_status:Mapped[str]=mapped_column(String(30))
class TrustedIslamicLifeAcceptance(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='trusted_islamic_life_acceptance';__table_args__=(UniqueConstraint('organisation_id','milestone_version',name='uq_trusted_islamic_life_acceptance'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));milestone_version:Mapped[str]=mapped_column(String(40));outcome:Mapped[str]=mapped_column(String(20));portable_ready:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false');production_ready:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false');evidence_sha256:Mapped[str]=mapped_column(String(64));notes:Mapped[str|None]=mapped_column(Text)
