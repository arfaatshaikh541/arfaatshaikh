# Personal World Model & Memory Architecture

## Personal World Model

A structured, queryable graph + relational representation of the owner's business
world — not a document pile, not chat history. Entity types (each a first-class schema,
not a blob): Owner, Business, Brand, Product, Service, Customer, Prospect, Supplier,
Partner, Employee, Contractor, Project, Repository, Website, Domain, Infrastructure
asset, Account, Campaign, Content item, Communication, Meeting, Document, Contract,
Invoice, Expense, Revenue event, Asset, Commitment, Deadline, Goal, Policy, Permission,
Decision, Experiment, Risk, Opportunity, Incident, Knowledge item, Relationship (edge
type connecting any two entities, typed and directional).

Implementation shape: relational store for structured entities and transactional
integrity (money, contracts, permissions) + graph store for relationship traversal
(who-knows-whom, which campaign touched which customer, which incident affected which
project) + vector store for semantic retrieval over unstructured content (documents,
communications, knowledge). These three are kept **consistent via the same write path**
(a single World Model service), not as independently-updated silos that can drift apart.

## Why not chat history as memory

Chat history is unstructured, unversioned, has no provenance model, can't be queried
temporally ("what did we know on March 3rd"), can't express confidence or supersession,
and grows unbounded. It is used only as an ephemeral working-memory input, never as the
system of record.

## Every memory record carries

- `source` — which agent/connector/document produced it
- `created_at` / `valid_from` / `valid_until` — temporal bounds (a fact can be true only
  for a period)
- `confidence` — 0–1, degraded for inferred vs. directly-observed facts
- `sensitivity` — public / internal / confidential / restricted (drives Privacy Gateway
  routing)
- `owner` — which business/brand context it belongs to (single human owner, multiple
  business contexts)
- `evidence` — pointer(s) to source artifact (email id, document id, transaction id)
- `supersedes` / `superseded_by` — correction chain, append-only
- `relationships` — typed edges to other entities
- `retention_policy` — how long it's kept, and under what legal/owner basis

## The ten memory systems

1. **Working Memory** — per-task scratch context assembled fresh for each agent
   invocation; discarded after the task, never a durable store.
2. **Episodic Memory** — timestamped event log: what happened and when (a call was
   made, a deploy occurred, a customer complained). Append-only, queryable by time range.
3. **Semantic Memory** — durable facts about the business world (current pricing,
   product features, org structure). Supports contradiction detection: a new fact that
   conflicts with an existing high-confidence fact is flagged, not silently overwritten.
4. **Procedural Memory** — how recurring tasks should be performed ("how we onboard a
   customer," "how we triage a support ticket"). Changes to procedures go through the
   evaluation gate described in `01-executive-intelligence.md`'s learning loop before
   becoming default.
5. **Relationship Memory** — customers, suppliers, partners, and full communication
   history per relationship, used for CRM-grade context (never fabricate relationship
   history — this is a hard rule enforced at generation time via evidence-required
   prompting and post-hoc citation checks).
6. **Decision Memory** — significant decisions with reasoning, alternatives, and
   confidence, at both EI and specialist-agent level. This is the backbone of "why did
   you do that."
7. **Failure Memory** — mistakes, near-misses, and their root cause, feeding the
   self-improvement loop and the Security Guardian's pattern detection.
8. **Creative Memory** — brand voice, vocabulary, visual identity references, past
   concepts (including what underperformed, not just wins) — used to avoid repetitive,
   generic AI-sounding output.
9. **Business Memory** — metrics, pricing history, strategy documents, operational
   knowledge, product roadmap.
10. **Commitment Memory** — promises made (to customers, partners, the owner),
    deadlines, and fulfillment status; the source for "what requires me" and "pending
    commitments" in reporting.

## Memory operations required by every store

- **Provenance** — never optional, enforced at the write API.
- **Versioning** — every update creates a new version; nothing is destructively
  overwritten except under explicit retention/deletion policy.
- **Correction** — an authorized correction (owner or a verifying agent with evidence)
  supersedes rather than deletes, preserving the audit trail of "we used to believe X."
- **Deletion** — supported for legal/privacy requirements (e.g., a customer's
  data-deletion request), but deletion itself is logged in the audit trail (the fact
  that something was deleted, when, and under what basis is retained even though the
  content is not).
- **Encryption** — per sensitivity class, per `docs/privacy/README.md`.
- **Semantic + structured + temporal query** — "what do we know about Customer X"
  (semantic), "list open invoices over 30 days" (structured), "what was our pricing on
  Jan 1" (temporal).
- **Contradiction detection** — a background process that flags new writes conflicting
  with existing high-confidence semantic facts for review rather than silent acceptance.

## Retrieval discipline against hallucination

Any agent output that states a fact must be able to trace it to a memory record with
evidence, or explicitly mark it as an inference/estimate with stated confidence. This is
enforced by a post-generation citation-check step for anything entering an executive
report or a customer-facing/financial artifact — not left to the model's self-restraint
alone.
