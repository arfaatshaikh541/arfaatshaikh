# ADR 0004: Policy Engine is native Python + SQL, not OPA/Rego, for now

## Status
Implemented (`core/src/aura_core/governance/policy_engine.py`)

## Context
`docs/architecture/11-technology-stack.md` recommended Open Policy Agent
(OPA/Rego) for policy-as-code. When actually building the Policy Engine,
introducing the `opa` binary as an external process dependency, managing
its lifecycle, and serializing policy state to Rego added real complexity
without a corresponding benefit at this stage: there is exactly one
policy consumer (the Action Broker), the policy shapes needed (autonomy
levels, prohibited actions, budgets, a kill switch) are simple key-value
and threshold checks, and the priority was getting a real, tested,
deterministic engine running today rather than a closer match to the
original tech-stack recommendation.

## Decision
Implement the Policy Engine as native Python logic over a SQL-backed
store (SQLite via SQLAlchemy, same engine as the memory store). All
decision logic remains deterministic and data-driven — `evaluate()`
contains no model calls and no free-form logic beyond explicit,
inspectable rules — which was the actual safety-relevant requirement, not
the specific rule-engine technology.

## Consequences
- **Positive**: real, tested, running today; zero new operational
  dependency (no separate `opa` process to deploy, monitor, or secure);
  simpler to review for a security-relevant component with one clear
  consumer.
- **Negative**: policy rules are Python method calls, not Rego source
  files — less directly diffable/reviewable as standalone "policy
  documents" than a Rego-based approach would be, and the
  `_LEVEL_BASE_DECISION` table lives in code rather than externally
  editable data. If policy authoring needs to be delegated to someone who
  isn't editing the codebase (e.g., a future non-technical policy admin
  UI), this will need revisiting.

## Migration path
The `PolicyEngine.evaluate()` interface (`ActionRequest`, `RiskTier` in;
`PolicyEvaluation` out) is the only contract the `ActionBroker` depends
on. Swapping the backend to OPA later means reimplementing that one
method against an `opa eval` call or embedded OPA server, with autonomy
levels/prohibited actions/budgets expressed as Rego data — no change
required to the Action Broker, the handlers, or any calling code. This is
the same "swap the implementation behind a narrow interface" pattern
already used for model providers (`ModelRouter`) and memory (`MemoryStore`).
