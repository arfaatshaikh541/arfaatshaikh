# Translation governance and reader tools

Translations are interpretive works and remain separate from the canonical Arabic text. A translation edition can be published only through a staged import batch whose records point to current passages from the edition's approved Source Registry source.

## Publication gates

1. The translation source edition is approved for retrieval.
2. Every staged translation references a published canonical ayah.
3. Every staged translation references a current source passage from the same translation source edition.
4. Count and deterministic manifest SHA-256 reconcile.
5. A human reviewer approves the batch with rationale.
6. Source approval is checked again immediately before atomic publication.

No translation is silently treated as the Qur'an itself. The reader always presents Arabic as the primary text and labels the selected translation edition.

## Reader state

Authenticated reader preferences are account-scoped and contain translation choice, translation visibility, Arabic font scale, and theme. Bookmarks and reading progress remain private to the authenticated user. Copy-citation output includes the Arabic text, the explicitly selected translation when present, canonical reference, and stable deep link.
