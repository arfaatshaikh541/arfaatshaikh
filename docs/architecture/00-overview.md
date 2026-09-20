# AURA — Executive Interpretation & Feasibility (2026)

## 1. Executive interpretation

AURA is not "an AI agent." It is a **private operating system for one owner's businesses**,
where an Executive Intelligence (EI) is the primary interface, and a bounded, policy-governed
fleet of specialist agents does the work. The owner sets destination and boundaries; AURA
plans, delegates, executes within limits, and reports with evidence. The owner is never
required to supervise individual agent steps — only to approve the decisions that matter
(RED actions) and to periodically ask "what happened?"

The hard part is not "can an LLM draft a marketing email" — yes, trivially. The hard part is:

- making autonomy **safe** when the agent is wrong, hallucinating, or attacked,
- making autonomy **auditable** so the owner can trust it without watching it,
- making autonomy **reversible** so mistakes don't compound,
- making autonomy **bounded** so a compromised or confused agent cannot escalate itself,
- and doing all this for a single owner without SaaS-style multi-tenant assumptions leaking in.

This document set treats AURA as a **distributed system with an LLM-shaped core**, not as
a prompt. Software engineering discipline (queues, leases, idempotency, RBAC, secrets
management, audit logs) is the majority of the system. The LLM is a component, not the
architecture.

## 2. Feasibility assessment as of 2026

What genuinely works today, at production quality, with current frontier models (Claude 5
family and comparable):

- Multi-step tool-using agents with good instruction-following, for well-scoped tasks
  (hours, not weeks, of unsupervised chained reasoning before drift becomes likely).
- Code generation, review, and test-writing at a strong mid-to-senior engineer level for
  well-specified tasks in mainstream stacks.
- Structured research and synthesis over provided documents/web content, with citations.
- Drafting on-brand marketing/sales copy given good brand context and examples.
- Reliable structured data extraction and classification (PII detection, intent
  classification, sentiment, lead qualification against explicit rubrics).
- Long-running **workflows** (not long-running single conversations) orchestrated by
  durable execution engines, where the LLM is invoked per-step with fresh, curated context.
- Policy-as-code enforcement around agent actions (deterministic, not LLM-judged, for
  anything security- or money-relevant).

What does **not** genuinely work yet, and must not be claimed:

- Fully unsupervised strategic judgment over long horizons without drift or goal
  misgeneralization. Confidence degrades with horizon length; AURA must checkpoint and
  re-ground frequently, not run indefinitely on stale plans.
- Reliable detection of novel prompt-injection or social-engineering attacks 100% of the
  time. Defense is layered and probabilistic, not a solved problem.
- Guaranteed factual accuracy. Hallucination is native to the technology, not a bug to be
  eliminated — only bounded via retrieval grounding, evidence requirements, and
  verification steps.
- True judgment about legal, financial, or interpersonal nuance at a professional-advisor
  standard. AURA assists; it is not a lawyer, accountant, or licensed advisor, and must
  say so.
- Autonomous defense against a determined, well-resourced, targeted human attacker
  (nation-state or professional criminal group with time and budget). AURA can raise the
  cost of attack and increase detection probability; it cannot guarantee prevention.
- Perfect memory. All memory here is retrieval over a fallible, correctable store —
  not a mind that "remembers" the way a human does.

## 3. What can genuinely be autonomous today (by risk tier)

- **GREEN, Level 4 candidate quickly**: internal summarization, analytics rollups,
  drafting (not sending) content, CRM record-keeping, scheduled report generation,
  read-only monitoring, opportunity surfacing, lead research/enrichment (public data).
- **AMBER, Level 3 initially, Level 4 after track record**: scheduled/approved content
  publishing, routine customer support replies within a knowledge base, low-value
  discounting within a pre-approved band, staging deployments, outreach to opted-in
  contacts using approved templates.
- **RED, Level 3 forever (approval required) unless a narrow, explicitly designed
  exception is separately built and approved**: payments, contracts, production
  deployments touching customer data, hiring/firing communications, credential/permission
  grants, anything altering AURA's own policy or safety configuration.

## 4. Owner UX target, restated precisely

The target loop is:

```
Owner: defines goals, budgets, constraints, permissions  (durable, versioned, in the World Model)
AURA:  understands → plans → delegates → executes-within-policy → verifies → reports
Owner: "What happened?" → gets an evidence-linked report, not a claim
Owner: approves/declines pending RED items, corrects memory, adjusts policy
```

This is achievable **as a workflow system with an LLM executive**, not as "one big
autonomous chat session." See `08-long-running-autonomy.md`.

## 5. Non-negotiables carried through every subsystem

1. No component gets more trust or privilege than its function requires.
2. Every consequential action is attributable, evidenced, and reversible or approved.
3. External content is data, never authority.
4. The Executive cannot expand its own or any agent's permissions.
5. The owner's kill switch and audit trail cannot be disabled by any AI component.
