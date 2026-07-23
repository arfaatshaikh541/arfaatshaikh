# GRIDKEEP Permission Matrix (seeded ground truth)

This document is generated from the actual seeded `roles`/`permissions`/`role_permissions`
rows -- most from migration `0002_rbac.up.sql` (Milestone 1), plus permissions added by
`0012_registry_locations.up.sql` (Milestone 2), `0023_workload_model_permissions.up.sql`
(Milestone 4), and `0025_placement_permissions.up.sql` (Milestone 5) -- it is not
aspirational, it is what the running system enforces today. Regenerate after any change
to these with:

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
| **AI Platform Engineer** (`ai_platform_engineer`) | artefacts.download, artefacts.upload, artefacts.view, capacity.view, deployments.rollback, deployments.view, images.register, images.view, models.edit, models.register, models.view, policies.simulate, policies.view, regions.view, reservations.cancel, reservations.create, vulnerability_exceptions.request, workloads.create, workloads.deploy, workloads.edit, workloads.publish, workloads.scale, workloads.view |
| **Application Owner** (`application_owner`) | artefacts.view, deployments.view, usage.view, workloads.create, workloads.deploy, workloads.edit, workloads.pause, workloads.publish, workloads.scale, workloads.view |
| **Compliance Manager** (`compliance_manager`) | approvals.respond, approvals.view, artefacts.view, audit.view, incidents.view, models.approve, policies.simulate, policies.view, reservations.approve, sbom.view, vulnerabilities.view, vulnerability_exceptions.approve |
| **Data Engineer** (`data_engineer`) | artefacts.delete, artefacts.download, artefacts.upload, artefacts.view, models.view, workloads.view |
| **DevOps Engineer** (`devops_engineer`) | capacity.view, deployments.failover, deployments.rollback, deployments.view, images.view, incidents.view, infrastructure.view, regions.select, regions.view, reservations.cancel, reservations.create, sbom.view, vulnerabilities.view, workloads.deploy, workloads.pause, workloads.retry, workloads.scale, workloads.terminate, workloads.view |
| **Enterprise Administrator** (`enterprise_admin`) | approvals.respond, approvals.view, artefacts.delete, artefacts.download, artefacts.upload, artefacts.view, audit.view, billing.view, capacity.view, credentials.manage, deployments.approve, deployments.failover, deployments.rollback, deployments.view, images.approve, images.register, images.revoke, images.view, incidents.manage, incidents.view, infrastructure.view, integrations.manage, models.approve, models.edit, models.publish, models.register, models.retire, models.view, policies.approve, policies.create, policies.edit, policies.publish, policies.rollback, policies.simulate, policies.view, regions.select, regions.view, reservations.approve, reservations.cancel, reservations.create, roles.manage, sbom.view, settings.manage, usage.view, users.manage, vulnerabilities.view, vulnerability_exceptions.approve, vulnerability_exceptions.request, workloads.create, workloads.deploy, workloads.edit, workloads.pause, workloads.publish, workloads.retire, workloads.retry, workloads.scale, workloads.terminate, workloads.view |
| **Enterprise Owner** (`enterprise_owner`) | approvals.respond, approvals.view, artefacts.delete, artefacts.download, artefacts.upload, artefacts.view, audit.view, billing.view, capacity.view, credentials.manage, deployments.approve, deployments.failover, deployments.rollback, deployments.view, images.approve, images.register, images.revoke, images.view, incidents.manage, incidents.view, infrastructure.view, integrations.manage, models.approve, models.edit, models.publish, models.register, models.retire, models.view, policies.approve, policies.create, policies.edit, policies.publish, policies.rollback, policies.simulate, policies.view, regions.select, regions.view, reservations.approve, reservations.cancel, reservations.create, roles.manage, sbom.view, settings.manage, usage.view, users.manage, vulnerabilities.view, vulnerability_exceptions.approve, vulnerability_exceptions.request, workloads.create, workloads.deploy, workloads.edit, workloads.pause, workloads.publish, workloads.retire, workloads.retry, workloads.scale, workloads.terminate, workloads.view |
| **FinOps Manager** (`finops_manager`) | billing.view, capacity.view, reservations.cancel, reservations.create, usage.view |
| **Read-Only Auditor** (`read_only_auditor`) | approvals.view, artefacts.view, audit.view, billing.view, capacity.view, deployments.view, images.view, incidents.view, infrastructure.view, models.view, policies.view, regions.view, sbom.view, usage.view, vulnerabilities.view, workloads.view |
| **Security Administrator** (`security_administrator`) | audit.view, credentials.manage, images.approve, images.revoke, incidents.manage, incidents.view, integrations.manage, policies.approve, policies.create, policies.edit, policies.publish, policies.rollback, policies.simulate, policies.view, reservations.approve, sbom.view, vulnerabilities.view, vulnerability_exceptions.approve, workloads.retire, workloads.terminate |

## Operator Roles

| Role | Permissions |
|---|---|
| **Operator Auditor** (`operator_auditor`) | operator.audit.view, operator.deployments.view, operator.settlements.view, operator.usage.view |
| **Operator Capacity Manager** (`operator_capacity_manager`) | operator.capacity.manage, operator.deployments.view, operator.offerings.manage, operator.reservations.view |
| **Operator Cloud Administrator** (`operator_cloud_administrator`) | operator.capacity.manage, operator.deployments.view, operator.regions.manage |
| **Operator Compliance Officer** (`operator_compliance_officer`) | operator.agreements.manage, operator.audit.view |
| **Operator Edge Administrator** (`operator_edge_administrator`) | operator.capacity.manage, operator.deployments.view, operator.locations.manage |
| **Operator Finance Manager** (`operator_finance_manager`) | operator.pricing.manage, operator.settlements.view, operator.usage.view |
| **Operator Infrastructure Administrator** (`operator_infrastructure_administrator`) | operator.capacity.manage, operator.clusters.manage, operator.deployments.view, operator.locations.manage |
| **Operator Network Administrator** (`operator_network_administrator`) | operator.deployments.view, operator.regions.manage |
| **Operator Platform Owner** (`operator_platform_owner`) | operator.agents.manage, operator.agreements.manage, operator.audit.view, operator.capacity.manage, operator.clusters.manage, operator.deployments.manage, operator.deployments.view, operator.incidents.manage, operator.locations.manage, operator.offerings.manage, operator.pricing.manage, operator.profile.manage, operator.regions.manage, operator.reservations.view, operator.security.manage, operator.settlements.view, operator.sla.manage, operator.usage.view |
| **Operator Product Manager** (`operator_product_manager`) | operator.agreements.manage, operator.offerings.manage, operator.pricing.manage |
| **Operator Security Administrator** (`operator_security_administrator`) | operator.agents.manage, operator.audit.view, operator.incidents.manage, operator.security.manage |
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
