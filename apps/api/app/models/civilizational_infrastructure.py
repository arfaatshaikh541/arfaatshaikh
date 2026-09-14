from uuid import UUID
from sqlalchemy import Boolean,CheckConstraint,ForeignKey,Integer,JSON,String,Text,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.db.base import Base,TimestampMixin,UUIDPrimaryKeyMixin
class PreservationArchive(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='preservation_archives'; __table_args__=(UniqueConstraint('organisation_id','slug','version',name='uq_preservation_archive_version'),CheckConstraint("status IN ('building','sealed','verified','invalidated')",name='ck_preservation_archive_status'))
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); slug:Mapped[str]=mapped_column(String(100)); version:Mapped[str]=mapped_column(String(40)); content_type:Mapped[str]=mapped_column(String(40)); manifest_sha256:Mapped[str]=mapped_column(String(64)); source_sha256:Mapped[str]=mapped_column(String(64)); status:Mapped[str]=mapped_column(String(16),default='building',server_default='building'); retention_years:Mapped[int]=mapped_column(Integer)
class ArchiveObject(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='archive_objects'; __table_args__=(UniqueConstraint('archive_id','object_path',name='uq_archive_object_path'),)
 archive_id:Mapped[UUID]=mapped_column(ForeignKey('preservation_archives.id',ondelete='CASCADE')); object_path:Mapped[str]=mapped_column(String(500)); object_sha256:Mapped[str]=mapped_column(String(64)); size_bytes:Mapped[int]=mapped_column(Integer); media_type:Mapped[str|None]=mapped_column(String(120))
class ArchiveReplica(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='archive_replicas'; __table_args__=(UniqueConstraint('archive_id','region','provider_slug',name='uq_archive_replica_location'),)
 archive_id:Mapped[UUID]=mapped_column(ForeignKey('preservation_archives.id',ondelete='CASCADE')); region:Mapped[str]=mapped_column(String(40)); provider_slug:Mapped[str]=mapped_column(String(100)); endpoint_url:Mapped[str]=mapped_column(String(500)); air_gapped:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false'); status:Mapped[str]=mapped_column(String(16),default='pending',server_default='pending')
class ArchiveFixityCheck(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='archive_fixity_checks'
 archive_id:Mapped[UUID]=mapped_column(ForeignKey('preservation_archives.id',ondelete='CASCADE')); expected_sha256:Mapped[str]=mapped_column(String(64)); observed_sha256:Mapped[str]=mapped_column(String(64)); outcome:Mapped[str]=mapped_column(String(16)); objects_verified:Mapped[int]=mapped_column(Integer); unreadable_objects:Mapped[int]=mapped_column(Integer,default=0,server_default='0'); evidence_json:Mapped[dict]=mapped_column(JSON,default=dict,server_default='{}')
class SemanticIndex(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='semantic_indexes'; __table_args__=(UniqueConstraint('organisation_id','slug','version',name='uq_semantic_index_version'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); slug:Mapped[str]=mapped_column(String(100)); version:Mapped[str]=mapped_column(String(40)); content_type:Mapped[str]=mapped_column(String(40)); model_sha256:Mapped[str]=mapped_column(String(64)); index_sha256:Mapped[str]=mapped_column(String(64)); source_coverage_percent:Mapped[int]=mapped_column(Integer); status:Mapped[str]=mapped_column(String(16),default='building',server_default='building')
class SearchCorpusShard(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='search_corpus_shards'; __table_args__=(UniqueConstraint('semantic_index_id','shard_key',name='uq_search_corpus_shard_key'),)
 semantic_index_id:Mapped[UUID]=mapped_column(ForeignKey('semantic_indexes.id',ondelete='CASCADE')); shard_key:Mapped[str]=mapped_column(String(100)); document_count:Mapped[int]=mapped_column(Integer); shard_sha256:Mapped[str]=mapped_column(String(64)); storage_uri:Mapped[str]=mapped_column(String(500))
class SearchQualityEvaluation(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='search_quality_evaluations'
 semantic_index_id:Mapped[UUID]=mapped_column(ForeignKey('semantic_indexes.id',ondelete='CASCADE')); precision_at_10:Mapped[int]=mapped_column(Integer); recall_at_10:Mapped[int]=mapped_column(Integer); grounding_rate:Mapped[int]=mapped_column(Integer); harmful_result_rate:Mapped[int]=mapped_column(Integer); outcome:Mapped[str]=mapped_column(String(16)); evidence_sha256:Mapped[str]=mapped_column(String(64))
class OfflineDistributionPackage(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='offline_distribution_packages'; __table_args__=(UniqueConstraint('organisation_id','package_slug','version',name='uq_offline_package_version'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); package_slug:Mapped[str]=mapped_column(String(100)); version:Mapped[str]=mapped_column(String(40)); manifest_sha256:Mapped[str]=mapped_column(String(64)); package_sha256:Mapped[str]=mapped_column(String(64)); size_mb:Mapped[int]=mapped_column(Integer); status:Mapped[str]=mapped_column(String(16),default='draft',server_default='draft')
class OfflinePackageRelease(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='offline_package_releases'
 package_id:Mapped[UUID]=mapped_column(ForeignKey('offline_distribution_packages.id',ondelete='CASCADE')); channel:Mapped[str]=mapped_column(String(40)); signature_sha256:Mapped[str]=mapped_column(String(64)); expires_at_iso:Mapped[str]=mapped_column(String(40)); revocation_list_sha256:Mapped[str]=mapped_column(String(64)); status:Mapped[str]=mapped_column(String(16),default='pending',server_default='pending')
class OfflineUpdateDelta(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='offline_update_deltas'; __table_args__=(UniqueConstraint('base_package_id','target_package_id',name='uq_offline_update_transition'),)
 base_package_id:Mapped[UUID]=mapped_column(ForeignKey('offline_distribution_packages.id',ondelete='CASCADE')); target_package_id:Mapped[UUID]=mapped_column(ForeignKey('offline_distribution_packages.id',ondelete='CASCADE')); delta_sha256:Mapped[str]=mapped_column(String(64)); size_mb:Mapped[int]=mapped_column(Integer); rollback_sha256:Mapped[str]=mapped_column(String(64))
class ResilienceRegion(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='resilience_regions'; __table_args__=(UniqueConstraint('organisation_id','region',name='uq_resilience_region'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); region:Mapped[str]=mapped_column(String(40)); role:Mapped[str]=mapped_column(String(20)); health_status:Mapped[str]=mapped_column(String(20)); replication_lag_seconds:Mapped[int]=mapped_column(Integer,default=0,server_default='0'); endpoint_url:Mapped[str]=mapped_column(String(500))
class FailoverExercise(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='failover_exercises'
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); exercise_version:Mapped[str]=mapped_column(String(40)); rpo_seconds:Mapped[int]=mapped_column(Integer); rto_seconds:Mapped[int]=mapped_column(Integer); data_loss_detected:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false'); outcome:Mapped[str]=mapped_column(String(16)); evidence_sha256:Mapped[str]=mapped_column(String(64))
class ObservabilityCoverage(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='observability_coverages'; __table_args__=(UniqueConstraint('organisation_id','coverage_version',name='uq_observability_coverage_version'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); coverage_version:Mapped[str]=mapped_column(String(40)); metrics_percent:Mapped[int]=mapped_column(Integer); traces_percent:Mapped[int]=mapped_column(Integer); logs_integrity_verified:Mapped[bool]=mapped_column(Boolean); redaction_verified:Mapped[bool]=mapped_column(Boolean); evidence_sha256:Mapped[str]=mapped_column(String(64))
class CapacityBenchmark(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='capacity_benchmarks'
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); benchmark_version:Mapped[str]=mapped_column(String(40)); tested_rps:Mapped[int]=mapped_column(Integer); p95_latency_ms:Mapped[int]=mapped_column(Integer); error_rate_basis_points:Mapped[int]=mapped_column(Integer); corpus_millions:Mapped[int]=mapped_column(Integer); headroom_percent:Mapped[int]=mapped_column(Integer); evidence_sha256:Mapped[str]=mapped_column(String(64))
class CivilizationalInfrastructureAcceptance(UUIDPrimaryKeyMixin,TimestampMixin,Base):
 __tablename__='civilizational_infrastructure_acceptances'; __table_args__=(UniqueConstraint('organisation_id','milestone_version',name='uq_civilizational_acceptance_version'),)
 organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id',ondelete='CASCADE')); milestone_version:Mapped[str]=mapped_column(String(40)); outcome:Mapped[str]=mapped_column(String(16)); portable_ready:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false'); production_ready:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false'); evidence_sha256:Mapped[str]=mapped_column(String(64)); notes:Mapped[str|None]=mapped_column(Text)
