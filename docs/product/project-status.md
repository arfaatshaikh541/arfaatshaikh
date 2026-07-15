# Project status

**Current milestone:** Milestone 9 — Platform Super Admin: Commercial Catalog Management
**Status:** Complete, verified against a real PostgreSQL + Redis stack. Awaiting your review before starting Milestone 10.
**Last updated:** 2026-07-15

---

## What was built (Milestone 9)

Two forward-references left in earlier milestones defined this one:
`apps/api/app/db/seed/catalog.py` states the commercial model (modules,
features, plans, add-ons, usage metrics) is "meant to be edited by the
platform team (later: through the Platform Super Admin UI planned for
Milestone 9)," and the `/admin/plans` page said "Plan editing UI ships
in Milestone 9" since launch. Until now, that catalog could only be
*read* through the platform-admin API (`GET /platform/modules`,
`GET /platform/plans`) — every change required editing Python seed code
and redeploying. This milestone makes the whole catalog manageable at
runtime.

### Backend (`apps/api`)
- **Full CRUD for the commercial catalog**, all under the existing `require_platform_admin` dependency — no new authorization primitive:
  - **Modules & features**: creatable and editable (name/description only). Deliberately **not deletable** — `Module.code`/`Feature.code` are referenced directly in Python (`require_module("...")`, `require_feature("...")` across nine modules), so removing one out from under running code would silently break those checks. A feature's `feature_type` is likewise immutable after creation, since existing `plan_features`/`tenant_feature_overrides`/`add_ons.grants` rows already store a config dict shaped for that type.
  - **Plans**: full CRUD — create, edit name/description, and activate/deactivate. No hard delete (`SubscriptionPlan` is `RESTRICT`-referenced by `TenantSubscription.plan_id`) — deactivating is the "stop offering this, don't destroy history" equivalent, the same pattern already used for `document_requests`/`proposal_templates`.
  - **Plan-feature grants**: a per-plan editor endpoint (`PUT`/`DELETE /platform/plans/{id}/features`) that builds the `PlanFeature.config` dict from the feature's own `feature_type` — never trusting an arbitrary client-supplied shape — so a boolean feature always gets `{"enabled": bool}` and a limit feature gets `{"limit": int}` (or explicit `{"enabled": false}`), preventing a config shape `resolve_entitlements` wouldn't know how to interpret.
  - **Add-ons**: full CRUD (code, name, and the `grants` dict of feature codes + config an add-on turns on).
  - **Usage metrics**: full CRUD (code, name, unit) — no code-level reference constraints, unlike modules/features.
