# Agent Architecture: Zero-Trust Fleet, Action Broker, Policy/Risk Engines, Credential Broker

## Core principle

**Agents are untrusted workloads.** An agent is an LLM invocation plus a task context —
it never holds a long-lived credential, never talks to an external system directly, and
never writes to the Policy Engine or Credential Vault. Every real-world effect goes
through one choke point:

```
Agent → Action Request → Action Broker → Policy Engine (allowed?)
                                       → Risk Engine (classify GREEN/AMBER/RED)
                                       → Approval Engine (if required)
                                       → Credential Broker (issue scoped short-lived cred)
                                       → External Tool / Connector
                                       → Audit Log (always, regardless of outcome)
```

This single choke point is also where the **kill switch** lives (see
`docs/policies/README.md#kill-switch`): if the switch is engaged, the Action Broker
rejects every request, unconditionally, before any of the other stages run. No agent,
including the EI, has an execution path that bypasses the Broker.

## Action Broker

- Validates the action against a registered schema (rejects hallucinated/unknown tools).
- Attaches full context: which goal authorized this, which agent requested it, what
  data it touches.
- Is the single audit-log writer for actions (agents cannot write their own audit
  entries — self-attestation is not evidence).
- Enforces idempotency keys so retries don't double-execute (double-send an email,
  double-charge a card).

## Policy Engine

Stores, as data (not prompts): permissions per agent-role/capability, autonomy level per
capability, budget envelopes, prohibited actions, connector scopes, and the kill-switch
state. Policy is **owner-authored and owner-approved**; the EI can *propose* a policy
change (e.g., "raise the discount autonomy level after 3 months of clean track record")
but cannot commit it — commits require owner authentication through the Control Plane.
Policy Engine decisions are deterministic (allow/deny/require-approval), not another LLM
judgment call, for anything above GREEN.

## Risk Engine

Classifies every action request into GREEN / AMBER / RED using a **rule-based
classifier** keyed on action type, resource sensitivity, and monetary value — augmented
by, but not solely dependent on, model judgment. Rules are explicit and inspectable
(e.g., "any outbound payment > 0 is at minimum AMBER; > owner-set threshold is RED";
"any write to production infrastructure is AMBER minimum"). The model can request a
stricter classification than the rule engine computed (fail-safe upgrade) but cannot
downgrade a rule-computed classification.

| Tier | Definition | Examples | Default gate |
|---|---|---|---|
| GREEN | Routine, reversible, low-impact | analytics, CRM updates, internal summaries, scheduled/approved content, standard support replies | Level 4 achievable |
| AMBER | Potential financial/reputational/operational impact | discounts, ad spend, refunds, production deploys, supplier commitments, sensitive comms | Level 3 initially, Level 4 only within explicit sub-limits after track record |
| RED | Material legal/financial/security/identity impact | large transfers, bank changes, binding contracts, hiring/firing, root security changes, credential authority changes, granting new AI permissions | Owner approval always, or a separately-designed narrow exception |

## Approval Engine

Manages the owner-facing approval queue for AMBER (when not pre-authorized at Level 4)
and RED actions. Batches non-urgent approvals into digest form to avoid approval
fatigue (see failure scenario #48); time-sensitive ones page/notify directly. Every
approval request includes: the action, the risk classification and why, the money/data
involved, and a one-line recommendation with confidence — not a bare "approve?".

## Credential Broker

The only component that can produce a credential usable against a real external system.

- Issues **short-lived, narrowly scoped, task-specific, revocable** tokens — never
  master secrets — to an agent only after the Action Broker has cleared policy/risk/
  approval for the specific action.
- Backed by a hardware-backed vault (KMS/HSM/OS secure enclave — see
  `docs/security/README.md#credential-vault`).
- Every issuance is logged with: which agent, which action, which scope, expiry.
- Automatic revocation on: task completion, timeout, Security Guardian freeze order, or
  kill-switch engagement.

## Agent lifecycle

- **Ephemeral by default**: spawned for a task, torn down after, no persistent
  standing process, no persistent standing credential. This bounds the blast radius of
  a compromised agent to the lifetime of one task.
- **Long-lived roles** (e.g., "Customer Support Agent" as a role handling many tickets)
  are implemented as a durable *workflow* consuming a queue, not as one agent process
  that stays "alive" and accumulates context indefinitely — each ticket is still a
  fresh, bounded invocation.
- **Concurrency caps** per capability family, enforced by the orchestrator independent
  of what the EI requests, to prevent unbounded agent sprawl (failure scenario #14).

## Security Guardian (independent oversight)

A monitoring system **outside** the EI/agent hierarchy, with its own credentials and its
own write path to a freeze command at the Action Broker.

Watches for: unusual tool-use patterns, unusual credential requests, privilege-
escalation attempts, unexpected data exports, anomalous spending velocity, unusual
communication patterns (e.g., sudden mass outreach), new/unapproved integrations,
suspicious network destinations, policy violations, memory-tampering patterns, and
audit-log tampering attempts.

- Can **freeze** any agent or capability immediately, pending owner review.
- **The Executive cannot disable, reconfigure, or reason its way around the Security
  Guardian** — this is a hard architectural separation (different service, different
  credential root, different deployment, no API from EI to Guardian's config), not a
  policy the EI is merely instructed to respect.
- Runs both deterministic rules (hard thresholds) and anomaly-detection models; a rule
  hit is instant-freeze, an anomaly-model flag is escalate-for-review (fewer false-
  positive freezes, still fast on clear violations).
- Subjected to scheduled synthetic "fire drills" (failure scenario #50) to verify it
  still actually catches things.

## Isolation / failure containment

Compromise of one agent must not compromise another agent, the EI, the vault, the owner
account, or the host. Achieved via: per-agent sandboxes (see
`docs/security/sandboxing.md`), per-task scoped credentials (no shared long-lived
secret an agent could steal and reuse elsewhere), network segmentation so an agent can
only reach the specific connectors its task needs, and the fact that no agent ever
holds vault master keys or Policy Engine write access regardless of role.
