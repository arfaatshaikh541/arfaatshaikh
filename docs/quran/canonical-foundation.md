# Qur'an canonical foundation

Milestone 3 Unit 1 introduces schema and API boundaries only. It does not import, reconstruct, or publish Qur'anic text.

## Trust invariants

- Arabic text editions must reference a Source Registry edition already approved for retrieval.
- Every ayah references an immutable source passage belonging to the same approved source edition.
- Arabic text is validated without normalising away diacritics or asking AI to repair it.
- A SHA-256 digest is stored over the exact UTF-8 text.
- New text editions, ayat, and translations are unpublished by default.
- Translations remain distinct attributed works and are never represented as the Qur'an itself.
