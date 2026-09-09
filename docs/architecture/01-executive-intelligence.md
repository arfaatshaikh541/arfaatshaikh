# Executive Intelligence (EI) & Single-Owner Identity

## Single-owner identity architecture

There is exactly one root principal: the Owner. The Owner's identity is anchored to
hardware-backed credentials (passkey/hardware security key + device certificate), not a
password. Every other identity in the system — every agent, every connector, every
contractor account — is a **derived, scoped principal** issued by the Credential Broker
and traceable back to an owner-approved grant.

```
Owner (root, hardware-backed keys)
  └─ issues policy & grants via Control Plane (mTLS, passkey-gated)
        └─ Policy Engine stores permissions, budgets, autonomy levels
              └─ Credential Broker issues short-lived scoped credentials to agents
                    └─ Agents (zero standing privilege)
```

No AI component can create, elevate, or extend a principal. Only the Control Plane,
gated by owner authentication, can. This is enforced at the service/API boundary
(the Policy Engine's write endpoints reject any caller that isn't the owner-authenticated
Control Plane), not by instructing the model to behave.

## Executive Intelligence — responsibilities

The EI is a **role**, implemented as an orchestration service that invokes an LLM with
curated context per turn/step — not a single ever-growing chat session. Responsibilities:

- Interpret owner intent into goals (via the Goal Engine).
- Maintain the active goal set and priorities.
- Decompose goals into delegable tasks for specialist agents.
- Resolve conflicts (competing priorities, budget contention) using owner-defined
  priority rules; escalate to owner when rules don't resolve it.
- Allocate budget *within* limits the owner has already authorized — it cannot create
  new budget authority.
- Monitor agent progress via the workflow engine's status, not by "trusting" agent
  self-reports.
- Evaluate results against the goal's declared success metric.
- Detect failure patterns (via Failure Memory) and adjust strategy.
- Request owner approval for anything the Risk Engine classifies AMBER without
  standing Level-4 authorization, or RED always.

## What the EI explicitly cannot do

- Cannot call the Credential Broker directly for raw secrets — it requests actions
  through the Action Broker like any other agent (see `04-agent-architecture.md`).
- Cannot modify Policy Engine records (permissions, autonomy levels, budgets, kill-switch
  state, audit configuration).
- Cannot disable or reconfigure the Security Guardian.
- Cannot spawn unbounded subordinate agents — subject to the same concurrency caps as
  any orchestrator role.

## Why a separate role from "just a bigger prompt"

A single giant always-on conversation degrades: context grows stale, past mistakes get
silently re-reinforced, and there's no clean boundary for interruption, rollback, or
per-task audit. The EI is instead a **stateless-per-invocation service** that reads
current state from the World Model and Goal Engine, is invoked to make one planning/
delegation decision, writes its decision and reasoning back as Decision Memory, and
exits. Continuity comes from the durable state store, not from an open model context
window. This is what makes "leave it running, come back, ask what happened" actually
reliable — the state is real, not conversational residue.

## Explainability requirement

Every EI decision that leads to a delegated task, budget allocation, or plan change is
recorded in Decision Memory with: the goal it serves, alternatives considered (if any),
the reasoning summary, and confidence. "Why did you make that decision?" is answered by
querying this record, not by re-prompting the model to rationalize after the fact.
