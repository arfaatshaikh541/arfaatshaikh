# Policy Architecture: Autonomy Levels, Action Risk, Kill Switch

## Autonomy levels (per capability, not global)

Every capability (e.g., "publish social content for Brand X," "send refund," "deploy to
production") has its **own** autonomy level setting in the Policy Engine. There is no
single global autonomy dial — this is deliberate, because "how autonomous should AURA
be" is not one number for a system spanning engineering, marketing, sales, and finance.

| Level | Meaning |
|---|---|
| 0 | Observe only — AURA monitors and records, takes no action |
| 1 | Recommend — AURA surfaces a recommendation, owner decides and executes manually |
| 2 | Prepare — AURA prepares the action (draft email, draft deploy) but does not execute |
| 3 | Execute after owner approval — AURA prepares and executes, gated on explicit per-instance approval |
| 4 | Autonomous within explicit policy and limits — AURA executes without per-instance approval, within pre-set budget/scope/rate limits, fully audited |
| 5 | Executive autonomy inside a defined business domain — the broadest grant, reserved for narrow, extensively track-recorded domains the owner explicitly designates |

**No capability starts at, or automatically advances to, Level 5.** Advancement is an
explicit owner action, informed by (but not automatically triggered by) accumulated
track record — the EI can *propose* an advancement with evidence, never grant it.

## Action Risk Engine (GREEN/AMBER/RED)

Specified in `docs/architecture/04-agent-architecture.md#risk-engine`. The key policy
point: risk tier and autonomy level are **two different axes** — a GREEN action can
still require approval if its capability is only set to Level 2, and conversely a
capability set to "Level 4 within limits" only actually executes autonomously for
instances that are also within those explicit limits; an instance that exceeds the
configured limit is automatically treated as requiring approval regardless of the
capability's general level.

## RED-tier default: owner approval, always

RED actions (large financial transfers, bank changes, binding contracts, hiring/firing,
root security changes, credential-authority changes, granting new AI permissions,
regulated decisions, identity verification) require explicit owner approval by default,
permanently, unless a **separately designed, narrowly scoped, legally reviewed
mechanism** is built and explicitly approved for one specific narrow case (e.g., a
tightly bounded recurring-vendor auto-pay, as noted in `06-financial-control.md`). This
is a standing architectural rule, not a setting the EI or an agent can toggle.

## Owner sovereignty controls

The owner must have, at all times, functioning:

- **Global pause** — halts all new action execution; in-flight actions either complete
  their current atomic step or are cancelled per their defined cancellation semantics
  (`08-long-running-autonomy.md`), never left in an undefined half-state.
- **Global kill switch** — see below.
- **Agent revocation** — terminate a specific agent/workflow instantly.
- **Credential revocation** — instantly invalidate any issued credential via the
  Credential Broker.
- **Session revocation** — terminate any owner or contractor session.
- **Action history** — full queryable audit trail.
- **Reasoning/evidence inspection** — Decision Memory queries.
- **Memory correction** — supersede any memory record with evidence.
- **Rollback** — per the action-type-specific semantics in
  `architecture/10-owner-interface.md#rollback`.
- **Spending controls** — adjust budget envelopes/limits in real time.
- **Communication controls** — disable specific channels/connectors instantly.
- **Integration controls** — revoke/reconfigure any connector.

All of the above are Control Plane operations, authenticated by the owner's
hardware-backed credentials, and **none of them can be initiated by any AI component**
— they are owner-only write paths, enforced at the API boundary.

## Kill-switch design

The kill switch is a single boolean flag in the Policy Engine's store, but its
enforcement point is deliberately narrow and singular: **the Action Broker checks it
before every action, unconditionally, as the very first step, before policy/risk/
approval evaluation even begins.** This is the reason the entire agent fleet is required
to route every real-world effect through the Action Broker (`04-agent-architecture.md`)
— it's not just an audit convenience, it's what makes the kill switch actually
comprehensive rather than "off in most places."

- Engaging the switch is instantaneous (no workflow needs to "notice" it — the next
  action attempt by any agent is rejected immediately).
- In-flight, already-dispatched external calls (e.g., an HTTP request already sent to a
  connector) cannot be un-sent, but no *new* action dispatch occurs after engagement,
  and the workflow engine marks all in-flight workflows paused pending owner review.
- Disengaging requires the same owner-authenticated Control Plane path as engaging —
  no auto-resume.
- The kill switch's own state changes are themselves logged to the tamper-evident audit
  trail with full attribution.

## AURA's self-improvement boundary (restated as policy)

AURA may improve strategies, prompts, workflows, and routing within defined boundaries
(subject to the evaluation gate in Procedural Memory, `02-world-model-memory.md`). AURA
may **not**, under any reasoning path: increase its own permissions, disable safety
controls, remove audit systems, change owner identity, modify root policies, expand
spending authority, create hidden persistence, copy itself to unauthorized systems,
bypass network controls, or conceal actions from the owner. These are enforced as
structural absences of capability (no API exists for the EI to do these things), not as
instructions the model is asked to honor — per the repeated theme of this architecture:
**safety-critical constraints are enforced by what the system cannot reach, not by what
it's told not to do.**
