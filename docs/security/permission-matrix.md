# GRIDKEEP Permission Matrix (seeded ground truth)

This document is generated from the actual seeded `roles`/`permissions`/`role_permissions`
rows -- most from migration `0002_rbac.up.sql` (Milestone 1), plus permissions added by
`0012_registry_locations.up.sql` (Milestone 2), `0023_workload_model_permissions.up.sql`
(Milestone 4), `0025_placement_permissions.up.sql` (Milestone 5),
`0029_attestation_permissions.up.sql` (Milestone 8), `0031_network_permissions.up.sql`
(Milestone 9), `0033_assurance_permissions.up.sql` (Milestone 10), and
`0035_billing_permissions.up.sql` (Milestone 11) -- it is not aspirational,
it is what the running system enforces today. Regenerate after any change to these with:

```sql
SELECT r.scope_type, r.key, r.name, string_agg(p.key, ', ' ORDER BY p.key)
FROM roles r
LEFT JOIN role_permissions rp ON rp.role_id = r.id
LEFT JOIN permissions p ON p.id = rp.permission_id
GROUP BY r.scope_type, r.key, r.name ORDER BY r.scope_type, r.key;
```

## Enterprise Roles

| Role | Permissions |
|---|---|
| **AI Platform Engineer** (`ai_platform_engineer`) | artefacts.download, artefacts.upload, artefacts.view, assurance.view, attestation.view, budgets.manage, capacity.view, deployments.rollback, deployments.view, images.register, images.view, models.edit, models.register, models.view, network.view, policies.simulate, policies.view, regions.view, reservations.cancel, reservations.create, slos.manage, vulnerability_exceptions.request, workloads.create, workloads.deploy, workloads.edit, workloads.publish, workloads.scale, workloads.view |
| **Application Owner** (`application_owner`) | artefacts.view, attestation.view, deployments.view, usage.view, workloads.create, workloads.deploy, workloads.edit, workloads.pause, workloads.publish, workloads.scale, workloads.view |
| **Compliance Manager** (`compliance_manager`) | approvals.respond, approvals.view, artefacts.view, attestation.view, audit.view, billing.dispute, incidents.view, models.approve, policies.simulate, policies.view, reservations.approve, sbom.view, vulnerabilities.view, vulnerability_exceptions.approve |
| **Data Engineer** (`data_engineer`) | artefacts.delete, artefacts.download, artefacts.upload, artefacts.view, models.view, workloads.view |
| **DevOps Engineer** (`devops_engineer`) | assurance.view, attestation.view, budgets.manage, capacity.view, deployments.failover, deployments.rollback, deployments.view, images.view, incidents.view, infrastructure.view, network.view, regions.select, regions.view, reservations.cancel, reservations.create, sbom.view, slos.manage, vulnerabilities.view, workloads.deploy, workloads.pause, workloads.retry, workloads.scale, workloads.terminate, workloads.view |
| **Enterprise Administrator** (`enterprise_admin`) | approvals.respond, approvals.view, artefacts.delete, artefacts.download, artefacts.upload, artefacts.view, assurance.view, attestation.view, audit.view, billing.dispute, billing.view, budgets.manage, capacity.view, credentials.manage, deployments.approve, deployments.failover, deployments.rollback, deployments.view, images.approve, images.register, images.revoke, images.view, incidents.manage, incidents.view, infrastructure.view, integrations.manage, models.approve, models.edit, models.publish, models.register, models.retire, models.view, network.view, policies.approve, policies.create, policies.edit, policies.publish, policies.rollback, policies.simulate, policies.view, regions.select, regions.view, reservations.approve, reservations.cancel, reservations.create, roles.manage, sbom.view, settings.manage, slos.manage, usage.view, users.manage, vulnerabilities.view, vulnerability_exceptions.approve, vulnerability_exceptions.request, workloads.create, workloads.deploy, workloads.edit, workloads.pause, workloads.publish, workloads.retire, workloads.retry, workloads.scale, workloads.terminate, workloads.view |
| **Enterprise Owner** (`enterprise_owner`) | approvals.respond, approvals.view, artefacts.delete, artefacts.download, artefacts.upload, artefacts.view, assurance.view, attestation.view, audit.view, billing.dispute, billing.view, budgets.manage, capacity.view, credentials.manage, deployments.approve, deployments.failover, deployments.rollback, deployments.view, images.approve, images.register, images.revoke, images.view, incidents.manage, incidents.view, infrastructure.view, integrations.manage, models.approve, models.edit, models.publish, models.register, models.retire, models.view, network.view, policies.approve, policies.create, policies.edit, policies.publish, policies.rollback, policies.simulate, policies.view, regions.select, regions.view, reservations.approve, reservations.cancel, reservations.create, roles.manage, sbom.view, settings.manage, slos.manage, usage.view, users.manage, vulnerabilities.view, vulnerability_exceptions.approve, vulnerability_exceptions.request, workloads.create, workloads.deploy, workloads.edit, workloads.pause, workloads.publish, workloads.retire, workloads.retry, workloads.scale, workloads.terminate, workloads.view |
| **FinOps Manager** (`finops_manager`) | assurance.view, billing.dispute, billing.view, budgets.manage, capacity.view, network.view, reservations.cancel, reservations.create, usage.view |
| **Read-Only Auditor** (`read_only_auditor`) | approvals.view, artefacts.view, assurance.view, attestation.view, audit.view, billing.view, capacity.view, deployments.view, images.view, incidents.view, infrastructure.view, models.view, network.view, policies.view, regions.view, sbom.view, usage.view, vulnerabilities.view, workloads.view |
| **Security Administrator** (`security_administrator`) | attestation.view, audit.view, credentials.manage, images.approve, images.revoke, incidents.manage, incidents.view, integrations.manage, policies.approve, policies.create, policies.edit, policies.publish, policies.rollback, policies.simulate, policies.view, reservations.approve, sbom.view, vulnerabilities.view, vulnerability_exceptions.approve, workloads.retire, workloads.terminate |

