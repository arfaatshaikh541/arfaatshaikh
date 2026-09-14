from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DeploymentEnvironment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "deployment_environments"
    __table_args__ = (
        CheckConstraint("environment IN ('development','test','staging','production')", name="ck_deployment_environment_name"),
        UniqueConstraint("environment", name="uq_deployment_environment_name"),
    )
    environment: Mapped[str] = mapped_column(String(24), nullable=False)
    region: Mapped[str] = mapped_column(String(80), nullable=False)
    public_base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    secrets_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    immutable_images_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    backups_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class DeploymentRelease(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "deployment_releases"
    __table_args__ = (
        CheckConstraint("status IN ('draft','approved','deploying','healthy','failed','rolled_back')", name="ck_deployment_release_status"),
        Index("ix_deployment_release_environment_created", "environment_id", "created_at"),
    )
    environment_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_environments.id", ondelete="RESTRICT"), nullable=False)
    release_version: Mapped[str] = mapped_column(String(120), nullable=False)
    image_digest: Mapped[str] = mapped_column(String(160), nullable=False)
    migration_revision: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", server_default="draft")
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    release_manifest: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")


class DeploymentVerification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "deployment_verifications"
    __table_args__ = (
        CheckConstraint("check_type IN ('config','secrets','migration','health','readiness','backup','rollback')", name="ck_deployment_verification_type"),
        CheckConstraint("status IN ('passed','failed','blocked')", name="ck_deployment_verification_status"),
        UniqueConstraint("release_id", "check_type", name="uq_deployment_verification_release_check"),
    )
    release_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_releases.id", ondelete="CASCADE"), nullable=False)
    check_type: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    verified_by: Mapped[str] = mapped_column(String(160), nullable=False)


class BackupRestoreRehearsal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "backup_restore_rehearsals"
    __table_args__ = (
        CheckConstraint("status IN ('scheduled','running','passed','failed')", name="ck_backup_restore_rehearsal_status"),
        CheckConstraint("restore_time_seconds >= 0", name="ck_backup_restore_time_nonnegative"),
        Index("ix_backup_restore_environment_created", "environment_id", "created_at"),
    )
    environment_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_environments.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="scheduled", server_default="scheduled")
    encrypted_backup_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    restore_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    recovery_point: Mapped[str | None] = mapped_column(String(120), nullable=True)
    evidence_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
