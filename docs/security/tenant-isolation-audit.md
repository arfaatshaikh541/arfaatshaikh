# Independent Tenant-Isolation Audit

**Scope:** every enterprise-tenant-scoped table and code path in `apps/control-api`, across all 38
migrations and the modules that query them. **Method:** exhaustive inventory (every RLS policy,
every `PlatformBypass`/`withPlatformBypass` call site, every session-GUC-setting middleware, every
existing isolation test), not a sample — see the methodology note at the end of this document.
**Not in scope:** application-security concerns unrelated to tenant boundaries (see
`docs/security/application-security-audit.md`) and Kubernetes/cryptographic/supply-chain concerns
(see the Milestone 16 audits of the same name).

## Architecture summary

Tenant isolation in this codebase rests on PostgreSQL Row-Level Security, not application-code
filtering. Every tenant-owned table carries a policy of the shape:

```sql
CREATE POLICY <table>_tenant_scope ON <table>
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
```

`app.tenant_id` is a transaction-local (`SET LOCAL`, i.e. `set_config(..., true)`) session variable,
set exactly once per request by `internal/modules/rbac/middleware.go`'s `RequireEnterprisePermission`
or `RequireEnterpriseMembership`, via `store.BeginScoped(ctx, dbpkg.Scope{TenantID: &tenantID})`
(`internal/platform/db/db.go:60-93`). A handler never opens its own unscoped connection for
tenant-facing routes; the scoped transaction is threaded through `rbac.TxFromContext`.

## Strength: the isolation model is fail-closed by construction, confirmed exhaustively

Two independent facts, both verified across every one of the 38 migrations and the entire `internal/`
tree, combine to make "no scope set" fail closed rather than fail open:

1. **Every single `current_setting(...)` call in this codebase uses the `missing_ok=true` form** —
   zero uses of the strict form exist anywhere in `migrations/` or `internal/`. This means an unset
   GUC never raises a Postgres error; it returns SQL `NULL`.
2. **Every policy wraps that result in `NULLIF(current_setting(...), '')::uuid`** before comparing to
   a UUID column. `NULL = <anything>` is never `true` under SQL's three-valued logic, so a
   transaction with no tenant scope set sees **zero rows**, never every row. The only way to see
   "every row" is the separate, explicit `current_setting('app.platform_bypass', true) = 'true'`
   policy, which requires that GUC to be the literal string `'true'`.

`BeginScoped` (`internal/platform/db/db.go:79-89`) also always explicitly `set_config`s all three
GUCs (`app.tenant_id`, `app.operator_id`, `app.platform_bypass`) on every call, to `''`/`'false'` for
whichever `Scope` fields are unpopulated — so a scoped transaction never inherits ambient state from
a previous connection-pool user. `TestTenantAndOperatorRowLevelSecurity`
(`internal/app/isolation_test.go`) proves this directly at the database layer for `enterprise_tenants`
itself: a raw, no-`WHERE`-clause `SELECT` inside a tenant-A-scoped transaction returns only tenant A's
row.

## Inventory: tenant-scoped tables

- **~30 tables** carry the simple two-policy shape (`<table>_tenant_scope` `ALL` + `_platform_bypass`
  `ALL`): `sovereignty_policies`, `policy_evaluation_records`, the full `models`/`model_versions`/
  `model_capabilities`/`model_benchmarks`/`model_safety_evaluations`/`model_deployment_profiles`
  family, the container-supply-chain family (`container_images`, `image_signatures`,
  `image_provenance`, `sboms`, `vulnerability_scans`/`_findings`/`_policies`/`_exceptions`),
  `artefact_uploads`/`artefact_access_grants`, the workload family (`workloads`, `workload_versions`,
  `workload_components`, `workload_health_checks`, `workload_artefacts`, `model_artefacts`,
  `workload_version_sboms`), `deployment_plans`, `workload_secrets`, `placement_requests`/
  `placement_evaluations`, `network_service_requests`/`_evaluations`, `quotes`, `budgets`.
