# ADR 0008: control-api ↔ policy-engine Uses HTTP/JSON, Not gRPC

## Status
Accepted (Milestone 3)

## Context
The approved architecture's system data-flow (§6) states "control-api requests policy
evaluation from policy-engine (**gRPC**)," and §14 (service-identity strategy) frames
service-to-service calls as using "mTLS in production; in local dev, plain gRPC over the
compose network, DEV ONLY, NO MTLS." Milestone 3 needs a real, working integration between
control-api (Go) and policy-engine (Python) now, since policy evaluation, simulation, and
conflict detection are all in its explicit scope.

## Decision
The integration is plain HTTP/JSON, not gRPC. `policy-engine` already exposes `/evaluate` and
`/conflicts` as FastAPI JSON endpoints (the natural shape for a Python service built on
FastAPI); control-api's new `internal/platform/policyengine` package is a small `net/http`
client calling them with typed Go request/response structs mirroring the Python Pydantic
schema.

Reading §6 and §14 together, gRPC-with-mTLS describes the *production transport security
posture* for inter-service calls generally (the same paragraph explicitly labels local-dev
plain gRPC as a stand-in for that posture, not a requirement in itself) -- it is not a
specific mandate that this one integration's wire format must be Protocol Buffers rather than
JSON. Given that, introducing gRPC now would mean standing up protobuf schema definitions and
codegen tooling across two languages (`packages/event-contracts`-style, but for RPC) for a
service with exactly two endpoints, before either endpoint's shape has been exercised against
a real caller -- premature machinery for the actual Milestone 3 scope, and out of step with
working rule #35 ("do not create unnecessary microservices" / avoid premature complexity more
broadly).

## Alternatives considered
- **Real gRPC now.** Rejected for Milestone 3: the added protobuf/codegen surface is
  significant relative to two endpoints, and nothing about policy evaluation's semantics
  requires gRPC specifically (no streaming, no need for HTTP/2 multiplexing at this call
  volume). Revisit if policy-engine's API surface grows enough, or if a later milestone's
  placement engine needs streaming evaluation results, to justify the investment.
- **Defer the integration entirely, keep control-api and policy-engine unconnected.**
  Rejected: Milestone 3's explicit scope is "the actual sovereignty policy evaluation... engine"
  (per `docs/project-status.md`'s own prior note) -- a policy module that never calls a real
  evaluator would violate working rule #6 (no pseudocode in accepted implementation work).

## Consequences
- control-api's policy-engine client (`internal/platform/policyengine`) must implement its own
  fail-closed behavior in Go code, since there is no gRPC deadline/status-code convention to
  lean on: any transport error, non-200 response, or response that fails to parse is treated
  identically to a `deny` decision with reason code `POLICY_ENGINE_UNAVAILABLE` -- see
  `internal/modules/policies` and its test coverage for this specific behavior.
- Local development has no mTLS between control-api and policy-engine, exactly as already
  documented for every other local-dev inter-service call in this codebase (labeled `DEV
  ONLY` in `docker-compose.yml` and `docs/operations/local-development.md`) -- this is not a
  new gap introduced by this decision, just the existing one applied to one more call.
- Migrating to gRPC later is a contained change: the Go client and the FastAPI endpoints are
  both already isolated behind small, single-purpose interfaces
  (`policyengine.Client`/`evaluate.py`/`conflicts.py`), so swapping transport does not require
  touching the policy module's business logic, dual-control workflow, or database schema.
