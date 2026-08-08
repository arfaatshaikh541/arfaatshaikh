# ADR 0002: Long-running autonomy is implemented as durable workflows, not a persistent chat session

## Status
Proposed

## Context
AURA must operate for hours to weeks unsupervised. A single, ever-growing LLM
conversation degrades (stale context, silent drift, no clean checkpoint/resume/cancel
semantics, unbounded cost growth) and cannot survive process restarts cleanly.

## Decision
Use a durable workflow engine (Temporal — see `docs/architecture/11-technology-stack.md`)
as the backbone of all multi-step or long-horizon work. Each LLM invocation is a bounded,
stateless activity within a workflow; state and continuity live in the durable store, and
each planning step re-reads current World Model/Goal/Policy state rather than relying on
accumulated conversational context.

## Consequences
- **Positive**: crash-safe, resumable, cancellable, auditable per-step; re-grounding at
  each step bounds goal drift; cost is bounded per step rather than growing with
  conversation length.
- **Negative**: more engineering complexity than "just keep a chat open"; requires
  discipline to keep each step's context assembly correct and complete (a step that
  forgets to re-fetch relevant context can behave worse than a long-context chat would
  on that one step) — mitigated by the World Model being the source of truth, not the
  step's own memory.

## Alternatives considered
- Single long-running agent conversation per goal (rejected — the specific failure
  modes above are exactly what the "long-running autonomy" requirement warns against).
- Simple cron-triggered stateless scripts without a workflow engine (rejected — lacks
  retries/leases/checkpoints/human-in-the-loop waits needed for real multi-step business
  processes).