## Operator Roles

| Role | Permissions |
|---|---|
| **Operator Auditor** (`operator_auditor`) | operator.audit.view, operator.deployments.view, operator.settlements.view, operator.usage.view |
| **Operator Capacity Manager** (`operator_capacity_manager`) | operator.capacity.manage, operator.deployments.view, operator.offerings.manage, operator.reservations.view |
| **Operator Cloud Administrator** (`operator_cloud_administrator`) | operator.capacity.manage, operator.deployments.view, operator.regions.manage |
| **Operator Compliance Officer** (`operator_compliance_officer`) | operator.agreements.manage, operator.audit.view |
| **Operator Edge Administrator** (`operator_edge_administrator`) | operator.capacity.manage, operator.deployments.view, operator.locations.manage |
| **Operator Finance Manager** (`operator_finance_manager`) | operator.pricing.manage, operator.settlements.manage, operator.settlements.view, operator.usage.view |
| **Operator Infrastructure Administrator** (`operator_infrastructure_administrator`) | operator.capacity.manage, operator.clusters.manage, operator.deployments.view, operator.locations.manage, operator.sla.manage |
| **Operator Network Administrator** (`operator_network_administrator`) | operator.deployments.view, operator.network.manage, operator.regions.manage |
| **Operator Platform Owner** (`operator_platform_owner`) | operator.agents.manage, operator.agreements.manage, operator.attestation.manage, operator.audit.view, operator.capacity.manage, operator.clusters.manage, operator.deployments.manage, operator.deployments.view, operator.incidents.manage, operator.locations.manage, operator.network.manage, operator.offerings.manage, operator.pricing.manage, operator.profile.manage, operator.regions.manage, operator.reservations.view, operator.security.manage, operator.settlements.manage, operator.settlements.view, operator.sla.manage, operator.usage.view |
| **Operator Product Manager** (`operator_product_manager`) | operator.agreements.manage, operator.offerings.manage, operator.pricing.manage |
| **Operator Security Administrator** (`operator_security_administrator`) | operator.agents.manage, operator.attestation.manage, operator.audit.view, operator.incidents.manage, operator.security.manage |
| **Operator Support Engineer** (`operator_support_engineer`) | operator.deployments.view, operator.incidents.manage |

## Platform Roles

| Role | Permissions |
|---|---|
| **GRIDKEEP Auditor** (`platform_auditor`) | platform.audit.view, platform.billing.view, platform.security.view, platform.support_access.view |
| **GRIDKEEP Billing Administrator** (`platform_billing_administrator`) | platform.billing.manage, platform.billing.view |
| **GRIDKEEP Platform Operations Engineer** (`platform_operations_engineer`) | platform.feature_flags.manage, platform.releases.manage |
| **GRIDKEEP Security Operator** (`platform_security_operator`) | platform.audit.view, platform.security.view, platform.support_access.view |
| **GRIDKEEP Platform Super Administrator** (`platform_super_administrator`) | platform.audit.view, platform.billing.manage, platform.billing.view, platform.container_registries.manage, platform.feature_flags.manage, platform.model_catalogue.manage, platform.operators.manage, platform.regions.manage, platform.releases.manage, platform.security.view, platform.support_access.grant, platform.support_access.view, platform.tenants.manage |
| **GRIDKEEP Support Engineer** (`platform_support_engineer`) | platform.support_access.grant, platform.support_access.view |

