"""Source-level provenance and type-specific structure for knowledge records; job/event/volunteering fields for listings.

knowledge_records gains source_work, edition, volume, page, chapter, language, publication_status, license_status,
provenance_status and an `attributes` document (madhhab/question/ruling/evidence for fiqh, school/statement for aqeedah,
per-grader grades for hadith grading ...). directory_listings gains `attributes` (employer, salary, employment type,
application URL, opening hours, facilities ...), expires_at, posted_at and last_verified. quran_recitation_editions gains
delivery_mode (hosted / external_link), licence status and name, rights_authorization, source_url and caching/offline
permissions, and quran_ayah_audio checksums become optional (required by the service for hosted recordings). Existing rows
keep their meaning: new columns default to 'unspecified' / 'UNKNOWN' / 'unclear' / an empty document / 'hosted'.
Downgrade removes external-link recordings (they cannot satisfy the old NOT NULL checksum columns).
"""
from alembic import op

revision = "20261001_0086"
down_revision = "20261001_0085"
branch_labels = None
depends_on = None

LICENSES = "'VERIFIED_OPEN','PUBLIC_DOMAIN','PD_WORK_OPEN_EDITION_DECLARED','OWNER_PERMISSION_GRANTED','LICENSE_REQUIRED','PROVENANCE_UNCLEAR','UNKNOWN'"

