from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DeveloperPartner(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "developer_partners"
    __table_args__ = (
        CheckConstraint("status IN ('applicant','verified','suspended','revoked')", name="ck_developer_partner_status"),
        UniqueConstraint("organisation_id", name="uq_developer_partner_organisation"),
    )

    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="applicant", server_default="applicant")
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    website_url: Mapped[str] = mapped_column(String(500), nullable=False)
    privacy_contact: Mapped[str] = mapped_column(String(254), nullable=False)
    terms_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class IntegrationListing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "integration_listings"
    __table_args__ = (
        CheckConstraint("status IN ('draft','review','published','suspended','retired')", name="ck_integration_listing_status"),
        UniqueConstraint("slug", name="uq_integration_listing_slug"),
        Index("ix_integration_listing_partner_status", "partner_id", "status"),
    )

    partner_id: Mapped[UUID] = mapped_column(ForeignKey("developer_partners.id", ondelete="CASCADE"), nullable=False)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("developer_applications.id", ondelete="RESTRICT"), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requested_scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    support_url: Mapped[str] = mapped_column(String(500), nullable=False)


class IntegrationSecurityReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "integration_security_reviews"
    __table_args__ = (
        CheckConstraint("status IN ('pending','passed','failed','expired')", name="ck_integration_security_review_status"),
        CheckConstraint("critical_findings >= 0 AND high_findings >= 0", name="ck_integration_security_review_findings"),
        Index("ix_integration_security_review_listing_status", "listing_id", "status"),
    )

    listing_id: Mapped[UUID] = mapped_column(ForeignKey("integration_listings.id", ondelete="CASCADE"), nullable=False)
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    critical_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    high_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    data_minimisation_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    deletion_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class IntegrationCertification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "integration_certifications"
    __table_args__ = (
        CheckConstraint("status IN ('active','expired','revoked')", name="ck_integration_certification_status"),
        UniqueConstraint("listing_id", "certificate_version", name="uq_integration_certification_listing_version"),
    )

    listing_id: Mapped[UUID] = mapped_column(ForeignKey("integration_listings.id", ondelete="CASCADE"), nullable=False)
    security_review_id: Mapped[UUID] = mapped_column(ForeignKey("integration_security_reviews.id", ondelete="RESTRICT"), nullable=False)
    certificate_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    expires_at_iso: Mapped[str] = mapped_column(String(40), nullable=False)
    certification_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class PartnerSecurityIncident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "partner_security_incidents"
    __table_args__ = (
        CheckConstraint("severity IN ('low','medium','high','critical')", name="ck_partner_security_incident_severity"),
        CheckConstraint("status IN ('open','contained','resolved')", name="ck_partner_security_incident_status"),
        Index("ix_partner_security_incident_partner_status", "partner_id", "status"),
    )

    partner_id: Mapped[UUID] = mapped_column(ForeignKey("developer_partners.id", ondelete="CASCADE"), nullable=False)
    listing_id: Mapped[UUID | None] = mapped_column(ForeignKey("integration_listings.id", ondelete="SET NULL"), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", server_default="open")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    credentials_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
