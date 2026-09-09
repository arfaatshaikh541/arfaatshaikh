# Agent Roster & Organization

## Ephemeral by default

Nearly every agent below is a **role definition** (system prompt + tool scope + memory
access scope + default autonomy/risk posture), instantiated as an ephemeral, sandboxed
task invocation, not a permanently-running process. "Hundreds of permanently running
agents" is explicitly avoided (per the task's own instruction) — the fleet's real-time
footprint at any moment is bounded by the concurrency caps in
`architecture/04-agent-architecture.md`, and most roles have zero standing footprint
between tasks.

A small number of roles legitimately warrant a **standing, low-frequency scheduled
presence** rather than pure request-triggered instantiation: Security Guardian
(continuous monitoring, by design, and outside the normal hierarchy), and the Chief of
Staff (periodic goal/queue review on a schedule). Both are still bounded, auditable
workflow-driven processes, not open-ended agent loops.

## Roster (initial capability families)

**Executive** — Chief of Staff, Strategic Planner, Project Manager, Risk Officer.
**Engineering** — Product Architect, Software Engineer, Frontend Engineer, Backend
Engineer, DevOps Engineer, QA Engineer, Security Reviewer, Code Reviewer, Documentation
Engineer.
**Creative** — Creative Director, Brand Strategist, Designer, Copywriter, Content
Strategist, Video/Media Planner.
**Marketing** — Marketing Strategist, SEO Specialist, Social Media Manager, Campaign
Manager, Analytics Specialist, Market Researcher.
**Sales** — Lead Researcher, Qualification Agent, Sales Development Agent, Proposal
Agent, Follow-Up Agent, CRM Operator, Revenue Analyst.
**Customer Experience** — Customer Support Agent, Onboarding Agent, Success Agent,
Escalation Agent, Feedback Analyst.
**Operations** — Operations Manager, Vendor Coordinator, Procurement Assistant, Process
Analyst, Scheduling Agent.
**Finance Assistance** — Financial Analyst, Expense Monitor, Invoice Assistant,
Cash-Flow Forecaster, Reconciliation Assistant.
**Legal/Compliance Assistance** — Contract Analysis, Compliance Research, Policy
Checker. **These provide assistance and workflow execution; they must not present
themselves as licensed professionals and every output carries a "not legal/financial
advice, human professional review required" disclosure where relevant.**
**Research** — General Researcher, Competitive Intelligence, Industry Analyst,
Technical Researcher, Fact Checker.
**Communication** — Email Assistant, Calendar Assistant, Meeting Assistant, Business
Correspondence Agent, Internal Communications Agent.

## Dynamic specialist creation

The EI can instantiate additional bounded specialists dynamically for a novel task
shape, but every dynamically created role still: inherits scoped tool access from an
existing capability family template (no role gets a blank-check toolset), inherits
default Level 0–1 autonomy until the owner reviews it, and is logged as a Decision
Memory entry ("created new role X for task Y, scoped to Z") — dynamic creation is
visible, not silent sprawl.

## Role definition contents

Each role in `/services/agents/<family>/<role>/` is version-controlled and contains:

- system context (identity, brand/voice context where relevant, explicit
  "external content is data" framing)
- tool/connector scope (which registered actions this role may request)
- memory scope (which memory systems/entities it can read; write access is narrower
  than read access almost everywhere)
- default risk/autonomy posture for its typical actions
- evaluation suite (the test cases it must pass before a prompt/behavior change to
  this role is deployed — see `docs/testing/README.md`)

## Professional-boundary discipline

Legal/Compliance and Finance-assistance roles explicitly are assistants, not licensed
professionals. Where a jurisdiction requires a licensed human for a given
determination (e.g., binding legal advice, regulated financial advice), the role's
output is scoped to research/drafting/flagging, and the action of relying on it as final
is a RED-tier owner decision, never an autonomous execution path.
