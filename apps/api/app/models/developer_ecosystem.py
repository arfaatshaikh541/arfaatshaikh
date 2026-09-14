from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class APIProduct(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_products"
    __table_args__ = (
        CheckConstraint("status IN ('draft','active','deprecated','retired')", name="ck_api_product_status"),
        UniqueConstraint("slug", name="uq_api_product_slug"),
    )

    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required_scope: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    public_documentation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class APIVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_versions"
    __table_args__ = (
        CheckConstraint("lifecycle_status IN ('preview','current','deprecated','retired')", name="ck_api_version_lifecycle"),
        CheckConstraint("sunset_notice_days >= 0", name="ck_api_version_sunset_notice"),
        UniqueConstraint("product_id", "version", name="uq_api_version_product_version"),
        Index("ix_api_version_product_status", "product_id", "lifecycle_status"),
    )

    product_id: Mapped[UUID] = mapped_column(ForeignKey("api_products.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[str] = mapped_column(String(24), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(20), nullable=False)
    specification_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    changelog: Mapped[str] = mapped_column(Text, nullable=False)
    breaking_changes: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    sunset_notice_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    successor_version: Mapped[str | None] = mapped_column(String(24), nullable=True)


class APIDocumentationArtifact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_documentation_artifacts"
    __table_args__ = (
        CheckConstraint("artifact_type IN ('openapi','guide','example','changelog')", name="ck_api_documentation_artifact_type"),
        UniqueConstraint("api_version_id", "artifact_type", "locale", name="uq_api_documentation_version_type_locale"),
    )

    api_version_id: Mapped[UUID] = mapped_column(ForeignKey("api_versions.id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(20), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="en", server_default="en")
    content_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class SDKRelease(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sdk_releases"
    __table_args__ = (
        CheckConstraint("language IN ('python','typescript','java','dotnet')", name="ck_sdk_release_language"),
        CheckConstraint("status IN ('draft','published','yanked')", name="ck_sdk_release_status"),
        UniqueConstraint("language", "version", name="uq_sdk_release_language_version"),
    )

    api_version_id: Mapped[UUID] = mapped_column(ForeignKey("api_versions.id", ondelete="RESTRICT"), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    package_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    package_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    tests_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    provenance_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class DeveloperSandboxSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "developer_sandbox_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('active','expired','revoked')", name="ck_developer_sandbox_status"),
        CheckConstraint("request_limit > 0 AND request_limit <= 1000", name="ck_developer_sandbox_limit"),
        CheckConstraint("used_requests >= 0", name="ck_developer_sandbox_usage"),
        Index("ix_developer_sandbox_application_status", "application_id", "status"),
    )

    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("developer_applications.id", ondelete="CASCADE"), nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    allowed_scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    request_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    used_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    expires_at_iso: Mapped[str] = mapped_column(String(40), nullable=False)