- **~19 tables** carry the dual-scope, three-policy shape (`_tenant_scope` OR `_operator_scope` OR
  `_platform_bypass`, Postgres ORs permissive policies together): `capacity_reservations`,
  `deployments`, `deployment_events`, `network_reservations`, `network_health_events`,
  `slo_definitions`, `slo_evaluations`, `incidents`, `incident_events`, `alert_rules`, `alerts`,
  `usage_events`, `usage_aggregations`, `invoices`, `adjustments`, `credit_notes`,
  `billing_disputes`, `billing_provider_events`, `bilateral_agreements`, `capacity_offer_grants`,
  `settlement_records` — each of these genuinely has both a tenant and an operator party with a
  legitimate reason to read the same row (a deployment belongs to both the tenant who requested it
  and the operator running it, an invoice belongs to both the billed tenant and the billing
  operator, etc.).
- **11 tables** carry the "owner `ALL` + additional permissive cross-tenant `SELECT`" marketplace
  pattern this codebase established in Milestones 5, 12, and 13: `capacity_offers`,
  `network_service_offers`, `price_books`, `price_rules`, `bilateral_agreements`,
  `capacity_offer_grants`, `settlement_records`, `model_access_grants`, `model_versions`,
  `model_capabilities`, `model_benchmarks`, `model_safety_evaluations`, `model_deployment_profiles`.
  Postgres ORs the owner policy and the additional `SELECT` policy together — a cross-tenant reader
  never gets write access, only a narrower read.
- **9 tables** are deliberately operator-scope-only, with no tenant-facing read path at all:
  `operator_agents`, `agent_certificates`, `capacity_snapshots`, `cluster_agents`,
  `cluster_agent_certificates`, `control_messages`, `deployment_plan_validations`,
  `attestation_policies`, `attestation_sessions` — correct, since these are pure
  infrastructure-operational tables a tenant has no legitimate reason to read.
- Global reference tables (`jurisdictions`, `regions`, `roles`/`permissions`/`role_permissions`,
  `model_providers`, `model_licences`, `approved_container_registries`, `platform_ca`,
  `usage_metrics`, the user-identity tables) correctly carry no RLS — each has an explicit migration
  comment stating why (no tenant/operator ownership column exists on the table at all).

## Findings

### Finding 1 (Medium) — `support_access_grants` has no RLS despite a tenant/operator-shaped scope column