## Notes

- Platform roles are granted only via `platform_role_assignments` -- never inherited
  from any enterprise or operator membership (see ADR 0002 and the support-access
  dual-control flow in `internal/modules/platformadmin`).
- A user with no membership and no active, approved support-access grant is denied
  regardless of any permission listed here -- the permission check only runs *after*
  scope resolution succeeds (see `internal/modules/rbac/middleware.go`).
- Permission keys for modules that do not exist yet (deployments, incidents, approvals,
  billing, credentials, integrations, settings, users, roles, ...) are seeded as durable
  product vocabulary but are not yet enforced by any route. They will be wired to real
  enforcement as their owning modules are built in later milestones.
- As of Milestone 2, `operator.regions.manage`, `operator.locations.manage`,
  `operator.clusters.manage`, `operator.profile.manage`, and `operator.agents.manage` are
  enforced for real by `internal/modules/registry` and `internal/modules/agents` (data
  centres, edge sites, clusters, node pools, accelerators, storage pools, network
  capabilities, operator contracts, and operator-agent registration/certificate lifecycle).
  `platform.regions.manage` (new in Milestone 2) gates writes to the global
  region/jurisdiction taxonomy; reading that taxonomy requires only an authenticated
  session, no specific permission, since it is non-sensitive shared reference data.
- As of Milestone 3, `policies.*` are enforced for real by `internal/modules/policies`
  (draft/edit/dual-control publish/rollback/simulate/evaluate against the Python
  policy-engine service).
- As of Milestone 4, `workloads.*`, `models.*`, `images.*`, `artefacts.*`, `sbom.view`,
  `vulnerabilities.view`, and `vulnerability_exceptions.*` are enforced for real by
  `internal/modules/workloads`, `internal/modules/models`, `internal/modules/images`, and
  `internal/modules/artefacts`. `platform.container_registries.manage` and
  `platform.model_catalogue.manage` (new in Milestone 4) gate platform-curated
  supply-chain and model-catalogue reference data the same way `platform.regions.manage`
  gates the region taxonomy.
- As of Milestone 5, `capacity.view`, `reservations.create`, `reservations.cancel`, and
  the new `reservations.approve` (dual-control commit of a capacity reservation) are
  enforced for real by `internal/modules/placement`; `operator.capacity.manage` and the
  new `operator.reservations.view` are enforced for real by
  `internal/modules/capacityoffers`. `regions.view`/`regions.select` remain enforced by
  `internal/modules/registry` as they have been since Milestone 2 -- Milestone 5 is their
  first consumer on the enterprise side (browsing/placing against the region a capacity
  offer sits in).
- Milestone 6 introduces no new permission keys. Cluster-agent registration/revocation,
  certificate rotation, deployment-plan-validation requests, and control-message/
  validation history are all gated by the existing `operator.agents.manage` permission
  from Milestone 2 (an `operator_security_administrator` or `operator_platform_owner`
  concern, consistent with that permission's existing scope) -- a cluster agent is the
  same trust model as an operator agent, scoped one level narrower, not a new privilege
  category. The machine-authenticated poll/respond/rotate/bootstrap endpoints are not
  gated by any permission at all, by design: identity there is proved by certificate
  signature, the same posture as Milestone 2's capacity-snapshot ingestion.
- Milestone 7 also introduces no new permission keys -- every action
  `internal/modules/deployments` needs was already seeded in Milestone 1 anticipating
  exactly this milestone: `workloads.deploy` gates creating a deployment, drafting a
  plan, requesting its approval, and submitting an approved plan for execution;
  `deployments.approve` gates the dual-control plan approve/reject step;
  `workloads.scale`/`workloads.pause`/`workloads.terminate`/`workloads.retry` gate the
  corresponding lifecycle actions (`workloads.pause` covers resume too -- it is the same
  lifecycle-control capability, not two); `deployments.rollback` gates rolling back to a
  previously executed plan version; `deployments.view` gates read access to deployments,
  plans, and the event stream; `credentials.manage` gates workload-secrets CRUD (values
  are never returned by any session-authenticated response regardless of permission --
  see `internal/platform/secretsvault`). `operator.deployments.view` (seeded in
  Milestone 1) is enforced for real for the first time, gating an operator's read-only
  view of deployments running on its own clusters. The agent-facing secret-retrieval and
  command-result endpoints are, like Milestone 6's machine-facing endpoints, not gated by
  any permission at all -- identity is proved by certificate signature, and
  `AgentFetchSecrets` additionally checks the calling cluster agent is the one actually
  assigned to the requested deployment before decrypting anything.
- Milestone 8 introduces two new permission keys, enforced for real by
  `internal/modules/attestation`: `attestation.view` (enterprise) gates the tenant's own
  "customer verification view" of a deployment's confidential-computing attestation status --
  always a redacted summary (decision/provider/reason codes/evaluated_at only) regardless of
  this permission, since the redaction happens by never selecting `measurements`/`raw_evidence`
  in the underlying query, not by a separate permission tier; `operator.attestation.manage`
  (operator) gates creating/revoking attestation policies for the operator's own clusters.
  Viewing attestation sessions/results for an operator's own clusters requires only operator
  membership, mirroring Milestone 6's control-message/validation-history precedent (view is
  membership, manage/mutate is a permission). The agent-facing attestation-session and
  evidence-submission endpoints are, like every other machine-facing endpoint since
  Milestone 2, not gated by any permission at all -- identity is proved by certificate
  signature.
