from uuid import UUID
from sqlalchemy import Boolean,ForeignKey,Integer,JSON,String,Text,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.db.base import Base,TimestampMixin,UUIDPrimaryKeyMixin
class FederationNetwork(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='federation_networks';__table_args__=(UniqueConstraint('organisation_id','slug',name='uq_federation_network_slug'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE'));slug:Mapped[str]=mapped_column(String(100));name:Mapped[str]=mapped_column(String(200));manifest_sha256:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class FederationMember(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='federation_members';__table_args__=(UniqueConstraint('network_id','institution_id',name='uq_federation_member'),)
 network_id:Mapped[UUID]=mapped_column(ForeignKey('federation_networks.id',ondelete='CASCADE'));institution_id:Mapped[UUID]=mapped_column(ForeignKey('institutions.id',ondelete='CASCADE'));jurisdiction_code:Mapped[str]=mapped_column(String(2));status:Mapped[str]=mapped_column(String(20),default='pending',server_default='pending');capabilities_json:Mapped[dict]=mapped_column(JSON,default=dict,server_default='{}')
class FederationTrustPolicy(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='federation_trust_policies';__table_args__=(UniqueConstraint('network_id','version',name='uq_federation_trust_policy_version'),)
 network_id:Mapped[UUID]=mapped_column(ForeignKey('federation_networks.id',ondelete='CASCADE'));version:Mapped[str]=mapped_column(String(40));policy_sha256:Mapped[str]=mapped_column(String(64));published:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
class FederatedIdentityCredential(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='federated_identity_credentials';__table_args__=(UniqueConstraint('issuer_institution_id','subject_key',name='uq_federated_identity_subject'),)
 issuer_institution_id:Mapped[UUID]=mapped_column(ForeignKey('institutions.id',ondelete='CASCADE'));subject_key:Mapped[str]=mapped_column(String(160));assurance_level:Mapped[int]=mapped_column(Integer);proof_sha256:Mapped[str]=mapped_column(String(64));revoked:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
class InteroperabilityProfile(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='interoperability_profiles';__table_args__=(UniqueConstraint('network_id','profile_slug','version',name='uq_interop_profile_version'),)
 network_id:Mapped[UUID]=mapped_column(ForeignKey('federation_networks.id',ondelete='CASCADE'));profile_slug:Mapped[str]=mapped_column(String(100));version:Mapped[str]=mapped_column(String(40));schema_sha256:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class InteroperabilityConformanceRun(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='interoperability_conformance_runs'
 profile_id:Mapped[UUID]=mapped_column(ForeignKey('interoperability_profiles.id',ondelete='CASCADE'));member_id:Mapped[UUID]=mapped_column(ForeignKey('federation_members.id',ondelete='CASCADE'));tests_passed:Mapped[int]=mapped_column(Integer);tests_failed:Mapped[int]=mapped_column(Integer);evidence_sha256:Mapped[str]=mapped_column(String(64));outcome:Mapped[str]=mapped_column(String(20))
class FederatedSearchNode(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='federated_search_nodes';__table_args__=(UniqueConstraint('network_id','node_slug',name='uq_federated_search_node'),)
 network_id:Mapped[UUID]=mapped_column(ForeignKey('federation_networks.id',ondelete='CASCADE'));node_slug:Mapped[str]=mapped_column(String(100));institution_id:Mapped[UUID]=mapped_column(ForeignKey('institutions.id',ondelete='CASCADE'));endpoint_fingerprint:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default='offline',server_default='offline')
class FederatedSearchEvaluation(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='federated_search_evaluations'
 network_id:Mapped[UUID]=mapped_column(ForeignKey('federation_networks.id',ondelete='CASCADE'));grounding_percent:Mapped[int]=mapped_column(Integer);attribution_percent:Mapped[int]=mapped_column(Integer);harmful_rate_basis_points:Mapped[int]=mapped_column(Integer);p95_timeout_ms:Mapped[int]=mapped_column(Integer);outcome:Mapped[str]=mapped_column(String(20))
class DataSharingAgreement(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='data_sharing_agreements';__table_args__=(UniqueConstraint('network_id','agreement_slug','version',name='uq_data_sharing_agreement_version'),)
 network_id:Mapped[UUID]=mapped_column(ForeignKey('federation_networks.id',ondelete='CASCADE'));agreement_slug:Mapped[str]=mapped_column(String(100));version:Mapped[str]=mapped_column(String(40));purpose:Mapped[str]=mapped_column(Text);retention_days:Mapped[int]=mapped_column(Integer);policy_sha256:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class ConsentReceipt(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='consent_receipts';__table_args__=(UniqueConstraint('agreement_id','subject_reference','receipt_sha256',name='uq_consent_receipt'),)
 agreement_id:Mapped[UUID]=mapped_column(ForeignKey('data_sharing_agreements.id',ondelete='CASCADE'));subject_reference:Mapped[str]=mapped_column(String(160));purposes_json:Mapped[dict]=mapped_column(JSON,default=dict,server_default='{}');receipt_sha256:Mapped[str]=mapped_column(String(64));withdrawn:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
class CrossBorderScholarlyProject(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='cross_border_scholarly_projects';__table_args__=(UniqueConstraint('network_id','project_slug',name='uq_cross_border_project_slug'),)
 network_id:Mapped[UUID]=mapped_column(ForeignKey('federation_networks.id',ondelete='CASCADE'));project_slug:Mapped[str]=mapped_column(String(100));title:Mapped[str]=mapped_column(String(240));methodology_sha256:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class CrossBorderScholarParticipant(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='cross_border_scholar_participants';__table_args__=(UniqueConstraint('project_id','scholar_profile_id',name='uq_cross_border_scholar'),)
 project_id:Mapped[UUID]=mapped_column(ForeignKey('cross_border_scholarly_projects.id',ondelete='CASCADE'));scholar_profile_id:Mapped[UUID]=mapped_column(ForeignKey('scholar_profiles.id',ondelete='CASCADE'));institution_id:Mapped[UUID]=mapped_column(ForeignKey('institutions.id',ondelete='CASCADE'));role:Mapped[str]=mapped_column(String(60));conflict_disclosed:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
class FederationResilienceExercise(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='federation_resilience_exercises'
 network_id:Mapped[UUID]=mapped_column(ForeignKey('federation_networks.id',ondelete='CASCADE'));scenario:Mapped[str]=mapped_column(String(160));healthy_nodes:Mapped[int]=mapped_column(Integer);recovery_minutes:Mapped[int]=mapped_column(Integer);evidence_sha256:Mapped[str]=mapped_column(String(64));outcome:Mapped[str]=mapped_column(String(20))
class FederationTransparencyReport(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='federation_transparency_reports';__table_args__=(UniqueConstraint('network_id','report_slug','version',name='uq_federation_transparency_version'),)
 network_id:Mapped[UUID]=mapped_column(ForeignKey('federation_networks.id',ondelete='CASCADE'));report_slug:Mapped[str]=mapped_column(String(100));version:Mapped[str]=mapped_column(String(40));publication_sha256:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default='draft',server_default='draft')
class FederationAuditReview(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='federation_audit_reviews'
 network_id:Mapped[UUID]=mapped_column(ForeignKey('federation_networks.id',ondelete='CASCADE'));member_coverage_percent:Mapped[int]=mapped_column(Integer);critical_findings:Mapped[int]=mapped_column(Integer);evidence_sha256:Mapped[str]=mapped_column(String(64));outcome:Mapped[str]=mapped_column(String(20))
class GlobalUmmahNetworkAcceptance(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='global_ummah_network_acceptance';__table_args__=(UniqueConstraint('network_id','milestone_version',name='uq_global_ummah_acceptance_version'),)
 network_id:Mapped[UUID]=mapped_column(ForeignKey('federation_networks.id',ondelete='CASCADE'));milestone_version:Mapped[str]=mapped_column(String(40));outcome:Mapped[str]=mapped_column(String(20));portable_ready:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false');production_ready:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false');evidence_sha256:Mapped[str]=mapped_column(String(64));notes:Mapped[str|None]=mapped_column(Text)
