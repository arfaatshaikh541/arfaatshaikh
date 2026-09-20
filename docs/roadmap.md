# Milestone Roadmap

## Working method (restated)

For every milestone: PLAN → OWNER APPROVAL → IMPLEMENT → TEST → HOSTILE AUDIT → FIX →
ACCEPTANCE REPORT → OWNER APPROVAL. No milestone begins before the prior one is
owner-approved. `docs/project-status.md` is updated at every step, not just at the end.

## Major limitations (carried forward from `architecture/00-overview.md`, restated as
planning constraints)

- No milestone claims autonomous judgment beyond current model capability; RED-tier
  actions remain owner-gated indefinitely absent a separately-approved narrow exception.
- No milestone claims immunity to sophisticated/state-level attack — only prevention,
  detection, containment, and recovery improve over time.
- Every milestone's "done" claim requires actually-executed tests and actually-reviewed
  security findings, per `docs/testing/README.md` — no fabricated completion.
- Cost, capability, and reliability of hosted model providers may change between
  milestones; the Model Router abstraction exists specifically so this doesn't force a
  redesign, but it may force a provider swap.

## Roadmap (indicative — each milestone's exact scope is finalized at its own PLAN step)

**Milestone 0 — Foundations (this milestone; see exact scope below).**
Owner identity, Control Plane skeleton, Action Broker + Policy Engine + Risk Engine +
Credential Broker (minimal), audit logging, kill switch, World Model schema (core
entities only), CI/CD with the required security gates, one working end-to-end GREEN
action (read-only), zero autonomous AMBER/RED capability.

**Milestone 1 — Executive Intelligence & Goal Engine.**
EI service, Goal Engine, Decision Memory, first specialist agent family (Research —
lowest risk), Morning Brief / Evening Report generation over real (if sparse) data.

**Milestone 2 — Memory depth & World Model completeness.**
Remaining nine memory systems fully implemented with provenance/versioning/
contradiction detection; Relationship and Business Memory populated from at least one
real connector (read-only).

**Milestone 3 — First write-capable connector, AMBER Level 3.**
One connector (e.g., CRM or email) with write capability, gated at Level 3
(approval-required) only; Approval Engine UI; first real owner-approved AMBER actions.

**Milestone 4 — Security Guardian & red-team gate.**
Security Guardian fully separated and operational; first scheduled fire drills; first
formal red-team exercise before any capability is proposed for Level 4.

**Milestone 5 — Build Engine (staging only).**
Software engineering workflow against a real (non-production) repository; production
deployment authority remains off.

**Milestone 6 — Marketing/Sales/CX engines, budgeted AMBER Level 4 pilots.**
Narrow, budget-capped Level 4 pilots (e.g., scheduled content publishing within
pre-approved templates) after track record from Milestones 3–4.

**Milestone 7 — Financial Control layer & Reconciliation.**
Read-only financial monitoring, budget envelopes, Reconciliation Assistant; no
write-capable payment action yet.

**Milestone 8+ — Expand connector surface, expand Level 4 scope per capability,
evaluate narrow RED exceptions (e.g., bounded auto-pay) only as explicit, separately
approved sub-projects.**

Each milestone after 0 is scoped in detail only once the prior milestone's acceptance
report is approved — planning further than one milestone ahead in exact detail would
itself be the kind of over-claiming this architecture is designed to avoid.

## Exact scope of Milestone 0

**Goal**: prove the safety-critical skeleton works end-to-end, with zero autonomous
business capability yet. Milestone 0 deliberately does *nothing* businesses-facing —
it is entirely plumbing and controls.

**In scope:**
1. Repository skeleton per `docs/architecture/12-data-and-api.md` (this documentation
   tree is the first deliverable, already committed).
2. Owner identity bootstrap: hardware-backed credential (passkey or hardware key)
   registration flow for the single owner.
3. Control Plane skeleton: minimal owner-authenticated API (mTLS + passkey session).
4. Policy Engine: OPA integration with a minimal policy set (kill switch, one example
   autonomy-level rule, one example budget rule) — owner-write-only, enforced.
5. Action Broker: the choke-point service per ADR 0001, wired to check kill-switch →
   policy → (stubbed risk/approval for now) → audit write, for one real action type.
6. Credential Broker: minimal Vault integration issuing a short-lived scoped token for
   exactly one connector.
7. One real connector, **read-only**: a low-risk read (e.g., read a calendar or read a
   GitHub repo's issues) — chosen specifically to be GREEN-tier and reversible-by-
   definition (reading changes nothing).
8. Audit log: hash-chained, append-only, with a basic query endpoint.
9. Kill switch: implemented and tested to actually block the one action type end-to-end.
10. World Model: schema for Owner, Goal, Policy/Permission, and Audit-adjacent entities
    only (not the full 30+ entity list yet) with the provenance/versioning envelope
    proven on these.
11. CI/CD: required checks wired (unit tests, secret scan, dependency scan, SAST) on the
    repository, branch protection enabled.
12. Test categories executed for this scope: unit, integration, permission, policy,
    credential, kill-switch-specific — categories 1–2, 5–6, 9 from
    `docs/testing/README.md`, run for real, results linked in the acceptance report.

**Explicitly out of scope for Milestone 0**: Executive Intelligence, Goal Engine
decomposition logic, any specialist agent, any write-capable connector, Security
Guardian (design documented here; implementation is Milestone 4), any AMBER/RED action,
any owner-facing UI beyond the minimal Control Plane auth flow, local inference,
disaster-recovery automation (design documented; drills start once there's real data
worth protecting).

**Acceptance criteria**: kill switch demonstrably blocks the one wired action end-to-end
in a test; the one read-only action executes successfully through the full Action
Broker chain with a complete audit trail; policy change requires owner auth and is
rejected from any other caller in a test; all CI gates pass on the actual repository.

**Milestone 0 does not require owner approval of this roadmap document to *start*
drafting — but implementation of Milestone 0 itself does require explicit owner
approval, per the non-negotiable working method above, and per the task instruction to
stop after architecture and Milestone 0 planning.**
