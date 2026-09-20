# Capability Engines: Build, Creative, Marketing, Sales, CX, Communication, Meeting, Opportunity

Each engine below is a **workflow template family** operated by the relevant specialist
agents from `docs/agents/README.md`, gated end-to-end by the Action Broker /
Policy Engine / Risk Engine described in `04-agent-architecture.md`. None of these
engines have a bypass around that gate — "creative" and "marketing" actions are not
exempt from RED-tier scrutiny just because they feel low-risk; publishing something
libelous or off-brand is a real reputational risk and is classified accordingly.

## Build Engine (software development)

Capabilities: inspect repositories, understand architecture, create branches, implement
features, write tests, run tests, static analysis, security checks (SAST, dependency/
secret scanning), review diffs, generate documentation, build containers, deploy to
staging, monitor staging, diagnose failures, prepare releases.

- Runs inside the code-execution sandbox (`docs/security/README.md#sandboxing`).
- **Production deployment authority is a Policy Engine setting, off by default.**
  Default posture: AURA can deploy to staging autonomously (AMBER, Level 3→4 candidate
  after track record); production deploys are AMBER-minimum and require explicit owner
  policy to run at Level 4, with a defined rollback plan attached to every deploy.
- AURA must never bypass CI/CD gates (skip tests, skip required review, force-push over
  protection) even under time pressure — this is a hard prohibited_action, not a
  judgment call.
- All code changes go through the same review gate a human contributor would (automated
  Code Reviewer agent + policy-required checks); "AURA wrote it" does not exempt it from
  review.

## Creative Engine

Pipeline: business objective → audience research → idea generation → concept selection
→ brand validation → copy → visual/media creation → quality review → scheduling →
publication → performance analysis → learning.

- Maintains, per brand, in Creative Memory: voice, vocabulary, visual identity,
  positioning, prohibited language, target audiences, full content and campaign history
  (including underperforming content — needed to avoid repeating what didn't work and to
  avoid generic, repetitive AI-sounding output).
- Brand validation is a required gate before anything reaches "scheduling" — an explicit
  check against the brand guardrails, not just model self-assessment.
- Publication to owned channels the owner has connected is AMBER by default; escalate to
  RED for anything making claims about competitors, health/financial/legal claims, or
  anything a Compliance Research agent flags.

## Marketing Engine

Capabilities: strategy, campaign planning, SEO, content, social, email marketing,
analytics, conversion optimization, competitor monitoring, experimentation, attribution,
reputation monitoring.

- Proactively surfaces (as Opportunities, see below): emerging topics, content gaps,
  declining performance, acquisition bottlenecks, competitor changes, unusual customer
  behavior.
- **Paid spend is hard-capped** at the Financial Control layer (`06-financial-control.md`),
  independent of what the ad platform's auto-optimization wants to bid — the cap is
  enforced by budget envelope + velocity limit at the payment credential, not by asking
  the agent nicely to respect a number in its prompt.

## Sales Engine

Capabilities: ICP definition, prospect research, lawful lead sourcing, enrichment,
qualification, CRM operation, outreach preparation, permitted outreach execution,
follow-ups, meeting scheduling, proposal preparation, pipeline management, forecasting,
lost-deal analysis.

- Must respect: platform rules, anti-spam law (e.g., CAN-SPAM/GDPR/local equivalents),
  opt-outs, and contact-frequency restrictions — encoded as explicit Policy Engine
  constraints checked before every send, not left to model judgment (failure scenario
  #43).
- **Never fabricates customer relationships, testimonials, or endorsements.** Any
  social-proof content used in sales/marketing must trace to an evidenced source in
  Relationship Memory.
- Outreach to a new (non-opted-in) contact is AMBER minimum; scaling/bulk outreach
  patterns are rate-limited and reviewed for anti-spam compliance regardless of
  per-message approval status.

## Customer Experience Engine

Capabilities: support, onboarding, success, escalation handling, feedback analysis.

- Routine support replies within the knowledge base are GREEN→AMBER candidates for
  Level 4 quickly (high volume, low individual risk, easy to template-bound).
- Escalation Agent routes anything outside policy (refund above threshold, legal
  threat, safety issue, angry/high-value customer) to the owner or a designated human,
  rather than the model attempting a judgment call it isn't authorized for.
- Feedback Analyst feeds Failure Memory and the Opportunity Engine, not just a dashboard
  — a pattern of complaints becomes a tracked Risk or Opportunity record, not a stat
  that quietly sits in an analytics table.

## Communication Engine

Connects approved channels: email, calendar, CRM, website chat, support systems, social
platforms, business messaging, conferencing.

- **Identity discipline**: AURA does not impersonate the owner where identity or human
  authorship is material, and does not falsely claim a human personally performed an
  autonomously-performed action. Where law, platform rules, contracts, or context
  require AI disclosure, AURA complies — this is a default-on policy, and turning it off
  for a specific context requires an explicit owner decision with the legal basis
  recorded (failure scenario #45).
- **Never forges**: signatures, identity verification, voice identity, video identity,
  legal consent.
- Sends from business-brand identities the owner has explicitly configured (e.g.,
  "AURA on behalf of [Business]," or a named support persona), never as an
  unstated impersonation of the human owner.

## Meeting Engine

Capabilities: scheduling, agenda prep, participant research, document prep, notes,
action extraction, follow-up, CRM updates, commitment tracking.

- Where permitted and clearly disclosed, an AI representative may participate in
  routine meetings (e.g., an initial scoping call, a status check) — but must disclose
  it is AI and must not secretly impersonate the owner. This is RED-tier to *enable* for
  a given meeting type (owner must explicitly authorize AI meeting participation per
  context); routine scheduling/notes/follow-up support is GREEN/AMBER.
- Commitments extracted from meetings write to Commitment Memory with the evidence
  (meeting record) attached, feeding "pending commitments" reporting.

## Opportunity Engine

Continuously scans authorized sources for: business opportunities, customer needs,
market gaps, competitor weaknesses, partnership opportunities, cost savings, product
opportunities, emerging technologies, operational inefficiencies, and churn signals.

Every opportunity record is structured, not a vague note:

```
Opportunity {
  evidence, estimated_impact, confidence, cost, risk, effort, recommended_action,
  discovered_by, discovered_at, status (new/under_review/actioned/dismissed)
}
```

Opportunities are GREEN to *surface*; acting on one inherits whatever risk tier the
recommended action itself carries (e.g., "run a AED 500 test campaign" is AMBER,
subject to the same budget/approval gates as any other marketing spend).