- Milestone 9 introduces two new permission keys, enforced for real by
  `internal/modules/networkservices`: `network.view` (enterprise) gates browsing the
  network-service marketplace and viewing a tenant's own requests/evaluations/reservations/
  health events; `operator.network.manage` (operator) gates publishing/pausing/withdrawing
  network service offers for the operator's own infrastructure. Reservation lifecycle actions
  (create/cancel) deliberately *reuse* the already-generically-named `reservations.create`/
  `reservations.cancel` from Milestone 1 rather than minting network-specific equivalents, and
  viewing reservations held against an operator's own offers reuses `operator.reservations.view`
  from Milestone 5 -- both reuses are documented in migration `0031`'s header comment. Listing an
  operator's own offers requires only operator membership, mirroring Milestone 5's
  `capacityoffers`/Milestone 8's attestation precedent (view is membership, manage/mutate is a
  permission). The one machine-facing network-provision-result endpoint is, like every other
  machine-facing endpoint since Milestone 2, not gated by any permission at all -- identity is
  proved by certificate signature.
- Milestone 10 introduces two new permission keys, enforced for real by
  `internal/modules/assurance`: `assurance.view` (enterprise) gates correlated health, SLOs,
  incidents, and alerts for a tenant's own workloads; `slos.manage` (enterprise) gates SLO
  *and* alert-rule configuration -- deliberately reused for both rather than minting a third key,
  since both are the same "reliability configuration a workload owner sets" concern (see
  migration `0033`'s header comment). Incident lifecycle actions reuse
  `incidents.view`/`incidents.manage` from Milestone 1, activated for real enforcement here for
  the first time. Operator-side SLA/alert-rule configuration reuses `operator.sla.manage`, also
  seeded in Milestone 1 but, remarkably, never once granted to any role until this migration --
  granted to Operator Platform Owner (blanket) and Operator Infrastructure Administrator, the
  role whose existing remit (capacity/clusters/locations) an SLA on that same infrastructure most
  naturally belongs to. Operator-side incident lifecycle reuses `operator.incidents.manage` from
  Milestone 1. Every read (SLOs, incidents, incident events, alert rules, alerts, correlated
  health) on the operator side requires only operator membership, mirroring Milestone 5/8/9's own
  precedent (view is membership, manage/mutate is a permission). Audit correlation
  (`GET .../audit-correlation/{resourceType}/{resourceID}`) deliberately reuses
  `audit.view`/`operator.audit.view` from Milestone 1 rather than `assurance.view`, since it
  exposes audit evidence directly -- the same disclosure the `auditlog` module's own routes
  already gate.
- Milestone 11 introduces only three new permission keys, enforced for real by
  `internal/modules/billing`: `budgets.manage` (enterprise) gates defining/archiving a tenant's
  own spend budgets -- deliberately narrower than `usage.view`/`billing.view`, since a budget is
  private financial configuration a tenant sets for itself, not something a broad billing-viewer
  needs to write; granted to Enterprise Owner/Administrator (blanket), plus FinOps Manager (who
  already holds `usage.view`/`billing.view`) and AI Platform Engineer/DevOps Engineer (who
  already hold `slos.manage`, the closest-adjacent "reliability configuration" permission --
  budget alerts reuse Milestone 10's own `alert_rules`/`alerts` infrastructure via a widened
  `metric_source`, so the same roles that configure SLO/alert-rule reliability now configure
  budget thresholds too). `billing.dispute` (enterprise) gates opening a dispute against an
  issued invoice -- a distinct, narrower action from merely viewing `billing.view`; granted to
  Enterprise Owner/Administrator (blanket), FinOps Manager, and Compliance Manager (whose
  existing `approvals.respond` remit already covers "responding to a financial disagreement").
  `operator.settlements.manage` (operator) gates creating/reconciling settlement records and
  issuing adjustments/credit notes/dispute resolutions -- narrower than the already-seeded
  `operator.settlements.view` (viewing is broad membership-adjacent visibility, settling money
  is not); granted to Operator Platform Owner (blanket) and Operator Finance Manager, the role
  already holding both `operator.pricing.manage` and `operator.settlements.view`, the two
  closest-adjacent permissions to "actually reconcile a settlement." Every other billing action
  reuses Milestone 1's own already-seeded, until-now-ungranted-for-real vocabulary:
  `usage.view`/`billing.view` (enterprise, gating usage/aggregation reads, quote requests, and
  invoice/credit-note/dispute reads); `operator.pricing.manage`/`operator.usage.view`/
  `operator.settlements.view` (operator, gating price-book writes, usage reads, and
  invoice/settlement/dispute reads respectively) -- the richest "roles anticipate milestones"
  case this project has found yet, five permission keys seeded in Milestone 1 and never granted
  for real enforcement until this migration. Price book reads require only operator membership,
  mirroring Milestone 5/8/9/10's own precedent (view is membership, manage/mutate is a
  permission). Generating an invoice, creating a settlement, issuing an adjustment or credit
  note, and resolving a dispute are all operator-triggered actions gated by
  `operator.settlements.manage`; a tenant can never trigger its own invoice generation, matching
  the approved scope's backend-authoritative-billing requirement. The one machine-facing
  usage-event-report endpoint is, like every other machine-facing endpoint since Milestone 2,
  not gated by any permission at all -- identity is proved by certificate signature, with a
  database-level `UNIQUE (cluster_agent_id, nonce)` constraint (not just the usual pre-insert
  `SELECT` check every other nonce-protected table in this codebase uses) since usage events
  directly drive billing amounts.
