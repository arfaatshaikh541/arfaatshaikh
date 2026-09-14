# Controlled Qur'an Import Pipeline

Qur'anic text is never inserted directly into the public canonical tables from an uploaded file or language model.

## Lifecycle

1. Register an approved Source Registry edition.
2. Register a Qur'an text edition linked to that source edition.
3. Create an import batch with an immutable manifest digest and expected counts.
4. Stage each ayah with an immutable source-passage reference.
5. Validate canonical references, per-surah counts, total count, provenance, and the deterministic manifest checksum.
6. Record a human review decision.
7. Publish in one database transaction only while the source remains retrieval eligible.

## Deterministic manifest

Rows are ordered by surah and ayah. Each line contains:

`canonical_reference<TAB>ayah_sha256<TAB>source_passage_id`

The SHA-256 digest of those UTF-8 lines must equal the registered manifest digest.

## Fail-closed rules

Publication is blocked when any of these conditions fail:

- source edition is no longer approved, ready, and retrieval eligible;
- validation did not complete successfully;
- review is absent or non-approving;
- staged ayah count differs from the manifest;
- canonical edition already contains ayahs;
- provenance passage is missing, stale, or belongs to another edition.

No AI correction, normalization, or reconstruction of Qur'anic Arabic is allowed.
