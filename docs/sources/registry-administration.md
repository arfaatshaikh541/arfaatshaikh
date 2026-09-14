# Source registry administration

Registry administration is deliberately separated into registration, legal review, integrity verification, scholarly review, approval-policy enforcement, and retrieval eligibility.

## Reviewer queue

Authenticated reviewers see only their own open assignments. Queue ordering prioritises due dates and then assignment age. Review submission remains bound to the assigned reviewer.

## Provenance inspection

Administrators can inspect an editorial claim together with every immutable source passage span linked to it. The service revalidates each stored character span before rendering. A mismatch fails closed as an integrity error.

## Policy enforcement

Retrieval eligibility requires an active approval policy for the source type. The active policy controls the minimum number of distinct approving reviewers and the complete set of required review domains. A registered source type without an active policy cannot become retrieval eligible.

## Audit exports

Exports contain source lifecycle events and are available as deterministic JSON or CSV. Every generated payload receives a SHA-256 digest, and the export request record is append-only. Export records contain metadata and integrity evidence, not a mutable copy of source text.
