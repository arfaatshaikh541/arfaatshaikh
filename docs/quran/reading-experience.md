# Qur’an reading experience

The reader exposes only ayahs from the published canonical text edition. A missing canonical edition returns `quran_corpus_unavailable`; the UI shows a trust notice and never substitutes sample scripture.

## Public reads

- `GET /quran/surahs/{number}/reading`
- Optional `translation` query parameter selects one published translation edition.
- Ayahs are returned in canonical order with stable `surah:ayah` references and fragment-compatible deep links.

## Private reading state

Bookmarks and reading progress are bound to the authenticated user. Mutations require session authentication and CSRF validation. Bookmark uniqueness prevents duplicate records. Reading progress is a single upserted resume point per user.

## Accessibility

Arabic is rendered with `dir=rtl` and `lang=ar`. Status changes use a live status region. Navigation and ayah references remain usable without JavaScript-generated URLs.
