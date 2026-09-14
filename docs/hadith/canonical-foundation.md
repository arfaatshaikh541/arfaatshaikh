# Canonical Hadith Foundation

Milestone 4 Unit 1 establishes a provenance-first model for hadith collections, books, chapters, narrations, narrator identities, isnad nodes, and attributed grading opinions.

## Trust rules

- Every collection is linked to one approved, ingestion-ready, retrieval-eligible Source Registry edition.
- Every book, chapter, narration, isnad node, and grading points to a current source passage from that same edition.
- Arabic matn is stored exactly and fingerprinted with SHA-256. The service never repairs or paraphrases it.
- Gradings are independent attributed opinions. The data model never collapses disagreement into a synthetic consensus.
- All public flags default to false. Unit 1 provides no publication workflow and no corpus data.

## Canonical references

Narrations use `<collection-key>:<collection-number>`. These references are stable inside the registered edition and must not be inferred across editions.