- **Duplicate-code protection**: creating a module, feature (scoped to its module), plan, or add-on with an already-used code returns 409 with a specific `*_code_taken` error code, never a silent overwrite.
- **Auditing**: every mutation (create/update/activate/deactivate/grant/remove) logs through the existing `audit_service.log_event` with `tenant_id=None`, since this catalog is platform-global rather than tenant-owned data.
- **Zero new permission codes or database migrations** — this milestone is entirely a management layer on top of Milestone 1's existing `modules`/`features`/`subscription_plans`/`plan_features`/`add_ons`/`usage_metrics` schema, and the platform team's access model (a single `User.is_platform_admin` boolean) was already sufficient.
- **14 new pytest tests** (172 total with Milestones 1–8's): module/feature create+update, duplicate-code conflicts for both, plan create/update/deactivate with the active-vs-all-plans list distinction, plan-feature grant set/remove for both boolean and limit features, add-on create+update, usage metric create+update, and a 403 test confirming a non-platform-admin (a tenant owner) is rejected on every new route.

### Frontend (`apps/web`)
- `/admin/modules` — now supports creating a module, editing name/description inline, and — per module — creating and editing features (with a boolean/limit type selector at creation).
- `/admin/plans` — now supports creating a plan, editing name/description inline, activating/deactivating (with a toggle to show inactive plans), and a per-plan feature-grant editor (checkbox to grant/revoke each feature, a numeric input for limit features).
- New `/admin/add-ons` — create/edit add-ons, with a repeatable grant-row editor (pick a feature, optionally set its limit) that builds the `grants` JSON.
- New `/admin/usage-metrics` — create/edit usage metrics.
- Platform admin sidebar nav gained "Add-ons" and "Usage metrics" entries.

### Tests & verification
- `ruff check app` — 0 errors. `pytest -q` — 172 passed. `eslint` — 0 errors. `tsc --noEmit` — 0 errors. `next build` — succeeds, 51 routes. `vitest run` — 4 passed.
- No new Alembic migrations this milestone (none needed).
- Manually smoke-tested over real HTTP with the API server actually running, logged in as the seeded platform admin: created a module and two features (one boolean, one limit) live; confirmed a duplicate module code returned 409; created a plan, granted both a boolean and a limit feature to it, confirmed the grants via `GET .../features`, removed the limit grant and confirmed it disappeared, deactivated the plan and confirmed it dropped out of the default (active-only) plans list but still appeared with `?all_plans=true`; created an add-on and a usage metric; logged in as a tenant owner (not a platform admin) and confirmed every one of these routes correctly returned 403 `platform_admin_required`; and confirmed all ten catalog mutations from this session appeared correctly in `/platform/audit-logs` with `tenant_id: null` and the expected `catalog.*` action names.

## Acceptance criteria — verified

| Criterion (from your Milestone 9 spec) | Verified how |
|---|---|
| Platform team can manage the commercial catalog without redeploying | Full CRUD on modules, features, plans, plan-feature grants, add-ons, and usage metrics, all live through `/platform/*` |
| No hardcoded customer-specific or plan-access data reaches the frontend | The frontend renders whatever the catalog API returns; no plan/module/feature logic is hardcoded client-side (unchanged from every prior milestone) |
| Existing tenants' entitlements resolve correctly against catalog edits | `resolve_entitlements` (Milestone 1) was untouched — it already reads `plan_features`/`add_ons` dynamically, so catalog edits take effect immediately with no code change needed |
| Safe editing (no way to break running entitlement checks) | Module/feature codes and feature types are immutable after creation; plan-feature config is server-constructed from the feature's own type, never trusted from the client |
| Auditability | Every catalog mutation logs through the existing audit system, verified live |
| Correct access control | `require_platform_admin`, unchanged; verified 403 for a non-platform-admin on every new route |

## Known limitations

1. **No delete for modules, features, plans, or add-ons** — a deliberate design choice (see above), not a gap: modules/features are code-referenced and plans/add-ons are FK-referenced, so "deactivate" (plans) or "just don't grant it to any plan" (features/add-ons) is the safe equivalent. If a genuine hard-delete need arises later, it would require an explicit "is this code still referenced anywhere in the codebase" check that's out of scope for a data-layer CRUD milestone.
2. **No bulk/CSV import for catalog data** — every module/feature/plan/add-on/usage-metric is created one at a time through the UI or API. Acceptable at the platform team's current scale (a handful of plans and roughly a dozen modules); a bulk-import tool would be a natural follow-up if the catalog grows significantly.
3. **The add-on grants editor is intentionally simple** — it supports one feature-code + optional-limit pair per row, matching the actual shape used by every seeded add-on. An add-on wanting a more exotic config shape (e.g. multiple overlapping limits) would need direct API use rather than the UI.
4. **Same environment caveats as Milestones 1–8 carry forward**: Docker Compose itself was not run end-to-end in this sandbox; all verification used the same application code run directly against local PostgreSQL 16 + Redis 7, including a real running `uvicorn` instance for the live HTTP smoke test. No browser was available to visually confirm the new UI.

## Pending decisions

None new this milestone — Milestone 1's pending decisions (tenant-URL routing, production email/storage provider choice) remain open and don't block Milestone 10. Milestone 7's malware-scanning production integration question (ClamAV vs. a cloud AV API) also remains open.

## Next action

Awaiting your review of Milestone 9. To proceed, reply exactly: **APPROVE MILESTONE 10**

Milestone 10 (per the original 10-milestone plan) is the final
milestone: security & compliance hardening — platform-wide rate
limiting (today it's login-only), a CSRF token for state-changing
requests, and a dependency audit pass, all flagged as deferred-to-M10
items in `docs/security/README.md` since Milestone 1.
