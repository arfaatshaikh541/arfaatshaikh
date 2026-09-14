# Tafsir reader and private study tools

The integrated reader returns only published authors, collections, editions, entries, translations, and reviewed cross-references. Commentary is displayed by edition and author; translations are separately attributed. Cross-reference confidence is not exposed as theological certainty.

Bookmarks, notes, collections, and progress are owned by one authenticated user. All mutations require CSRF validation. Private notes never become source text and cannot be surfaced as published commentary.

Canonical route: `/{locale}/tafsir/{surah}/{ayah}`. Stable entry anchors use `#tafsir-{entry_id}`.
