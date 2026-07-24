# Independent Operator-Isolation Audit

**Scope:** every telecom-operator-scoped table and code path in `apps/control-api`, across all 38
migrations and the modules that query them, plus the machine-identity trust model between control-api
and each operator's own agents (`operator_agents`, `cluster_agents`) — the isolation boundary unique
to the operator side that has no tenant-side equivalent. **Method:** same exhaustive inventory as the
companion `tenant-isolation-audit.md`; see that document's methodology note. This audit assumes that
document's shared findings (the fail-closed `NULLIF`/`missing_ok` pattern, `BeginScoped`'s
always-set-all-three-GUCs behavior) rather than re-deriving them.

## Architecture summary

Operator isolation uses the identical RLS mechanism as tenant isolation, scoped on `app.operator_id`
instead of `app.tenant_id`, set by `RequireOperatorMembership`/`RequireOperatorPermission`
(`internal/modules/rbac/middleware.go:186-329`). Everything in the companion audit's "fail-closed by
construction" section applies identically here — operator-scope policies use the same
`NULLIF(current_setting('app.operator_id', true), '')::uuid` pattern, with the same universal
`missing_ok=true` usage confirmed across every migration.

## What is unique to the operator side (vs. tenant isolation)

Enterprise tenants have no analogue to **operator infrastructure and machine agents** — the tables an
operator's own Kubernetes clusters and cluster-agent daemons write to and read from, authenticated by
certificate/signature rather than a user session. This is the operator-side isolation boundary that
most needs independent scrutiny, since it is enforced by cryptography and application code, not RLS,
for the machine-caller half of every request.

### Operator-scope-only tables (9): the correct default for infrastructure data

`operator_agents`, `agent_certificates`, `capacity_snapshots`, `cluster_agents`,
`cluster_agent_certificates`, `control_messages`, `deployment_plan_validations`,
`attestation_policies`, `attestation_sessions` carry only an `_operator_scope` policy plus
`_platform_bypass` — **no tenant, no matter how privileged within their own tenant, has any RLS path
into these tables.** This is correct: a tenant has no legitimate reason to read another party's
cluster inventory, agent certificates, in-flight control messages, or attestation session state. Where
a tenant genuinely needs a narrow, derived fact from this data (e.g., "is my deployment's target
cluster attested"), it is served by an explicit, redacted read path in application code (see
`RedactedAttestationResult` in the Milestone 15 workload page, which selects only `decision`/
`reason_codes`/`evaluated_at` — never raw measurements or evidence), never by widening these tables'
own RLS.

### Machine-agent trust model: certificate + signature, verified before any row is touched

Every operator-agent and cluster-agent action that bypasses RLS (see the companion audit's full
"Machine-caller RLS bypass review" — the same call sites apply, this section adds operator-specific
context) follows one consistent shape:

1. The agent holds a private key whose corresponding certificate was issued during bootstrap
   (`internal/platform/pki`), scoped to exactly one `operator_agents`/`cluster_agents` row.
2. Every subsequent request signs a server-issued, single-use challenge (bootstrap) or a
   deterministic payload derived from the request itself (capacity snapshot, control-message
   response, usage report) with that key.
3. Application code verifies the signature against the certificate **on file for that specific
   agent row**, checks the certificate has not been revoked (`agent_certificates.revoked_at`/
   `cluster_agent_certificates.revoked_at`) and has not expired, and — for the replay-sensitive
   paths (control-message responses, usage reports) — checks a nonce-uniqueness constraint before
   the operation is allowed to proceed.
4. Only after that verification succeeds does the handler open a `PlatformBypass` (or, for reads
   nested inside an already-tenant/operator-scoped transaction, a temporarily-elevated
   `withPlatformBypass`) transaction to perform the actual database work.

This means the actual isolation boundary for machine callers is **"can this specific certificate's
private key produce a valid signature for this specific agent row,"** not RLS — which is
appropriate, since there is no user session to derive an `app.operator_id` GUC from in the first
place. No call site was found where a machine-caller action skips this verify-then-elevate ordering
(i.e., no case where `PlatformBypass` is set up before the signature check, which would let an
unverified caller's request reach the database before authorization).

## Inventory: operator-scoped tables (dual-scope and marketplace shapes)

The full two-policy operator-scope-only list is above. In addition, every dual-scope table and every
marketplace table catalogued in the companion tenant-isolation audit also carries an `_operator_scope`
policy alongside its tenant-facing one — `capacity_reservations`, `deployments`, `deployment_events`,
`network_reservations`, `network_health_events`, `slo_definitions`, `slo_evaluations`, `incidents`,
`incident_events`, `alert_rules`, `alerts`, `usage_events`, `usage_aggregations`, `invoices`,
`adjustments`, `credit_notes`, `billing_disputes`, `billing_provider_events`, `bilateral_agreements`,
`capacity_offer_grants`, `settlement_records`, and the marketplace-owner side of `capacity_offers`/
`network_service_offers`/`price_books`/`price_rules`. In every one of these, the operator's own
policy is `ALL` (full CRUD on rows it owns), and the tenant-facing counterpart is either also `ALL`
(genuinely joint-ownership tables like `deployments`) or a narrower `SELECT`-only marketplace read
(offers, price books) — an operator never gains write access to a tenant-owned row through any of
these policies, and vice versa.

## Findings

### Finding 1 (Medium) — same as tenant-isolation audit's Finding 1

`support_access_grants` lacking RLS applies identically to operator-scoped support grants
(`scope_type='operator'`) as it does to enterprise ones. See
`docs/security/tenant-isolation-audit.md`'s Finding 1 for the full writeup and recommendation; not
repeated here to avoid duplicate remediation tracking.

### Finding 2 (Informational) — certificate revocation is checked, not cryptographically enforced at the transport layer

Consistent with `docs/project-status.md`'s Known Limitation 11 ("Certificate revocation is
application-level only... not CRL/OCSP-based"), this audit confirms that finding still holds and adds
no new instance of it: every signature-verification call site checked during this audit
(`internal/modules/agents`, `internal/modules/deployments`, `internal/modules/attestation`,
`internal/modules/networkservices`, `internal/modules/billing`) checks `revoked_at IS NULL` in
application code as part of the same query that loads the certificate, not via a separate CRL/OCSP
mechanism — appropriate given control-api never terminates TLS itself (ADR 0007), but worth
re-confirming whenever a new agent-facing route is added: the revocation check must live in the same
code path as the signature verification, not be assumed to happen elsewhere.

### Finding 3 (Informational) — no test proves a revoked agent certificate is rejected mid-session

Existing tests (`internal/app/agents_flow_test.go` and similar) cover certificate issuance and
rotation, but this audit did not find a test that explicitly revokes an agent's certificate mid-test
and then asserts a subsequent signed request using the now-revoked key is rejected. This is a
coverage gap worth closing in a future milestone, not a defect found in the revocation-check code
itself (which was read and confirmed correct at every call site during this audit).

## Verdict

Operator-isolation architecture is sound and follows the identical fail-closed RLS pattern the
tenant-isolation audit found. The operator-specific machine-agent trust boundary (certificate +
signature, verified before any RLS-bypassing database operation) is consistently applied across every
agent-facing route with no ordering violation found. The one real gap
(`support_access_grants` lacking RLS) is shared with the tenant-isolation audit and tracked there. Two
informational findings are noted for future test-coverage improvement; neither reflects a currently
exploitable defect.
