# Source provenance architecture

Provenance follows this chain:

`Source -> SourceEdition -> SourceAcquisition -> SourceIntegrityRecord -> SourceReview`

The edition is the citation and ingestion boundary. Acquisition records preserve where and under what terms material entered the platform. Integrity records are immutable checksums for stored objects. Reviews are append-only decisions with reviewer identity, domain, rationale and optional expiry.

The public API exposes only sources with an approved source status and at least one approved, retrieval-enabled edition.
