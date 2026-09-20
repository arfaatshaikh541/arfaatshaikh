# Repository Architecture, Data Model, API Architecture

## Repository architecture

Monorepo for Milestone 0–2 (single owner, small surface area, and cross-cutting policy
concerns benefit from atomic commits across services). Split into services only if/when
independent deploy cadence or team boundaries (e.g., contractors working on isolated
pieces) demand it.

```
/aura
  /services
    /executive        # Executive Intelligence orchestration
    /world-model       # entities, memory systems, query API
    /goal-engine
    /action-broker
    /policy-engine      # OPA policies + Policy Engine service
    /risk-engine
    /approval-engine
    /credential-broker
    /security-guardian  # deliberately separate deploy/trust boundary
    /model-router
    /privacy-gateway
    /connectors/<name>   # one package per connector
    /agents/<family>/<role>   # agent role definitions & prompts, versioned
  /workflows            # Temporal workflow definitions
  /web                  # owner interface (control plane UI)
  /infra                # IaC (Terraform/Pulumi), network policy, sandbox configs
  /docs                 # this documentation tree — authoritative project memory
  /tests
    /unit /integration /e2e /security /chaos
```

Branch protection on `main`; no direct pushes; CI required (tests, SAST, secret scan,
dependency scan) before merge, per `docs/security/README.md#supply-chain-security`.

## Data model (high level)

The World Model's relational schema implements the entity list from
`architecture/02-world-model-memory.md` as first-class tables with:

- a common **provenance/versioning envelope** (source, created_at, valid_from/until,
  confidence, sensitivity, owner, evidence refs, supersedes/superseded_by, retention
  policy) applied consistently via a shared base schema/mixin — not reimplemented
  per-entity;
- **typed relationship edges** (a single `relationships` table: subject_id, predicate,
  object_id, provenance envelope) so new relationship types don't require schema
  migrations;
- **row-level security** scoping every read/write to the owner's context and the calling
  service's authorized entity types.

Money-bearing entities (Invoice, Expense, Revenue, Contract) additionally carry a
reconciliation status and a link to the source-of-truth external record (bank/
accounting system), never treated as authoritative on their own (see
`06-financial-control.md`).

## API architecture

- **Internal service-to-service**: gRPC over mTLS between core services (low latency,
  strong typing, matches the "each service has its own workload identity" requirement).
- **Action Broker's action-request API**: a single, strongly-typed endpoint schema per
  registered action type (see connector manifests, `docs/connectors/README.md`) —
  agents cannot call arbitrary methods, only registered actions with validated
  arguments.
- **Owner-facing Control Plane API**: REST/GraphQL over the private network (via the
  Secure Access Layer), authenticated via mTLS + passkey/hardware-key-backed session,
  never exposed on the public internet.
- **No public API surface** by default. If a specific controlled integration later
  requires an inbound public endpoint (e.g., a webhook from a connector provider), it is
  narrowly scoped, rate-limited, signature-verified, and treated as an EXTERNAL DATA
  ingestion point subject to the same prompt-injection/data-provenance discipline as any
  other external content — never as a path with direct action authority.
- **Idempotency keys** required on every mutating API call that has an external-world
  effect, matching the long-running-autonomy requirement.
- **Versioning**: all internal and control-plane APIs are explicitly versioned; breaking
  changes require a migration plan, not silent contract changes (an agent depending on
  an API contract that silently changed is its own failure mode).
