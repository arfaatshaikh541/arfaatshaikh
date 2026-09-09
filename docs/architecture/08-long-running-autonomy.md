# Long-Running Autonomy Architecture

## Core principle

AURA operates beyond a single chat session by being built as **durable, event-driven
workflows**, not as one endless LLM conversation. An LLM invocation is a bounded,
stateless step in a workflow; continuity lives in a durable state store the workflow
engine manages, not in an ever-growing context window.

```
Owner intent → Goal (World Model) → Workflow instance (durable engine)
   → step: EI plans → step: delegate to specialist workflow → step: agent invocation
   → step: verify → step: report → [checkpoint] → next scheduled/triggered step
```

## Required primitives

- **Durable workflows** — orchestration state (which step, what inputs/outputs,
  what's pending) survives process restarts, deploys, and crashes. (Technology choice
  and rationale in `11-technology-stack.md`.)
- **Event-driven execution** — workflows advance on events (a webhook fires, a schedule
  triggers, an approval arrives, a connector returns data) rather than polling in a
  tight loop.
- **Scheduled tasks** — recurring workflows (daily brief generation, weekly report,
  periodic goal review) driven by a scheduler, with timezone handling normalized to UTC
  internally (failure scenario #38).
- **Goal queues** — goals and their derived tasks live in a queue/backlog the EI
  processes by priority, not an implicit ordering buried in conversation.
- **Retries** — bounded, with backoff, and explicit max-attempt limits (failure scenario
  #11).
- **Checkpoints** — a task's progress is persisted at defined points so a crash resumes
  from the last checkpoint, not from zero (failure scenario #13).
- **Leases** — a worker/agent claims a task with a time-bound lease; if it dies without
  releasing/completing, the lease expires and the task becomes claimable again — prevents
  a crashed agent from silently stalling a task forever.
- **Idempotency** — every external-effect action carries an idempotency key so a retry
  after a partial failure cannot double-send an email or double-charge a payment.
- **Resumability** — a paused goal/workflow (owner-paused, or auto-paused on a stop
  condition) can resume from exactly where it left off.
- **Cancellation** — the owner's "stop that" / kill-switch commands propagate to
  in-flight workflow steps, not just to new task creation.
- **Timeouts** — every step has a maximum duration; a hung external call or model
  invocation doesn't block a workflow indefinitely.
- **Dead-letter handling** — tasks that exhaust retries land in a dead-letter queue with
  full context, visible to the owner/Chief of Staff, not silently dropped (failure
  scenario #19).
- **Human escalation** — a first-class workflow outcome, not an exception path bolted on
  — "escalate to owner" is as normal a terminal state as "completed."
- **Agent health monitoring** — heartbeats from active agent workers, independent of the
  agents' self-reported status, feeding both the orchestrator (for lease expiry) and the
  Security Guardian (for anomaly detection) (failure scenario #20).

## Re-grounding against drift

Every workflow step that re-enters EI planning re-reads current goal/policy/memory
state from the World Model rather than carrying forward an assumed context from many
steps ago. This bounds the "drift over long horizons" failure mode named in the
feasibility assessment: a workflow can span days or weeks in wall-clock time, but each
individual reasoning step is grounded in current truth, not an accumulating, possibly
stale, conversational context.

## Long-lived "roles" vs. long-lived processes

A role like "Customer Support Agent" is implemented as a durable *consumer* of a ticket
queue — each ticket triggers a fresh, bounded agent invocation with task-scoped context
— not a single long-lived process accumulating unbounded conversational history across
thousands of tickets. This keeps per-invocation context small, auditable, and immune to
slow context poisoning over time.