- Milestone 12 introduces **zero** new permission keys -- the richest "roles anticipate
  milestones" case this project has found yet, richer even than Milestone 11's five. Bilateral
  agreement and capacity-offer-grant management (`internal/modules/capacityoffers`) reuses
  `operator.agreements.manage` ("Manage operator-enterprise agreements"), seeded in Milestone 1
  and never enforced for real until this migration -- already granted to Operator Platform Owner
  (blanket), Operator Product Manager, and Operator Compliance Officer, exactly the roles whose
  existing remit ("offerings and agreements", "agreements and audit") already anticipated this.
  Marking an offer degraded and toggling its visibility reuse the already-enforced
  `operator.capacity.manage`. Settlement-contract creation
  (`internal/modules/billing.CreateSettlementForAgreement`) reuses the already-enforced
  `operator.settlements.manage` from Milestone 11. On the enterprise side, seeing a private
  offer once granted requires nothing beyond the already-enforced `capacity.view` (the grant
  itself, not a new permission, is what makes the offer visible at all -- see
  `capacity_offers_enterprise_read`'s RLS policy in migration `0036`), and viewing the tenant's
  own bilateral agreements reuses the same `capacity.view`.
- Milestone 13 also introduces **zero** new permission keys. Publishing a model version to the
  exchange, unpublishing it, and creating/revoking a `model_access_grants` row
  (`internal/modules/models`) all reuse `models.publish` ("Publish a model for use"), seeded in
  Milestone 1 (`0002_rbac.up.sql`) and never enforced for real until this migration -- already
  granted only to Enterprise Owner and Enterprise Administrator, the two roles whose existing
  remit already covers commercializing a tenant's own approved assets. Provider onboarding
  (`CreateProvider`/`SuspendProvider`/`ReactivateProvider`, mounted top-level like
  Milestone 2's jurisdictions/regions) reuses `platform.model_catalogue.manage`, seeded in
  Milestone 4 (`0018_model_catalogue.up.sql`) for the read-only global provider/licence
  catalogue but never given a write endpoint until now -- still granted only to GRIDKEEP
  Platform Super Administrator. Browsing the marketplace, viewing a version's grants, and
  viewing received grants reuse the already-enforced `models.view`. A cross-tenant workload's
  model-version selection (`internal/modules/workloads.validateSelections`) needs no new
  permission either -- eligibility is decided by row visibility (RLS's
  `model_versions_marketplace_read` policy plus the widened WHERE clause in
  `modelVersionEligibilityFacts`), not by a permission check, the same "grant is visibility,
  not a role" design Milestone 12 established for capacity.
