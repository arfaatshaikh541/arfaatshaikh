# Source lifecycle, integrity, review, and passages

Milestone 2 Unit 2 turns the registry from passive metadata into a controlled trust workflow.

## Fail-closed retrieval

`approved_for_retrieval` is not accepted from any request. The platform computes it only when every gate passes:

1. the source authority is approved;
2. the edition licence has completed legal review;
3. redistribution is permitted;
4. at least one acquisition record exists;
5. at least one object has been cryptographically verified;
6. ingestion is in the `ready` state;
7. an assigned reviewer has submitted an approved review;
8. public attribution is present.

Any failed gate sets retrieval eligibility to false. Authority, ingestion, review, passage, or licensing changes do not silently preserve a prior approval.

## Integrity verification

The API streams the registered MinIO/S3 object and calculates SHA-256 or SHA-512 server-side. Clients cannot submit a digest and declare it verified. The immutable integrity record stores the object key, algorithm, digest, byte size, and verification timestamp.

## Review assignments

A platform administrator may assign an active, email-verified user to a review domain. Only the assigned reviewer can submit the decision. Assignments and decisions remain separate records so responsibility and outcome are independently auditable.

## Source passages

Passages are edition-specific, language-specific, versioned evidence units. Creating a changed passage creates a new version and retires the previous current pointer. Database protection prevents mutation of the content, checksum, citation locator, language, passage key, creator, or version after insertion.

No passage becomes publicly retrievable unless its parent edition passes every retrieval gate.

## Lifecycle evidence

Integrity checks, ingestion transitions, and retrieval evaluations emit append-only lifecycle events with actor, previous state, next state, rationale, and timestamp.