`support_access_grants` (`migrations/0006_platform_admin.up.sql`) has `scope_type TEXT CHECK
(scope_type IN ('enterprise','operator'))` and `scope_id UUID NOT NULL` — functionally identical in
purpose to every other table's `enterprise_tenant_id`/`operator_id` column — but carries **no `ENABLE
ROW LEVEL SECURITY`, no policy, anywhere** across all 38 migrations. Today, the only production code
path that reads it is `rbac.middleware.go`'s `activeSupportAccessGrant`, gated by the
`platform.support_access.view` permission and run on the raw, unscoped pool — so there is no
currently-reachable path for a tenant or operator to read another party's support-access grant. This
is not a currently-exploitable vulnerability; it is a defense-in-depth gap. If a future change adds a
second query path against this table without going through the vetted repository function, there is
no database-level backstop the way there is for every other scoped table in this codebase.

**Recommendation:** add RLS to `support_access_grants` with a policy matching its intended visibility
(most likely platform-role-only, since a support grant is inherently a platform-administration
concern rather than something the affected tenant/operator queries directly) plus the standard
`platform_bypass` policy. Track as a follow-up migration; not a blocker for this milestone's sign-off
since no exploitable path exists today.

### Finding 2 (Low, addressed this milestone) — marketplace grant-gated policies lacked a raw-database-layer isolation test

Every marketplace policy in the third bullet above (the "owner + additional permissive `SELECT`"
shape) had cross-tenant visibility tested only through the HTTP/application layer
(`TestAIModelExchangeMarketplaceGrantsEligibilityAndLicensing`,
`TestPlacementEvaluatesRanksAndDualControlsCommit`) — unlike `enterprise_tenants`, which
`TestTenantAndOperatorRowLevelSecurity` proves directly against a raw scoped transaction. These are
exactly the policies most likely to hide a subtly wrong `EXISTS` clause behind a passing
application-layer test (an off-by-one in the grant-status check, for instance, could still pass an
HTTP-level test that only checks the visible list's length in the common case).

**Remediation (this milestone):** added
`TestPrivateCapacityOfferMarketplaceRLSDeniesNonGrantedTenant`
(`internal/app/isolation_test.go`) — proves, with a raw `SELECT` inside a tenant-scoped transaction
(no HTTP layer involved), that a private `capacity_offers` row is invisible before any grant exists,
becomes visible to exactly the granted tenant once an active grant is created, becomes invisible
again once the grant is revoked, and is never visible to a third, uninvolved tenant at any point in
the sequence. Run against a real Postgres instance; passes.

**Not yet replicated:** the identical pattern for `model_versions_marketplace_read` (Milestone 13) —
its `EXISTS` clause is structurally near-identical to `capacity_offers`', so the risk is materially
lower than it was before this milestone's fix, but a future milestone should add the equivalent test
for completeness.

### Finding 3 (Informational) — an intentional, but worth-revisiting, marketplace-visibility asymmetry

`network_service_offers_enterprise_read` and `price_books_enterprise_read`/`price_rules_enterprise_read`
remain "any authenticated tenant may read any `status='active'` row," unlike `capacity_offers` and the
`model_versions` family, which were later upgraded (Milestones 12/13) to grant-gated private
visibility. This is a documented, intentional design choice — migration `0036`'s own header comment
explicitly contrasts the new grant-gated `capacity_offers` policy against "the same 'invitation-only'
shape network_service_offers_enterprise_read and price_books_enterprise_read already established for
their own visibility rules, just conditioned on ... a blanket 'any authenticated tenant' ... check" —
not an oversight. It is flagged here only because a future product requirement for private/
invitation-only network services or price books would need the identical `capacity_offer_grants`
pattern replicated for those two tables; no action is required today.

## Machine-caller RLS bypass review

Every direct `dbpkg.Scope{PlatformBypass: true}` call site in production code (as opposed to the
`withPlatformBypass`-on-an-already-scoped-transaction helper, which exists purely so a tenant-scoped
call can read an operator-scope-only table it has independent authorization to touch, e.g. resolving
a cluster agent during deployment creation) falls into exactly one of two categories:

1. **Pre-membership / row-doesn't-exist-yet** actions: `CreateTenant`, `CreateOperator`,
   token-based `AcceptInvitation` (both tenancy and operators), `ListMyMemberships` (deliberately
   cross-scope, for the account switcher). None of these have any tenant/operator row to scope to
   yet, or are intentionally cross-scope by design.
2. **Machine-to-machine calls with no user session**: agent bootstrap, certificate rotation,
   capacity-snapshot submission, control-message polling/response, attestation session
   request/evidence submission, network-provisioning result reporting, signed usage reporting. Every
   one of these is authorized by an ECDSA signature check performed in application code *before* any
   row is read or written — the same "verify before trusting the caller's claimed identity"
   discipline RLS exists to enforce for session-authenticated routes, just enforced one layer up
   because there is no session to derive a GUC from. `RequirePlatformPermission` (a third,
   session-authenticated case) is included here too: its authorization decision
   (`platformPermission(...)` against `platform_role_assignments`) is made *before* the bypass-scoped
   transaction is even opened, so RLS plays no role in that specific permission decision — only in
   what the handler is subsequently allowed to see.

No call site was found where `PlatformBypass: true` is used as a shortcut around an otherwise
enforceable tenant-scope check with no compensating authorization. This matches the existing,
narrower finding already on record in `docs/project-status.md`'s Unresolved Risks for capacity-snapshot
ingestion specifically — this audit generalizes and confirms the same reasoning holds for every other
bypass call site, not just that one.

## Verdict

Tenant-isolation architecture is sound: RLS is the real boundary (not merely a second check behind an
application-layer filter), it fails closed on missing scope, and every machine-caller bypass is
compensated by an equivalent-or-stronger authorization check performed first. One real gap
(`support_access_grants` lacking RLS) is documented as a defense-in-depth recommendation, not a
currently-exploitable finding. One test-coverage gap was found and closed this milestone; one is
noted as a lower-priority follow-up. No cross-tenant data leak was found in any inventoried policy,
bypass call site, or existing/added test.

## Methodology note

This audit's factual inventory (every RLS policy and its exact clause, every bypass call site, every
GUC-setting middleware, every existing isolation test) was produced by an exhaustive, file-by-file
pass across all 38 migrations and the entire `internal/` tree — not sampled, not inferred from
naming conventions alone. Every citation above is a real `file:line` reference verified against the
actual source at the time of writing. The synthesis, severity judgments, and the new test are this
author's own.
