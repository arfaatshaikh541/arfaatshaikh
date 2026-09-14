# Governed Retrieval Foundation

Milestone 6 Unit 1 introduces a projection layer between the canonical Islamic corpora and any future answer generator.

## Non-negotiable gates

A document is projected only when the canonical record is published, its Source Registry edition is approved and ingestion-ready, retrieval is explicitly allowed, the source passage is current, attribution is present, and redistribution is permitted. Failure of any gate rejects the projection.

## Exactness

Chunks preserve exact source text and character offsets. Each document and chunk has a SHA-256 checksum. Chunking never paraphrases, translates, repairs, or generates religious content.

## Revocation

Query-time retrieval must require both document and chunk to be active and must recheck source approval, current passage state, and retrieval approval. Projection snapshots are not trusted after source revocation.

## Evidence contract

Every evidence item carries corpus type, canonical reference, source edition, source passage, exact text, checksum, attribution, and licence. Future answer claims must link to these immutable identifiers.

## Injection boundary

Projected text is data, never executable instruction. Later prompt construction must wrap evidence as untrusted quoted material and prohibit source text from changing system or safety policy.
