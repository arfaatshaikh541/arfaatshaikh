# Controlled hadith import, review, and publication

Milestone 4 Unit 2 introduces a staging pipeline. It does not include a hadith corpus.

## Trust sequence

1. Register a collection against an approved, ingestion-ready, retrieval-eligible Source Registry edition.
2. Create a manifest with expected book, chapter, and narration counts plus a SHA-256 digest.
3. Stage each narration with exact matn, hierarchy metadata, and passage-level provenance.
4. Stage ordered isnād nodes. Positions must be contiguous when present; a manifest may require an isnād for every narration.
5. Resolve every duplicate candidate. Exact canonical-reference and exact matn-digest matches are never silently merged.
6. Validate counts, hierarchy consistency, manifest digest, current passages, and isnād structure.
7. Assign separate `hadith_text`, `isnad`, and `source_provenance` reviewers.
8. Require approval from all three domains.
9. Revalidate source eligibility and the approved manifest immediately before publication.
10. Publish books, chapters, narrations, and isnād nodes atomically.

## Duplicate policy

The automated detector raises deterministic candidates only. It never decides that two narrations are equivalent. A human must record `not_duplicate`, `confirmed_duplicate`, or `replace_existing` with rationale. Unit 2 blocks publication while any candidate remains pending. Replacement execution is intentionally not performed by this pipeline; a later correction/supersession workflow must preserve history.

## Review separation

A batch needs approvals in three domains. A rejection closes the batch. A changes-requested decision reopens it for correction and revalidation. Review events are append-only at the database layer.

## Content boundary

No hadith text, isnād, grading, translation, narrator biography, or sample religious data is bundled with this implementation.
