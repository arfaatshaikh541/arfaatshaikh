# Goal Engine

## Goal object schema

Every goal, from "reach AED 100,000 MRR" to "fix the checkout bug," is a structured
record, not a freeform instruction:

```
Goal {
  id, owner, business_context
  statement            # natural-language intent, for human readability
  priority             # owner-set or inherited/derived
  deadline             # optional
  success_metric       # measurable, explicit
  constraints          # e.g., "no layoffs," "AED 5,000/mo marketing cap"
  budget               # money + time/compute envelope
  dependencies         # other goals/resources this depends on
  allowed_actions       # explicit capability scope
  prohibited_actions   # explicit exclusions, always checked first
  progress             # current measured state vs. success_metric
  confidence           # EI's confidence in current plan reaching the metric
  review_interval      # how often EI re-evaluates this goal
  stop_conditions      # e.g., "pause if CAC exceeds X," "stop if 3 consecutive failures"
  status               # draft / active / paused / completed / abandoned
}
```

A goal cannot become `active` without success_metric, budget, and at least one stop
condition populated — enforced by schema validation, not left to good intentions.

## Decomposition example (illustrative, not prescriptive)

```
Goal: Reach AED 100,000 MRR
 → derive current MRR, gap, and realistic timeframe from Business Memory
 → derive required net-new customers (using current price point + churn rate)
 → derive required qualified pipeline (using current close rate)
 → derive required lead volume (using current qualification rate)
 → derive marketing/content/outreach requirements to hit lead volume within budget cap
 → derive product/capacity requirements if current product can't support the target
 → create child goals per engine (Marketing, Sales, Product) with their own metrics,
   each inheriting a narrowed budget and constraint set from the parent
 → schedule review_interval (e.g., weekly) to re-derive against actuals
```

The decomposition itself is logged as Decision Memory — the owner can inspect *why*
AURA chose this path (e.g., why it prioritized lead volume over price increase) and
override any node in the tree.

## Constraint precedence

When constraints conflict (e.g., a promising opportunity would exceed marketing budget),
the explicit `prohibited_actions` and `budget` fields always win over the EI's
optimization judgment. Exceeding a hard constraint is never a valid optimization path —
it surfaces as a proposal for the owner to raise the constraint, not a silent breach.

## Review and stop conditions

Goals are re-evaluated on their `review_interval`. If actual progress diverges
materially from the plan, or a stop condition triggers, the goal auto-pauses and
generates an owner-facing item in "what requires me" — it does not keep running on a
plan known to be failing.

## Relationship to Autonomy Levels

A goal's `allowed_actions` reference capability scopes that are themselves governed by
the Autonomy Level assigned per capability (see `docs/policies/README.md`). A goal
cannot grant an action a higher autonomy level than the Policy Engine already allows for
that capability — goals operate *within* policy, they don't set policy.
