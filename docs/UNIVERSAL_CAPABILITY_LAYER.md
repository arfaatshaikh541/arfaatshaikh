# The Universal Capability Layer: what's real, what's scoped out

This document is the honest scope statement for the "general-purpose
autonomous operating intelligence" pass. The request that drove this
work asked for something on the order of a multi-year, multi-team
product: dynamic arbitrary-code skill creation, fifteen separate
business-domain intelligence packages, a full simulated business (100
prospects, 20 customers, invoices, incidents, campaigns), and a
literal 1,000-command hardcoded evaluation suite. Building all of that
for real, to the standard this codebase has held all along (real
execution, real verification, never a mock presented as production),
is not something any single engineering session can honestly deliver.
Claiming otherwise would be exactly the "fake universality" this
system's own governing principle refuses.

What follows is what got built for real this pass, what deliberately
did not, and why — so nothing here is mistaken for more than it is.

## Built this pass (real, tested, wired into the running system)

### `aura_core.capabilities` — Capability Registry
A `Capability` dataclass (name, description, domain, tools,
verification, evidence_kind, inputs) wraps every action_type that
already has a real, registered handler in this codebase (48 entries,
hand-verified against `connectors/*.py`, `actions/builtins.py`, and
`governance/risk_engine.py`'s classification tables — not invented).
`CapabilityRegistry` joins that static catalog against a live
`ConnectorRegistry` and `RiskEngine`, so `is_handler_registered()` and
`status()` report what's *actually reachable in this running process*,
not just what's cataloged. Deliberately excluded: business-process
ideas with no registered handler (`crm.read`, `crm.write`, and every
RED-tier action_type) — cataloging those as executable capabilities
would misrepresent policy placeholders as real code.

### `aura_core.skills` — Skill Registry, Engine, and (scoped) Dynamic Builder
A `Skill` is a named, persisted, ordered composition of *existing*
capabilities (`SkillStep.capability_name` + a params template).
`SkillEngine` runs every step through the real `ActionBroker` — the
same kill-switch/risk/policy/approval/audit path any other submission
takes; a Skill cannot bypass governance. `DynamicSkillBuilder.compose()`
is the deliberately safe interpretation of "AURA can create a new
skill": it validates every step's capability name against the real
registry and rejects anything unknown outright, and it only ever
*composes* what already exists. **What this explicitly does not do**:
generate and execute novel, unreviewed code. That is a materially
different, much larger security undertaking — handing an autonomous
system arbitrary code execution authority is precisely the category of
risk this whole governance model exists to prevent handing out
casually — and building it responsibly (sandboxing, static analysis,
a review/approval gate before first execution, resource limits) is a
separate, larger design effort, not a corner to cut here.

### `aura_core.planning` — Universal Planner + Capability Gap Resolver
`UniversalPlanner.plan(objective)` asks the Model Router for a JSON
array of steps, constrained to the real, currently-available capability
list (never the full aspirational catalog). `parse_plan_response()` is
a pure, independently-tested function (mirroring
`executive.parse_plan()`'s and `email_intent.classify_message_intent()`'s
established discipline): every proposed step is re-validated against
the real registry — a step naming an unknown or hallucinated capability
is never executed, it becomes a `CapabilityGap`
(OBJECTIVE/MISSING_CAPABILITY/REQUIRED_TOOL/REQUIRED_PROVIDER/
REQUIRED_PERMISSION/CAN_BUILD_SKILL/NEXT_ACTION, per the product
brief's own structure) instead. An unparseable model response is
reported as "could not parse a plan," never coerced into a fabricated
one.

### `aura_core.opportunities` — Opportunity/Risk ledger
`OpportunityRecord` matches the requested contract (evidence,
confidence, estimated impact, effort, recommended next action,
source, status) and persists across restarts. **What this explicitly
does not do**: detect opportunities or risks on its own. There is no
real business data in a fresh AURA instance to reason over yet —
inventing pattern-matching against an empty or synthetic World Model
would produce fabricated "insights" exactly like the mocked-LIVE
connectors this project already had to catch and fix earlier. This is
the ledger a real mechanism (a Skill, a scheduled workstream, a future
connector) writes into once it finds something real; it is not itself
that mechanism.

### CLI and API surfaces
`aura capabilities list [--domain] [--available-only]`,
`aura skills list|compose|run`, `aura plan "<objective>"`; `GET
/capabilities`, `GET|POST /skills`, `POST /skills/{id}/run`, `POST
/plan`, `GET|POST /opportunities`, `POST /opportunities/{id}/status`.
All gated exactly like every other mutating endpoint in this codebase.

### Evaluation harness
`tests/test_capability_evaluation_harness.py`: 61 cases (30 resolvable
across every real domain in the catalog, 25 gap cases spanning sales,
marketing, social strategy, customer support, coding/web dev, design,
active security testing, and plain model hallucination, 3 cross-domain
objectives mixing resolved steps and gaps in one request) against the
same pure `parse_plan_response()` the real planner uses — no network,
no mocking of the function under test. This is a genuine, real
generalization proof at a scale that's actually inspectable, not a
1,000-line suite padded to hit a round number.

## Deliberately not built this pass, and why

- **15 separate hardcoded "domain intelligence" modules** (deep ICP
  scoring formulas, SEO audit algorithms, ad-campaign strategy logic,
  etc.). Domains are metadata tags on real capabilities instead;
  cross-domain objectives are composed by the planner. Writing
  "intelligence" for a business domain with no real data or chosen
  provider behind it would produce generic-sounding advice dressed up
  as domain expertise — the same failure mode section 22 of the
  original product brief already warned against.
- **A Gridkeep business simulation** (100 prospects, 20 customers,
  synthetic emails/calls/tickets/invoices/campaigns). A large,
  standalone fixture-building effort; not attempted here.
- **A literal 1,000-command hardcoded evaluation suite.** See the
  evaluation harness section above for what was built instead and why.
- **New provider connectors** (Gmail, Microsoft 365, Zoho, Google/
  Microsoft Calendar, Salesforce, HubSpot, Zoho CRM, GitLab, AWS,
  Azure, GCP, Cloudflare, Vercel, Netlify, IONOS, X, TikTok, YouTube,
  accounting/payment platforms). Each is `REQUIRES_EXTERNAL_PROVIDER`
  (the owner has to pick one) before a real adapter can be built
  against a verified contract, exactly like this session's existing
  CRM/finance/cloud rows already state.
- **Real image/video generation, OCR, document generation.** No
  provider is configured for any of these; capabilities that would
  wrap them are absent from the catalog rather than cataloged as
  available with nothing behind them.

## What this means honestly

AURA can now: describe what it can actually do right now (not what a
future version might); decompose a novel objective into real
capabilities when the model correctly identifies them, and say
precisely what's missing when it can't; compose and permanently reuse
a named workflow out of existing capabilities without ever generating
unreviewed code; and record a real opportunity or risk for later
follow-up. That is a genuine capability-composition layer sitting on
top of the existing, already-real governance/connector/memory stack —
not the full fifteen-domain autonomous business this pass's request
described, and not presented as if it were.
