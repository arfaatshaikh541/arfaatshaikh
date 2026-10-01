"""Diacritic-insensitive full-text search over Qur'an, hadith and tafsir text.

A plain ILIKE over 400 MB of tafsir takes seconds and cannot match text written with tashkeel. This adds an IMMUTABLE
normalising function (drops tashkeel and tatweel, folds alef/ya/ta-marbuta variants) and GIN indexes over
to_tsvector('simple', woi_ar_norm(text)), so word searches are index-backed and ignore vocalisation.
"""
from alembic import op

revision = "20261001_0085"
down_revision = "20261001_0084"
branch_labels = None
depends_on = None

MARKS = "".join(chr(c) for c in range(0x064B, 0x0660)) + chr(0x0670) + "".join(chr(c) for c in range(0x06D6, 0x06EE)) + chr(0x0640)
FROM_CHARS = "أإآٱىة"
TO_CHARS = "اااايه"

FUNCTION = f"""
CREATE FUNCTION woi_ar_norm(t text) RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS
$$ SELECT regexp_replace(translate(t, '{FROM_CHARS}', '{TO_CHARS}'), '[{MARKS}]', '', 'g') $$
"""

INDEXES = [
    ("ix_quran_ayahs_ar_fts", "quran_ayahs", "arabic_text"),
    ("ix_hadith_narrations_ar_fts", "hadith_narrations", "arabic_matn"),
    ("ix_tafsir_entries_ar_fts", "tafsir_entries", "arabic_text"),
]


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(FUNCTION)
    for name, table, column in INDEXES:
        bind.exec_driver_sql(f"CREATE INDEX {name} ON {table} USING gin (to_tsvector('simple', woi_ar_norm({column})))")


def downgrade() -> None:
    for name, _, _ in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
    op.execute("DROP FUNCTION IF EXISTS woi_ar_norm(text)")
