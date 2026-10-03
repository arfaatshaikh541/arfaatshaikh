"""Generic human-review queue; explicit recording rights for recitations.

review_items records decisions people make about things the platform cannot decide itself (Arabic UI strings awaiting a native reader,
mosque names that look wrong, co-located or near-identical listings). It never edits the reviewed data. quran_recitation_editions gains
the rights a holder may grant (owner, territory, streaming, download, redistribution, commercial use); every right defaults to NOT granted,
so existing rows stay unpublishable until someone records evidence.
"""
from alembic import op

revision = "20261003_0088"
down_revision = "20261001_0087"
branch_labels = None
depends_on = None

STATUSES = "'OPEN','KEEP_AS_IS','NEEDS_SOURCE_CHECK','CONFIRMED_DUPLICATE','NEEDS_NATIVE_REVIEW','NATIVE_REVIEW_APPROVED','NATIVE_REVIEW_CHANGES_REQUESTED'"
RIGHTS = ("streaming_allowed", "download_allowed", "redistribution_allowed", "commercial_use_allowed")


def upgrade() -> None:
    op.execute(
        "CREATE TABLE review_items (queue VARCHAR(40) NOT NULL, item_key VARCHAR(300) NOT NULL, group_name VARCHAR(40), payload JSONB DEFAULT '{}' NOT NULL, "
        "status VARCHAR(32) DEFAULT 'OPEN' NOT NULL, note VARCHAR(1000), reviewed_by_user_id UUID, reviewed_at TIMESTAMP WITH TIME ZONE, id UUID NOT NULL, "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "CONSTRAINT pk_review_items PRIMARY KEY (id), CONSTRAINT uq_review_items_queue_key UNIQUE (queue, item_key), "
        f"CONSTRAINT ck_review_items_status CHECK (status IN ({STATUSES})), "
        "CONSTRAINT fk_review_items_reviewed_by_user_id_users FOREIGN KEY(reviewed_by_user_id) REFERENCES users (id) ON DELETE SET NULL)")
    op.execute("CREATE INDEX ix_review_items_queue_status ON review_items (queue, status)")
    op.execute("ALTER TABLE quran_recitation_editions ADD COLUMN recording_owner VARCHAR(300)")
    op.execute("ALTER TABLE quran_recitation_editions ADD COLUMN territory VARCHAR(200)")
    for column in RIGHTS:
        op.execute(f"ALTER TABLE quran_recitation_editions ADD COLUMN {column} BOOLEAN DEFAULT false NOT NULL")
    op.execute("ALTER TABLE quran_recitation_editions ADD CONSTRAINT ck_quran_recitation_editions_offline_needs_download CHECK (NOT offline_allowed OR download_allowed)")


def downgrade() -> None:
    op.execute("ALTER TABLE quran_recitation_editions DROP CONSTRAINT ck_quran_recitation_editions_offline_needs_download")
    for column in RIGHTS:
        op.execute(f"ALTER TABLE quran_recitation_editions DROP COLUMN {column}")
    op.execute("ALTER TABLE quran_recitation_editions DROP COLUMN territory")
    op.execute("ALTER TABLE quran_recitation_editions DROP COLUMN recording_owner")
    op.execute("DROP TABLE review_items")