UP = [
    "ALTER TABLE knowledge_records ADD COLUMN source_work VARCHAR(500)",
    "ALTER TABLE knowledge_records ADD COLUMN edition VARCHAR(300)",
    "ALTER TABLE knowledge_records ADD COLUMN volume VARCHAR(80)",
    "ALTER TABLE knowledge_records ADD COLUMN page VARCHAR(80)",
    "ALTER TABLE knowledge_records ADD COLUMN chapter VARCHAR(300)",
    "ALTER TABLE knowledge_records ADD COLUMN language VARCHAR(24)",
    "ALTER TABLE knowledge_records ADD COLUMN publication_status VARCHAR(24) DEFAULT 'unspecified' NOT NULL",
    "ALTER TABLE knowledge_records ADD COLUMN license_status VARCHAR(40) DEFAULT 'UNKNOWN' NOT NULL",
    "ALTER TABLE knowledge_records ADD COLUMN provenance_status VARCHAR(24) DEFAULT 'unclear' NOT NULL",
    "ALTER TABLE knowledge_records ADD COLUMN attributes JSONB DEFAULT '{}' NOT NULL",
    f"ALTER TABLE knowledge_records ADD CONSTRAINT ck_knowledge_records_license_status CHECK (license_status IN ({LICENSES}))",
    "ALTER TABLE knowledge_records ADD CONSTRAINT ck_knowledge_records_publication_status CHECK (publication_status IN ('published_edition','manuscript','online_resource','dataset','unspecified'))",
    "ALTER TABLE knowledge_records ADD CONSTRAINT ck_knowledge_records_provenance_status CHECK (provenance_status IN ('source_and_page_cited','source_cited','unclear'))",
    "CREATE INDEX ix_knowledge_records_attributes ON knowledge_records USING gin (attributes jsonb_path_ops)",
    "ALTER TABLE directory_listings ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE directory_listings ADD COLUMN posted_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE directory_listings ADD COLUMN last_verified DATE",
    "ALTER TABLE directory_listings ADD COLUMN attributes JSONB DEFAULT '{}' NOT NULL",
    "CREATE INDEX ix_directory_listings_expiry ON directory_listings (expires_at, ends_at)",
    # recitation audio: hosted (checksummed files) or an external link; licence, authorisation and caching/offline permissions are explicit
    "ALTER TABLE quran_recitation_editions ADD COLUMN delivery_mode VARCHAR(16) DEFAULT 'hosted' NOT NULL",
    f"ALTER TABLE quran_recitation_editions ADD COLUMN license_status VARCHAR(40) DEFAULT 'LICENSE_REQUIRED' NOT NULL",
    "ALTER TABLE quran_recitation_editions ADD COLUMN license_name VARCHAR(240)",
    "ALTER TABLE quran_recitation_editions ADD COLUMN rights_authorization TEXT",
    "ALTER TABLE quran_recitation_editions ADD COLUMN source_url VARCHAR(800)",
    "ALTER TABLE quran_recitation_editions ADD COLUMN caching_allowed BOOLEAN DEFAULT false NOT NULL",
    "ALTER TABLE quran_recitation_editions ADD COLUMN offline_allowed BOOLEAN DEFAULT false NOT NULL",
    "ALTER TABLE quran_recitation_editions ADD CONSTRAINT ck_quran_recitation_editions_delivery_mode CHECK (delivery_mode IN ('hosted','external_link'))",
    f"ALTER TABLE quran_recitation_editions ADD CONSTRAINT ck_quran_recitation_editions_license_status CHECK (license_status IN ({LICENSES}))",
    "ALTER TABLE quran_recitation_editions ADD CONSTRAINT ck_quran_recitation_editions_offline_needs_cache CHECK (NOT offline_allowed OR caching_allowed)",
    "ALTER TABLE quran_ayah_audio ALTER COLUMN audio_sha256 DROP NOT NULL, ALTER COLUMN duration_ms DROP NOT NULL, ALTER COLUMN octet_size DROP NOT NULL",
    "ALTER TABLE quran_ayah_audio ADD CONSTRAINT ck_quran_ayah_audio_checksum_pair CHECK ((audio_sha256 IS NULL) = (octet_size IS NULL))",
]
DOWN = [
    "ALTER TABLE quran_ayah_audio DROP CONSTRAINT ck_quran_ayah_audio_checksum_pair",
    "DELETE FROM quran_ayah_audio WHERE audio_sha256 IS NULL OR duration_ms IS NULL OR octet_size IS NULL",
    "ALTER TABLE quran_ayah_audio ALTER COLUMN audio_sha256 SET NOT NULL, ALTER COLUMN duration_ms SET NOT NULL, ALTER COLUMN octet_size SET NOT NULL",
    "ALTER TABLE quran_recitation_editions DROP CONSTRAINT ck_quran_recitation_editions_offline_needs_cache, DROP CONSTRAINT ck_quran_recitation_editions_license_status, DROP CONSTRAINT ck_quran_recitation_editions_delivery_mode",
    "ALTER TABLE quran_recitation_editions DROP COLUMN offline_allowed, DROP COLUMN caching_allowed, DROP COLUMN source_url, DROP COLUMN rights_authorization, DROP COLUMN license_name, DROP COLUMN license_status, DROP COLUMN delivery_mode",
    "DROP INDEX IF EXISTS ix_directory_listings_expiry",
    "ALTER TABLE directory_listings DROP COLUMN attributes, DROP COLUMN last_verified, DROP COLUMN posted_at, DROP COLUMN expires_at",
    "DROP INDEX IF EXISTS ix_knowledge_records_attributes",
    "ALTER TABLE knowledge_records DROP CONSTRAINT ck_knowledge_records_provenance_status, DROP CONSTRAINT ck_knowledge_records_publication_status, DROP CONSTRAINT ck_knowledge_records_license_status",
    "ALTER TABLE knowledge_records DROP COLUMN attributes, DROP COLUMN provenance_status, DROP COLUMN license_status, DROP COLUMN publication_status, "
    "DROP COLUMN language, DROP COLUMN chapter, DROP COLUMN page, DROP COLUMN volume, DROP COLUMN edition, DROP COLUMN source_work",
]


def upgrade() -> None:
    bind = op.get_bind()
    for statement in UP:
        bind.exec_driver_sql(statement)


def downgrade() -> None:
    bind = op.get_bind()
    for statement in DOWN:
        bind.exec_driver_sql(statement)
