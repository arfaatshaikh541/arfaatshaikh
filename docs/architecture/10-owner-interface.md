# Owner Interface

## Design goal

Extraordinarily simple on the surface, backed by the full architecture underneath.
The owner interacts with the Executive Intelligence through natural language; the
Executive queries the underlying systems (World Model, Goal Engine, Action Broker's
audit log, Approval Engine) to answer, rather than answering from unstructured
"memory."

## Home surface (information architecture, not final UI)

- **AURA** — the conversational entry point (text now; voice as a later milestone).
- **Business Health** — top-line status per business/brand, sourced from Business
  Memory + Reconciliation Assistant, never from agent self-report alone.
- **Goals** — active goals, progress vs. success metric, confidence, stop conditions.
- **What AURA Is Doing** — live view of in-flight workflows/agents (Live Status report,
  see `docs/operations/README.md`).
- **Results** — completed work with evidence links.
- **Money** — spend, revenue, budgets, pending financial approvals.
- **Communications** — outbound/inbound activity summary per channel.
- **Projects** — Build Engine and Operations project state.
- **Opportunities** — the Opportunity Engine's current queue.
- **Risks** — open Risk records requiring attention.
- **Approvals** — the Approval Engine's pending queue (AMBER without standing
  authorization, and all RED).
- **Ask AURA** — freeform query surface over the whole World Model + audit trail.

## Core owner commands (illustrative, mapped to backing systems)

| Owner says | Backing operation |
|---|---|
| "Run the business." | Activates/resumes standing goals at their configured autonomy levels; no blanket permission escalation |
| "Grow revenue without exceeding AED 5,000/mo marketing spend." | Creates/updates a Goal with an explicit budget constraint |
| "What happened?" / "What happened while I was away?" | Queries Episodic Memory + Decision Memory + audit log over the elapsed period, renders Evening/interim report |
| "What requires me?" | Queries Approval Engine's pending queue + Commitment Memory deadlines + Risk records above threshold |
| "Why did you make that decision?" | Queries Decision Memory for the specific decision + linked evidence |
| "Show me the evidence." | Renders the audit trail / source documents backing a specific claim |
| "Undo that." | Triggers the rollback path for the specific action (see below) |
| "Stop all autonomous activity." | Engages the kill switch at the Action Broker (`docs/policies/README.md#kill-switch`) |

## Rollback ("undo that")

Not every action is technically reversible (a sent email cannot be unsent), so "undo"
resolves to the best available response per action type, defined at design time per
capability, not improvised at runtime:

- **Fully reversible** (a scheduled-but-not-yet-published post, a draft, a pending
  approval) — cancelled outright.
- **Compensable** (a CRM record change, a code change) — a compensating action is
  generated (revert commit, restore previous record version from World Model
  versioning).
- **Irreversible** (a sent communication, an executed payment) — "undo" is not offered
  as a false promise; instead AURA proposes the best available mitigation (a follow-up
  correction, a refund, a public correction) and flags it clearly as mitigation, not
  undo.

## Explainability is a query, not a re-generation

"Why did you make that decision" and "show me the evidence" must return the actual
recorded reasoning and evidence from Decision Memory / audit log — not a freshly
generated, possibly-confabulated justification. This is a hard product requirement, not
a nicety: it's what makes the owner's trust in the system verifiable rather than
faith-based.

## Multi-surface support

Desktop and mobile clients are thin views over the same Control Plane APIs; voice is a
later milestone, built as a speech-to-text front end onto the same text-command
surface (not a separate parallel command interpreter, to avoid divergent behavior
between voice and text).

## Security-over-cinematic-UI

Every interface surface authenticates the owner via hardware-backed credentials before
showing anything sensitive (financial data, credentials state, policy config); no
interface convenience (e.g., "remember me" tokens with broad scope) is allowed to
weaken the owner-authentication bar used for RED approvals specifically.
