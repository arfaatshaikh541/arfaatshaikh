# Canonical Tafsir Foundation

Milestone 5 Unit 1 introduces a provenance-first model for authored Qur'anic commentary. Tafsir remains distinct from canonical Qur'an text and from platform-authored explanations.

## Trust rules

- Authors require current Source Registry passage evidence.
- Editions require an approved, ingestion-ready, retrieval-eligible source edition.
- Volumes, sections, entries, and translations must use current passages from their own edition.
- Arabic entry text and translations receive SHA-256 fingerprints over exact UTF-8 bytes.
- Every publication flag defaults to false.
- Translations remain separate records with translator, publisher, language, source, and attribution.
- The platform does not infer an author's methodology, merge opinions, or generate commentary.

## Canonical references

References are edition-scoped and deterministic. Ayah commentary uses edition, surah, and ayah coordinates; ranges retain both endpoints. Introductions, appendices, and editorial notes remain explicitly typed.

## Publication boundary

Unit 1 supplies the canonical schema and protected authoring foundation only. Controlled import, scholarly review, manifest reconciliation, and atomic publication are Unit 2 responsibilities. No tafsir corpus is bundled.
